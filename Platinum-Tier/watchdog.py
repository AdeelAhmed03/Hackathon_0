#!/usr/bin/env python3
"""
Watchdog Process Monitor (Platinum Tier) — Spec Section 7.4

Dedicated process health monitor with cloud/local zone awareness:
  1. Zone-aware process sets: cloud monitors cloud watchers, local monitors local watchers
  2. Restarts dead processes with exponential backoff
  3. Tracks health metrics (uptime, restart count, last heartbeat)
  4. Escalates to human (ERROR alert) after MAX_RESTART_ATTEMPTS
  5. Cloud: writes alerts to Updates/ for local agent pickup via Git sync
  6. Cross-zone heartbeat checking (cloud_heartbeat.json / local_heartbeat.json)
  7. Graceful degradation: queues tasks when services are down
  8. Provides --status for health dashboard, --test for self-test

Zones (via VAULT_ENVIRONMENT):
  cloud  → monitors cloud watchers (gmail, social, cloud_sync, orchestrator_cloud)
  local  → monitors local watchers (hitl, scheduler, orchestrator_local) + heartbeat cross-check
  both   → monitors everything (single-machine dev mode)

Usage:
    python watchdog.py                 # Monitor zone-appropriate processes
    python watchdog.py --zone cloud    # Force cloud zone
    python watchdog.py --status        # Print health report
    python watchdog.py --dry-run       # Log only, no restarts
    python watchdog.py --test          # Run self-tests
    python watchdog.py --check-once    # Single health check, then exit
"""

import json
import logging
import os
import subprocess
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── AUDIT LOGGER INTEGRATION ─────────────────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
WATCHER_DIR = VAULT_DIR / "watcher"
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "watchdog.log"
HEALTH_FILE = LOGS_DIR / "watchdog_health.json"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"

POLL_INTERVAL = int(os.environ.get("WATCHDOG_POLL_SECONDS", "15"))
MAX_RESTART_ATTEMPTS = int(os.environ.get("WATCHDOG_MAX_RESTARTS", "5"))
RESTART_BACKOFF_BASE = int(os.environ.get("WATCHDOG_BACKOFF_BASE", "2"))
ESCALATION_COOLDOWN = int(os.environ.get("WATCHDOG_ESCALATION_COOLDOWN", "3600"))  # 1 hour

# Platinum: Zone detection
VAULT_ENVIRONMENT = os.environ.get("VAULT_ENVIRONMENT", "both")
UPDATES_DIR = VAULT_DIR / "data" / "Updates"
CLOUD_HEARTBEAT = VAULT_DIR / "data" / "cloud_heartbeat.json"
LOCAL_HEARTBEAT = VAULT_DIR / "data" / "local_heartbeat.json"
HEARTBEAT_STALE_SECONDS = int(os.environ.get("WATCHDOG_HEARTBEAT_STALE", "600"))  # 10 min

# ── MONITORED PROCESSES (zone-tagged) ────────────────────────────────────
# name -> {script, args, type, critical, zone}
# zone: "cloud" | "local" | "both" — determines which watchdog instance monitors it
MONITORED_PROCESSES = {
    # ── Cloud zone watchers (24/7 VM, triage-oriented) ───────────────────
    "gmail_watcher": {
        "script": "watcher/gmail_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": True,
        "zone": "cloud",
    },
    "facebook_watcher": {
        "script": "watcher/facebook_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": False,
        "zone": "cloud",
    },
    "instagram_watcher": {
        "script": "watcher/instagram_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": False,
        "zone": "cloud",
    },
    "x_watcher": {
        "script": "watcher/x_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": False,
        "zone": "cloud",
    },
    "cloud_sync_watcher": {
        "script": "watcher/cloud_sync_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": True,
        "zone": "cloud",
    },
    "orchestrator_cloud": {
        "script": "watcher/orchestrator_cloud.py",
        "args": [],
        "type": "orchestrator",
        "critical": True,
        "zone": "cloud",
    },
    # ── Local zone watchers (execution-oriented, holds secrets) ──────────
    "hitl_watcher": {
        "script": "watcher/hitl_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": True,
        "zone": "local",
    },
    "orchestrator_local": {
        "script": "watcher/orchestrator_local.py",
        "args": [],
        "type": "orchestrator",
        "critical": True,
        "zone": "local",
    },
    # ── Both zones ───────────────────────────────────────────────────────
    "needs_action_watcher": {
        "script": "watcher/needs_action_watcher.py",
        "args": [],
        "type": "watcher",
        "critical": True,
        "zone": "both",
    },
    "scheduler": {
        "script": "watcher/scheduler.py",
        "args": [],
        "type": "watcher",
        "critical": True,
        "zone": "both",
    },
    # MCP Servers (on-demand, zone-tagged for monitoring)
    "odoo_mcp": {
        "script": "mcp-servers/odoo-mcp/odoo_mcp.py",
        "args": [],
        "type": "mcp",
        "critical": False,
        "zone": "both",
    },
    "social_mcp": {
        "script": "mcp-servers/social-mcp/social_mcp.py",
        "args": [],
        "type": "mcp",
        "critical": False,
        "zone": "cloud",
    },
}


def get_zone_processes(zone):
    """Return processes appropriate for the current zone."""
    return {
        name: config for name, config in MONITORED_PROCESSES.items()
        if config["zone"] == zone or config["zone"] == "both" or zone == "both"
    }

# ── LOGGING SETUP ────────────────────────────────────────────────────────
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("Watchdog")


# ── HEALTH STATE ─────────────────────────────────────────────────────────
def load_health():
    """Load health state from JSON file."""
    if HEALTH_FILE.exists():
        try:
            content = HEALTH_FILE.read_text(encoding="utf-8").strip()
            if content:
                return json.loads(content)
        except (json.JSONDecodeError, OSError):
            pass
    return {"processes": {}, "last_check": None, "started_at": None}


def save_health(health):
    """Save health state to JSON file."""
    try:
        health["last_check"] = datetime.now(timezone.utc).isoformat()
        HEALTH_FILE.write_text(json.dumps(health, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error(f"Failed to save health state: {e}")


def get_process_health(health, name):
    """Get or initialize health record for a process."""
    if name not in health["processes"]:
        health["processes"][name] = {
            "pid": None,
            "status": "unknown",
            "restart_count": 0,
            "consecutive_failures": 0,
            "last_started": None,
            "last_died": None,
            "last_escalation": None,
            "uptime_seconds": 0,
            "escalated": False,
        }
    return health["processes"][name]


# ── PROCESS MANAGEMENT ───────────────────────────────────────────────────
_child_procs = {}


def is_process_alive(pid):
    """Check whether a PID is still running."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def start_process(name, config, dry_run=False):
    """Start a monitored process and return its PID."""
    script_path = VAULT_DIR / config["script"]
    if not script_path.exists():
        logger.error(f"[{name}] Script not found: {script_path}")
        return None

    cmd = [sys.executable, str(script_path)] + config["args"]

    if dry_run:
        logger.info(f"[DRY RUN] Would start {name}: {' '.join(cmd)}")
        return None

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _child_procs[name] = proc
        logger.info(f"[{name}] Started (PID {proc.pid})")
        return proc.pid
    except OSError as e:
        logger.error(f"[{name}] Failed to start: {e}")
        return None


def stop_process(name):
    """Stop a monitored process."""
    proc = _child_procs.get(name)
    if proc and proc.poll() is None:
        logger.info(f"[{name}] Stopping (PID {proc.pid})...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.warning(f"[{name}] Force-killed")
    _child_procs.pop(name, None)


# ── ESCALATION ───────────────────────────────────────────────────────────
def escalate_failure(name, config, proc_health):
    """Create an ERROR alert when a process exceeds max restart attempts."""
    now = datetime.now(timezone.utc)

    # Check cooldown — don't spam alerts
    last_esc = proc_health.get("last_escalation")
    if last_esc:
        try:
            elapsed = (now - datetime.fromisoformat(last_esc)).total_seconds()
            if elapsed < ESCALATION_COOLDOWN:
                logger.debug(f"[{name}] Escalation on cooldown ({int(elapsed)}s < {ESCALATION_COOLDOWN}s)")
                return
        except (ValueError, TypeError):
            pass

    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    error_id = now.strftime("%Y%m%d_%H%M%S")
    filename = f"ERROR_WATCHDOG_{name}_{error_id}.md"
    file_path = NEEDS_ACTION_DIR / filename

    critical_tag = " [CRITICAL]" if config.get("critical") else ""

    content = f"""---
type: error_alert
status: pending
priority: {"critical" if config.get("critical") else "high"}
error_type: process_failure
process_name: {name}
process_type: {config["type"]}
restart_attempts: {proc_health["restart_count"]}
consecutive_failures: {proc_health["consecutive_failures"]}
created: {now.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Watchdog Alert:{critical_tag} {name} Repeatedly Failing

The process **{name}** ({config["type"]}) has failed **{proc_health["consecutive_failures"]}** consecutive times
and exceeded the maximum restart attempts ({MAX_RESTART_ATTEMPTS}).

**Script:** `{config["script"]}`
**Last Started:** {proc_health.get("last_started", "never")}
**Last Died:** {proc_health.get("last_died", "unknown")}
**Total Restarts:** {proc_health["restart_count"]}

### Required Action

- Check the process logs for errors
- Verify configuration and credentials
- Manually restart: `python {config["script"]}`
- If resolved, the watchdog will auto-resume monitoring
"""

    try:
        file_path.write_text(content, encoding="utf-8")
        proc_health["last_escalation"] = now.isoformat()
        proc_health["escalated"] = True
        logger.warning(f"[{name}] ESCALATED — created {filename}")

        # Platinum: If running on cloud, also write alert to Updates/ for local pickup
        if VAULT_ENVIRONMENT == "cloud":
            UPDATES_DIR.mkdir(parents=True, exist_ok=True)
            alert_file = UPDATES_DIR / f"cloud_alert_{name}_{error_id}.md"
            alert_file.write_text(
                f"---\ntype: cloud_alert\nsource: watchdog\n"
                f"timestamp: {now.strftime('%Y-%m-%d %H:%M')}\n"
                f"summary: ALERT — {name} repeatedly failing on cloud VM\n"
                f"severity: {'critical' if config.get('critical') else 'high'}\n---\n\n"
                f"# Cloud VM Alert: {name} Down\n\n"
                f"The cloud process **{name}** has failed {proc_health['consecutive_failures']} times.\n"
                f"Script: `{config['script']}`\n\n"
                f"**Action required**: Check cloud VM logs and restart manually if needed.\n",
                encoding="utf-8",
            )
            logger.info(f"[{name}] Cloud alert written to Updates/ for local sync")
    except OSError as e:
        logger.error(f"[{name}] Failed to create escalation alert: {e}")


# ── HEALTH CHECK LOOP ────────────────────────────────────────────────────
def check_cross_zone_heartbeat(health, zone):
    """Platinum: Check the other zone's heartbeat file for staleness.

    Cloud watchdog checks local_heartbeat.json; local checks cloud_heartbeat.json.
    If stale, creates an alert in the appropriate queue.
    """
    if zone == "both":
        return  # Single-machine mode, no cross-checking needed

    if zone == "cloud":
        heartbeat_file = LOCAL_HEARTBEAT
        other_zone = "local"
    else:
        heartbeat_file = CLOUD_HEARTBEAT
        other_zone = "cloud"

    if not heartbeat_file.exists():
        return  # Other zone hasn't started yet

    try:
        data = json.loads(heartbeat_file.read_text(encoding="utf-8"))
        ts_str = data.get("timestamp")
        if not ts_str:
            return

        ts = datetime.fromisoformat(ts_str)
        now = datetime.now()
        # Make both naive or both aware for comparison
        if ts.tzinfo is not None:
            now = datetime.now(timezone.utc)
        age = (now - ts).total_seconds()

        if age > HEARTBEAT_STALE_SECONDS:
            logger.warning(
                f"[HEARTBEAT] {other_zone} heartbeat is stale ({int(age)}s old, threshold {HEARTBEAT_STALE_SECONDS}s)"
            )

            # Write alert
            if zone == "cloud":
                UPDATES_DIR.mkdir(parents=True, exist_ok=True)
                alert_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                alert_file = UPDATES_DIR / f"cloud_alert_heartbeat_{alert_id}.md"
                alert_file.write_text(
                    f"---\ntype: cloud_alert\nsource: watchdog\n"
                    f"timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"summary: Local heartbeat stale ({int(age)}s)\n"
                    f"severity: high\n---\n\n"
                    f"# Cross-Zone Alert: Local System Unresponsive\n\n"
                    f"The local system's heartbeat is {int(age)}s old (threshold: {HEARTBEAT_STALE_SECONDS}s).\n"
                    f"Local executive may be down. Check local machine.\n",
                    encoding="utf-8",
                )
            else:
                # Local watchdog: write Needs_Action alert for human
                NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
                alert_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                alert_file = NEEDS_ACTION_DIR / f"ALERT_cloud_heartbeat_{alert_id}.md"
                alert_file.write_text(
                    f"---\ntype: error_alert\nstatus: pending\npriority: critical\n"
                    f"error_type: heartbeat_stale\nprocess_name: cloud_executive\n"
                    f"created: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n---\n\n"
                    f"## Cloud VM Heartbeat Alert\n\n"
                    f"The cloud VM's heartbeat is {int(age)}s old (threshold: {HEARTBEAT_STALE_SECONDS}s).\n"
                    f"Cloud executive may be down. Check cloud VM status.\n\n"
                    f"### Required Action\n- SSH into cloud VM and check services\n"
                    f"- Run: `docker ps` to check Odoo/nginx\n"
                    f"- Run: `systemctl status orchestrator-cloud` to check orchestrator\n",
                    encoding="utf-8",
                )
        else:
            logger.debug(f"[HEARTBEAT] {other_zone} heartbeat OK ({int(age)}s old)")

    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning(f"[HEARTBEAT] Failed to check {other_zone} heartbeat: {e}")


def check_all_processes(health, dry_run=False, zone="both"):
    """Check zone-appropriate processes, restart dead ones, escalate as needed."""
    now = datetime.now(timezone.utc)
    zone_processes = get_zone_processes(zone)

    # Platinum: cross-zone heartbeat check
    check_cross_zone_heartbeat(health, zone)

    for name, config in zone_processes.items():
        proc_health = get_process_health(health, name)
        pid = proc_health.get("pid")
        alive = is_process_alive(pid)

        if alive:
            # Update uptime
            if proc_health.get("last_started"):
                try:
                    started = datetime.fromisoformat(proc_health["last_started"])
                    proc_health["uptime_seconds"] = int((now - started).total_seconds())
                except (ValueError, TypeError):
                    pass
            proc_health["status"] = "running"
            proc_health["consecutive_failures"] = 0
            proc_health["escalated"] = False
            continue

        # Process is dead
        if pid:
            logger.warning(f"[{name}] Dead (was PID {pid})")
            proc_health["last_died"] = now.isoformat()
            proc_health["consecutive_failures"] += 1

        proc_health["status"] = "dead"
        proc_health["uptime_seconds"] = 0

        # Check if we should escalate instead of restart
        if proc_health["consecutive_failures"] >= MAX_RESTART_ATTEMPTS:
            proc_health["status"] = "escalated"
            escalate_failure(name, config, proc_health)
            continue

        # Restart with backoff
        attempt = proc_health["consecutive_failures"]
        if attempt > 0:
            delay = RESTART_BACKOFF_BASE ** min(attempt, 5)  # Cap at 32s
            logger.info(f"[{name}] Backoff: waiting {delay}s before restart (attempt {attempt})")
            if not dry_run:
                time.sleep(delay)

        new_pid = start_process(name, config, dry_run=dry_run)
        if new_pid:
            proc_health["pid"] = new_pid
            proc_health["status"] = "running"
            proc_health["last_started"] = now.isoformat()
            proc_health["restart_count"] += 1
        elif not dry_run:
            proc_health["consecutive_failures"] += 1

    save_health(health)


# ── STATUS REPORT ────────────────────────────────────────────────────────
def print_status(zone="both"):
    """Print health report for zone-appropriate processes."""
    health = load_health()
    zone_processes = get_zone_processes(zone)
    print("=" * 70)
    print(f"  WATCHDOG HEALTH REPORT — Platinum Tier (zone: {zone})")
    print("=" * 70)
    print(f"  Last check: {health.get('last_check', 'never')}")
    print(f"  Started:    {health.get('started_at', 'never')}")
    print()
    print(f"  {'Process':<25s} {'Zone':<7s} {'Status':<12s} {'PID':<8s} {'Restarts':<10s} {'Uptime'}")
    print(f"  {'-'*25} {'-'*7} {'-'*12} {'-'*8} {'-'*10} {'-'*15}")

    for name, config in zone_processes.items():
        proc = health.get("processes", {}).get(name, {})
        status = proc.get("status", "unknown")
        pid = proc.get("pid", "-")
        restarts = proc.get("restart_count", 0)
        uptime = proc.get("uptime_seconds", 0)

        # Format uptime
        if uptime > 3600:
            uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"
        elif uptime > 60:
            uptime_str = f"{uptime // 60}m {uptime % 60}s"
        else:
            uptime_str = f"{uptime}s"

        # Status indicator
        if status == "running":
            indicator = "OK"
        elif status == "escalated":
            indicator = "ESCALATED"
        elif status == "dead":
            indicator = "DEAD"
        else:
            indicator = "UNKNOWN"

        critical = "*" if config.get("critical") else " "
        proc_zone = config.get("zone", "both")
        print(f"  {critical}{name:<24s} {proc_zone:<7s} {indicator:<12s} {str(pid):<8s} {str(restarts):<10s} {uptime_str}")

    print()
    print("  * = critical process")

    # Summary stats
    procs = health.get("processes", {})
    running = sum(1 for p in procs.values() if p.get("status") == "running")
    dead = sum(1 for p in procs.values() if p.get("status") == "dead")
    escalated = sum(1 for p in procs.values() if p.get("status") == "escalated")
    total_restarts = sum(p.get("restart_count", 0) for p in procs.values())

    print(f"\n  Summary: {running} running, {dead} dead, {escalated} escalated")
    print(f"  Total restarts: {total_restarts}")
    print("=" * 65)


# ── GRACEFUL DEGRADATION ─────────────────────────────────────────────────
def queue_degraded_task(service_name, action, details):
    """Queue a task file when a service is down (graceful degradation).

    Instead of failing silently, creates a task in Needs_Action that
    the agent will process once the service is restored.
    """
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y%m%d_%H%M%S")
    filename = f"DEFERRED_{service_name}_{today}.md"
    file_path = NEEDS_ACTION_DIR / filename

    content = f"""---
type: deferred_task
status: pending
priority: medium
service: {service_name}
action: {action}
created: {now.strftime("%Y-%m-%dT%H:%M:%SZ")}
deferred_reason: service_unavailable
---

## Deferred Task: {action}

The service **{service_name}** was unavailable when this action was requested.
This task has been queued for retry when the service is restored.

### Details

{details}

### Recovery

The watchdog will attempt to restart the service.
Once the service is running, this task should be re-processed.
"""

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"[DEGRADE] Queued deferred task: {filename}")
        return file_path
    except OSError as e:
        logger.error(f"[DEGRADE] Failed to queue deferred task: {e}")
        return None


# ── AUDIT LOG INTEGRATION ────────────────────────────────────────────────
def log_health_snapshot(health):
    """Write a health snapshot via centralized audit_logger (Spec 6.3).

    Falls back to inline JSON write if audit_logger is not importable.
    """
    procs = health.get("processes", {})
    params = {
        "running": sum(1 for p in procs.values() if p.get("status") == "running"),
        "dead": sum(1 for p in procs.values() if p.get("status") == "dead"),
        "escalated": sum(1 for p in procs.values() if p.get("status") == "escalated"),
        "total_restarts": sum(p.get("restart_count", 0) for p in procs.values()),
    }

    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="watchdog.health_check",
            actor="watchdog",
            target="all_processes",
            parameters=params,
            result="ok",
            severity="INFO",
        )
        return

    # Fallback: inline JSON write (pre-Gold compatibility)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"

    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action_type": "watchdog.health_check",
        "actor": "watchdog",
        "target": "all_processes",
        "parameters": params,
        "result": "ok",
        "severity": "info",
        "correlation_id": None,
        "duration_ms": None,
        "error_trace": None,
    }

    try:
        existing = []
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8").strip()
            if content:
                existing = json.loads(content)
        existing.append(entry)
        log_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass


# ── SELF-TEST ────────────────────────────────────────────────────────────
def self_test():
    """Run self-tests for watchdog module."""
    print("=" * 60)
    print("  WATCHDOG SELF-TEST")
    print("=" * 60)

    passed = 0
    total = 0

    # Test 1: Health state load/save
    total += 1
    health = load_health()
    health["started_at"] = datetime.now(timezone.utc).isoformat()
    save_health(health)
    reloaded = load_health()
    ok = reloaded.get("started_at") is not None
    print(f"  [{'PASS' if ok else 'FAIL'}] Health state load/save")
    if ok: passed += 1

    # Test 2: Process health initialization
    total += 1
    ph = get_process_health(health, "test_process")
    ok = ph["status"] == "unknown" and ph["restart_count"] == 0
    print(f"  [{'PASS' if ok else 'FAIL'}] Process health init: status={ph['status']}")
    if ok: passed += 1

    # Test 3: is_process_alive with current PID
    total += 1
    ok = is_process_alive(os.getpid())
    print(f"  [{'PASS' if ok else 'FAIL'}] is_process_alive(current PID={os.getpid()})")
    if ok: passed += 1

    # Test 4: is_process_alive with invalid PID
    total += 1
    ok = not is_process_alive(999999)
    print(f"  [{'PASS' if ok else 'FAIL'}] is_process_alive(999999) = False")
    if ok: passed += 1

    # Test 5: queue_degraded_task creates file
    total += 1
    path = queue_degraded_task("test_service", "test_action", "Self-test deferred task")
    ok = path is not None and path.exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] queue_degraded_task creates file")
    if ok:
        passed += 1
        try:
            path.unlink()
        except OSError:
            pass

    # Test 6: Escalation creates ERROR alert
    total += 1
    test_config = {"script": "test.py", "type": "watcher", "critical": True}
    test_ph = get_process_health(health, "test_escalation")
    test_ph["consecutive_failures"] = MAX_RESTART_ATTEMPTS
    test_ph["restart_count"] = MAX_RESTART_ATTEMPTS
    escalate_failure("test_escalation", test_config, test_ph)
    alerts = list(NEEDS_ACTION_DIR.glob("ERROR_WATCHDOG_test_escalation_*.md"))
    ok = len(alerts) > 0
    print(f"  [{'PASS' if ok else 'FAIL'}] escalate_failure creates ERROR alert")
    if ok: passed += 1
    # Cleanup
    for a in alerts:
        try:
            a.unlink()
        except OSError:
            pass

    # Test 7: MONITORED_PROCESSES has expected Platinum entries
    total += 1
    expected = ["gmail_watcher", "needs_action_watcher", "scheduler", "odoo_mcp",
                "orchestrator_cloud", "orchestrator_local", "hitl_watcher"]
    ok = all(name in MONITORED_PROCESSES for name in expected)
    print(f"  [{'PASS' if ok else 'FAIL'}] MONITORED_PROCESSES has all expected Platinum entries")
    if ok: passed += 1

    # Test 9: Zone filtering returns correct subsets
    total += 1
    cloud_procs = get_zone_processes("cloud")
    local_procs = get_zone_processes("local")
    ok = "gmail_watcher" in cloud_procs and "gmail_watcher" not in local_procs
    ok = ok and "hitl_watcher" in local_procs and "hitl_watcher" not in cloud_procs
    ok = ok and "needs_action_watcher" in cloud_procs and "needs_action_watcher" in local_procs
    print(f"  [{'PASS' if ok else 'FAIL'}] get_zone_processes returns correct subsets")
    if ok: passed += 1

    # Test 8: log_health_snapshot writes audit log
    total += 1
    log_health_snapshot(health)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"
    ok = log_file.exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] log_health_snapshot writes to audit log")
    if ok: passed += 1

    # Cleanup test process entries
    health["processes"].pop("test_process", None)
    health["processes"].pop("test_escalation", None)
    save_health(health)

    print(f"\n  Result: {passed}/{total} tests passed\n")
    return passed == total


# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    global logger

    parser = argparse.ArgumentParser(
        description="Watchdog process monitor (Platinum Tier) — zone-aware monitoring of watchers and MCPs"
    )
    parser.add_argument("--dry-run", action="store_true", help="Log actions without starting/stopping processes")
    parser.add_argument("--status", action="store_true", help="Print health report and exit")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument("--check-once", action="store_true", help="Single health check, then exit")
    parser.add_argument("--zone", choices=["cloud", "local", "both"], default=VAULT_ENVIRONMENT,
                        help=f"Override zone (default: {VAULT_ENVIRONMENT} from VAULT_ENVIRONMENT)")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help=f"Poll interval in seconds (default: {POLL_INTERVAL})")
    args = parser.parse_args()

    logger = setup_logging()

    if args.test:
        success = self_test()
        return 0 if success else 1

    zone = args.zone

    if args.status:
        print_status(zone=zone)
        return 0

    health = load_health()
    health["started_at"] = datetime.now(timezone.utc).isoformat()
    save_health(health)

    zone_processes = get_zone_processes(zone)
    mode = "DRY RUN" if args.dry_run else "ACTIVE"
    logger.info(f"Watchdog starting ({mode}, zone={zone}), poll interval: {args.interval}s")
    logger.info(f"Monitoring {len(zone_processes)}/{len(MONITORED_PROCESSES)} processes for zone '{zone}', max restarts: {MAX_RESTART_ATTEMPTS}")

    if args.check_once:
        check_all_processes(health, dry_run=args.dry_run, zone=zone)
        log_health_snapshot(health)
        print_status(zone=zone)
        return 0

    try:
        check_count = 0
        while True:
            check_all_processes(health, dry_run=args.dry_run, zone=zone)
            check_count += 1

            # Log health snapshot every 10 checks (~2.5 min at 15s interval)
            if check_count % 10 == 0:
                log_health_snapshot(health)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user (Ctrl+C)")
    finally:
        # Stop all child processes we started
        for name in list(_child_procs.keys()):
            stop_process(name)
        save_health(health)
        logger.info("Watchdog shut down, final health saved")

    return 0


if __name__ == "__main__":
    sys.exit(main())
