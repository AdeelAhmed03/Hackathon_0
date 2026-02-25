#!/usr/bin/env python3
"""
Orchestrator — Platinum Tier

Central process supervisor with cloud/local zone awareness.

Zones (detected via VAULT_ENVIRONMENT):
  cloud  → runs orchestrator_cloud.py + cloud watchers (gmail, social)
  local  → runs orchestrator_local.py + local watchers (hitl, scheduler)
  both   → (default, single-machine dev) runs everything

Responsibilities:
  1. Supervise zone-appropriate watcher subprocesses (PID check + restart)
  2. Cron jobs: dashboard refresh, weekly audit, error monitoring
  3. Delegation directory monitoring (Needs_Action/cloud/ ↔ Needs_Action/local/)
  4. Claim-by-move double-work prevention
  5. Health checks and quarantine monitoring

Run:
  python orchestrator.py                   # auto-detect zone from VAULT_ENVIRONMENT
  python orchestrator.py --zone cloud      # force cloud zone
  python orchestrator.py --zone local      # force local zone
  python orchestrator.py --dry-run         # log only, no subprocesses
  python orchestrator.py --status          # print health report and exit
  python orchestrator.py --no-watchers     # cron jobs only
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    import schedule
except ImportError:
    print("Error: 'schedule' package not installed. Run: pip install schedule")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
WATCHER_DIR = VAULT_DIR / "watcher"
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "orchestrator.log"
PID_FILE = VAULT_DIR / ".orchestrator.pids.json"

# Platinum directories
NEEDS_ACTION_CLOUD = VAULT_DIR / "data" / "Needs_Action" / "cloud"
NEEDS_ACTION_LOCAL = VAULT_DIR / "data" / "Needs_Action" / "local"
IN_PROGRESS_CLOUD = VAULT_DIR / "data" / "In_Progress" / "cloud"
IN_PROGRESS_LOCAL = VAULT_DIR / "data" / "In_Progress" / "local"
PLANS_CLOUD = VAULT_DIR / "data" / "Plans" / "cloud"
PENDING_APPROVAL = VAULT_DIR / "data" / "Pending_Approval" / "local"
APPROVED_DIR = VAULT_DIR / "data" / "Approved"
UPDATES_DIR = VAULT_DIR / "data" / "Updates"
DONE_CLOUD = VAULT_DIR / "data" / "Done" / "cloud"
DONE_LOCAL = VAULT_DIR / "data" / "Done" / "local"
QUARANTINE_DIR = VAULT_DIR / "data" / "Quarantine"
BRIEFINGS_DIR = VAULT_DIR / "data" / "Briefings"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"

# ── AUDIT LOGGER INTEGRATION ─────────────────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

# ── ZONE DETECTION ────────────────────────────────────────────────────────
# VAULT_ENVIRONMENT: "cloud" | "local" | "both" (default for single-machine dev)
VAULT_ENVIRONMENT = os.environ.get("VAULT_ENVIRONMENT", "both")
POLL_INTERVAL = int(os.environ.get("ORCHESTRATOR_POLL_SECONDS", "30"))
CEO_BRIEF_DAY = os.environ.get("CEO_BRIEF_DAY", "sunday").lower()
CEO_BRIEF_HOUR = int(os.environ.get("CEO_BRIEF_HOUR", "9"))
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))
QUARANTINE_ON_FAILURE = os.environ.get("QUARANTINE_ON_FAILURE", "true").lower() == "true"

# ── ZONE-AWARE WATCHER SETS ──────────────────────────────────────────────
# Cloud watchers: triage-oriented, no secrets needed
CLOUD_WATCHERS = {
    "gmail_watcher":        ("gmail_watcher.py",        []),
    "needs_action_watcher": ("needs_action_watcher.py", []),
    "facebook_watcher":     ("facebook_watcher.py",     []),
    "instagram_watcher":    ("instagram_watcher.py",    []),
    "x_watcher":            ("x_watcher.py",            []),
    "scheduler":            ("scheduler.py",            []),
}

# Local watchers: execution-oriented, holds secrets
LOCAL_WATCHERS = {
    "hitl_watcher":         ("hitl_watcher.py",         []),
    "needs_action_watcher": ("needs_action_watcher.py", []),
    "scheduler":            ("scheduler.py",            []),
}

# Platinum sub-orchestrators (launched as managed processes)
CLOUD_ORCHESTRATOR = ("orchestrator_cloud.py", [])
LOCAL_ORCHESTRATOR = ("orchestrator_local.py", [])


def get_managed_watchers(zone):
    """Return the watcher set appropriate for the current zone."""
    if zone == "cloud":
        return CLOUD_WATCHERS
    elif zone == "local":
        return LOCAL_WATCHERS
    else:  # "both"
        merged = {}
        merged.update(CLOUD_WATCHERS)
        merged.update(LOCAL_WATCHERS)
        return merged


# ── LOGGING ───────────────────────────────────────────────────────────────
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
    return logging.getLogger("Orchestrator")


# ── PID MANAGEMENT ────────────────────────────────────────────────────────
def load_pids():
    if PID_FILE.exists():
        try:
            data = json.loads(PID_FILE.read_text(encoding="utf-8"))
            return {k: int(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {}


def save_pids(pids):
    try:
        PID_FILE.write_text(json.dumps(pids, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Failed to save PID file: {exc}")


def is_process_alive(pid):
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# ── WATCHER SUPERVISION ──────────────────────────────────────────────────
_child_procs: dict[str, subprocess.Popen] = {}


def start_watcher(name, script, extra_args, dry_run=False):
    script_path = WATCHER_DIR / script
    if not script_path.exists():
        logger.error(f"[{name}] Script not found: {script_path}")
        return None

    cmd = [sys.executable, str(script_path)] + extra_args

    if dry_run:
        logger.info(f"[DRY RUN] Would start {name}: {' '.join(cmd)}")
        return None

    try:
        proc = subprocess.Popen(
            cmd, cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _child_procs[name] = proc
        logger.info(f"[{name}] Started (PID {proc.pid})")
        return proc.pid
    except OSError as exc:
        logger.error(f"[{name}] Failed to start: {exc}")
        return None


def ensure_watchers(pids, zone, dry_run=False):
    """Check every zone-appropriate watcher; restart any that have died."""
    watchers = get_managed_watchers(zone)
    for name, (script, args) in watchers.items():
        pid = pids.get(name)
        alive = is_process_alive(pid)

        if alive:
            logger.debug(f"[{name}] OK (PID {pid})")
            continue

        if pid:
            logger.warning(f"[{name}] Dead (was PID {pid}), restarting...")
        else:
            logger.info(f"[{name}] Not running, starting...")

        new_pid = start_watcher(name, script, args, dry_run=dry_run)
        if new_pid:
            pids[name] = new_pid

    save_pids(pids)


def ensure_sub_orchestrator(pids, zone, dry_run=False):
    """Launch the zone-specific sub-orchestrator (cloud or local)."""
    targets = []
    if zone in ("cloud", "both"):
        targets.append(("orchestrator_cloud", *CLOUD_ORCHESTRATOR))
    if zone in ("local", "both"):
        targets.append(("orchestrator_local", *LOCAL_ORCHESTRATOR))

    for name, script, args in targets:
        pid = pids.get(name)
        if is_process_alive(pid):
            logger.debug(f"[{name}] OK (PID {pid})")
            continue

        if pid:
            logger.warning(f"[{name}] Dead (was PID {pid}), restarting...")
        else:
            logger.info(f"[{name}] Not running, starting...")

        new_pid = start_watcher(name, script, args, dry_run=dry_run)
        if new_pid:
            pids[name] = new_pid

    save_pids(pids)


def stop_all_watchers(pids):
    for name, proc in _child_procs.items():
        if proc.poll() is None:
            logger.info(f"[{name}] Stopping (PID {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.warning(f"[{name}] Force-killed")
    _child_procs.clear()
    pids.clear()
    save_pids(pids)


# ── CLAIM-BY-MOVE: DOUBLE-WORK PREVENTION ────────────────────────────────
def check_claim_conflicts():
    """Detect files claimed by both cloud and local (shouldn't happen)."""
    conflicts = []
    for cloud_file in IN_PROGRESS_CLOUD.glob("*.md") if IN_PROGRESS_CLOUD.exists() else []:
        local_match = IN_PROGRESS_LOCAL / cloud_file.name
        if local_match.exists():
            conflicts.append(cloud_file.name)
            logger.error(f"[CONFLICT] {cloud_file.name} claimed by BOTH cloud and local!")

    if conflicts and HAS_AUDIT_LOGGER:
        log_action(
            action_type="orchestrator.claim_conflict",
            actor="orchestrator",
            target="claim_check",
            parameters={"conflicts": conflicts},
            result="conflict_detected",
            severity="ERROR",
        )
    return conflicts


def check_delegation_queues():
    """Log delegation queue depths for monitoring."""
    queues = {
        "Needs_Action/cloud": len(list(NEEDS_ACTION_CLOUD.glob("*.md"))) if NEEDS_ACTION_CLOUD.exists() else 0,
        "Needs_Action/local": len(list(NEEDS_ACTION_LOCAL.glob("*.md"))) if NEEDS_ACTION_LOCAL.exists() else 0,
        "Pending_Approval":   len(list(PENDING_APPROVAL.glob("*.md"))) if PENDING_APPROVAL.exists() else 0,
        "Approved":           len(list(APPROVED_DIR.glob("*.md"))) if APPROVED_DIR.exists() else 0,
        "Updates":            len(list(UPDATES_DIR.glob("*.md"))) if UPDATES_DIR.exists() else 0,
        "Plans/cloud":        len(list(PLANS_CLOUD.glob("*.md"))) if PLANS_CLOUD.exists() else 0,
        "In_Progress/cloud":  len(list(IN_PROGRESS_CLOUD.glob("*.md"))) if IN_PROGRESS_CLOUD.exists() else 0,
        "In_Progress/local":  len(list(IN_PROGRESS_LOCAL.glob("*.md"))) if IN_PROGRESS_LOCAL.exists() else 0,
    }

    total = sum(queues.values())
    if total > 0:
        logger.info(f"[QUEUES] {queues}")
    return queues


# ── CRON JOBS ─────────────────────────────────────────────────────────────
def job_dashboard_refresh(dry_run=False):
    """Daily 08:00 — trigger a Ralph loop to refresh the dashboard."""
    logger.info("[CRON] Dashboard refresh triggered")

    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="cron.dashboard_refresh",
            actor="orchestrator", target="dashboard.md",
            parameters={"dry_run": dry_run}, result="triggered", severity="INFO",
        )

    cmd = (
        'claude "Read data/Dashboard.md, count files in every data/ subdirectory, '
        'and update Dashboard.md with accurate counts and a timestamped activity entry. '
        'Use skill-dashboard-updater." '
        '--max-turns 5'
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would run: {cmd}")
        return

    try:
        subprocess.Popen(
            cmd, shell=True, cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        logger.info("[CRON] Dashboard refresh agent launched")
    except OSError as exc:
        logger.error(f"[CRON] Dashboard refresh failed to start: {exc}")
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="cron.dashboard_refresh", actor="orchestrator",
                target="dashboard.md", error=exc, severity="ERROR",
            )


def job_weekly_audit(dry_run=False):
    """Weekly CEO_BRIEF_DAY at CEO_BRIEF_HOUR — trigger audit + CEO brief."""
    logger.info("[CRON] Weekly audit + CEO brief triggered")
    today = datetime.now().strftime("%Y%m%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Platinum: route audit task to the appropriate zone
    if VAULT_ENVIRONMENT == "cloud":
        target_dir = NEEDS_ACTION_CLOUD
    else:
        target_dir = NEEDS_ACTION_LOCAL if NEEDS_ACTION_LOCAL.exists() else NEEDS_ACTION_DIR

    audit_filename = f"AUDIT_WEEKLY_{today}.md"
    audit_path = target_dir / audit_filename

    content = f"""---
type: audit_task
action: weekly_audit
status: pending
priority: high
created: {now_iso}
scheduled_by: orchestrator
zone: {VAULT_ENVIRONMENT}
skills_needed:
  - skill-weekly-audit
  - skill-ceo-briefing
  - skill-odoo-mcp
  - skill-social-integrator
approval_required: false
---

## Weekly Audit + CEO Briefing Request

Run skill-weekly-audit to generate AUDIT_{today}.md in data/Briefings/.
Then run skill-ceo-briefing to generate CEO_BRIEF_{today}.md.

### Data Sources
- data/Done/ — completed tasks (past 7 days)
- data/Logs/ — audit log entries (past 7 days)
- data/Accounting/ — Odoo financial records
- data/Quarantine/ — error recovery items
- Odoo MCP — get_account_summary, get_invoices
- Social MCP — get_fb_feed_summary, get_ig_media_summary, get_x_timeline_summary

### Generated
Auto-created by orchestrator.py on {now_iso} (zone: {VAULT_ENVIRONMENT}).
"""

    if dry_run:
        logger.info(f"[DRY RUN] Would create {audit_filename}")
        return

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(content, encoding="utf-8")
        logger.info(f"[CRON] Created weekly audit task: {audit_filename} in {target_dir.name}")
    except OSError as exc:
        logger.error(f"[CRON] Failed to create weekly audit task: {exc}")
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="cron.weekly_audit", actor="orchestrator",
                target=audit_filename, error=exc, severity="ERROR",
            )


def job_error_monitoring(dry_run=False):
    """Check quarantine directory for items needing attention."""
    if dry_run:
        logger.debug("[DRY RUN] Would check quarantine directory")
        return

    try:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        quarantined = list(QUARANTINE_DIR.glob("*.md"))
        if quarantined:
            logger.warning(f"[MONITOR] {len(quarantined)} items in quarantine")
            if HAS_AUDIT_LOGGER:
                log_action(
                    action_type="cron.error_monitoring", actor="orchestrator",
                    target="quarantine",
                    parameters={"item_count": len(quarantined), "items": [f.name for f in quarantined]},
                    result="items_found", severity="WARN",
                )
        else:
            logger.debug("[MONITOR] Quarantine is empty")
    except OSError as exc:
        logger.error(f"[MONITOR] Failed to check quarantine: {exc}")


def job_claim_check(dry_run=False):
    """Periodic check for claim-by-move conflicts between zones."""
    if dry_run:
        return
    conflicts = check_claim_conflicts()
    if conflicts:
        logger.error(f"[CLAIM CHECK] {len(conflicts)} double-claimed files detected!")
    check_delegation_queues()


def configure_schedules(dry_run=False):
    """Wire up all cron jobs (Platinum)."""
    # Daily dashboard refresh
    schedule.every().day.at("08:00").do(job_dashboard_refresh, dry_run=dry_run)

    # Weekly audit + CEO briefing
    audit_time = f"{CEO_BRIEF_HOUR:02d}:00"
    getattr(schedule.every(), CEO_BRIEF_DAY).at(audit_time).do(
        job_weekly_audit, dry_run=dry_run
    )

    # Error monitoring every 15 minutes
    schedule.every(15).minutes.do(job_error_monitoring, dry_run=dry_run)

    # Platinum: claim conflict check every 5 minutes
    schedule.every(5).minutes.do(job_claim_check, dry_run=dry_run)

    logger.info(
        f"Schedules configured: dashboard daily@08:00, "
        f"weekly audit {CEO_BRIEF_DAY}@{audit_time}, "
        f"error monitoring every 15min, claim check every 5min"
    )


# ── STATUS REPORT ─────────────────────────────────────────────────────────
def print_status(zone):
    pids = load_pids()
    watchers = get_managed_watchers(zone)
    print(f"Orchestrator — Platinum Tier (zone: {zone})")
    print("=" * 60)
    print("  Watchers:")
    for name in watchers:
        pid = pids.get(name)
        alive = is_process_alive(pid) if pid else False
        status_str = f"RUNNING (PID {pid})" if alive else "STOPPED"
        print(f"    {name:25s} {status_str}")

    print("  Sub-orchestrators:")
    for name in ("orchestrator_cloud", "orchestrator_local"):
        if zone == "cloud" and name == "orchestrator_local":
            continue
        if zone == "local" and name == "orchestrator_cloud":
            continue
        pid = pids.get(name)
        alive = is_process_alive(pid) if pid else False
        status_str = f"RUNNING (PID {pid})" if alive else "STOPPED"
        print(f"    {name:25s} {status_str}")

    print("  Delegation queues:")
    queues = check_delegation_queues()
    for q_name, count in queues.items():
        print(f"    {q_name:25s} {count} files")

    conflicts = check_claim_conflicts()
    if conflicts:
        print(f"\n  !! CONFLICTS: {conflicts}")

    print("=" * 60)
    print(f"  PID file: {PID_FILE}")
    print(f"  Log file: {LOG_FILE}")
    print(f"  Zone: {zone}")


# ── ENSURE DIRECTORIES ───────────────────────────────────────────────────
def ensure_directories():
    """Create all Platinum data directories if they don't exist."""
    for d in (NEEDS_ACTION_CLOUD, NEEDS_ACTION_LOCAL, IN_PROGRESS_CLOUD,
              IN_PROGRESS_LOCAL, PLANS_CLOUD, PENDING_APPROVAL, APPROVED_DIR,
              UPDATES_DIR, DONE_CLOUD, DONE_LOCAL, QUARANTINE_DIR,
              BRIEFINGS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    global logger

    parser = argparse.ArgumentParser(
        description="Platinum Tier orchestrator — zone-aware supervisor with cloud/local split"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Log actions without starting processes or writing files")
    parser.add_argument("--no-watchers", action="store_true",
                        help="Skip watcher supervision; run cron jobs only")
    parser.add_argument("--status", action="store_true",
                        help="Print health report and exit")
    parser.add_argument("--zone", choices=["cloud", "local", "both"],
                        default=VAULT_ENVIRONMENT,
                        help=f"Override zone (default: {VAULT_ENVIRONMENT} from VAULT_ENVIRONMENT)")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help=f"Main loop poll interval in seconds (default: {POLL_INTERVAL})")
    args = parser.parse_args()

    zone = args.zone
    logger = setup_logging()

    if args.status:
        print_status(zone)
        return

    mode = "DRY RUN" if args.dry_run else "ACTIVE"
    logger.info(f"Orchestrator starting ({mode}, zone={zone})")
    logger.info(f"Vault directory: {VAULT_DIR}")
    logger.info(f"Poll interval: {args.interval}s")

    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="orchestrator.start", actor="orchestrator",
            target="system",
            parameters={"mode": mode, "zone": zone, "poll_interval": args.interval},
            result="success", severity="INFO",
        )

    # Create all directories
    ensure_directories()

    # Load existing PIDs
    pids = load_pids()

    # Configure cron jobs
    configure_schedules(dry_run=args.dry_run)

    # Initial watcher + sub-orchestrator launch
    if not args.no_watchers:
        ensure_watchers(pids, zone, dry_run=args.dry_run)
        ensure_sub_orchestrator(pids, zone, dry_run=args.dry_run)

    # Main loop
    try:
        loop_count = 0
        while True:
            schedule.run_pending()

            if not args.no_watchers and not args.dry_run:
                ensure_watchers(pids, zone, dry_run=False)
                ensure_sub_orchestrator(pids, zone, dry_run=False)

            loop_count += 1
            if loop_count % 100 == 0 and HAS_AUDIT_LOGGER:
                log_action(
                    action_type="orchestrator.health_check", actor="orchestrator",
                    target="system",
                    parameters={"loop_count": loop_count, "zone": zone},
                    result="success", severity="INFO",
                )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user (Ctrl+C)")
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="orchestrator.shutdown", actor="orchestrator",
                target="system", parameters={"reason": "user_interrupt"},
                result="success", severity="INFO",
            )
    finally:
        if not args.dry_run and not args.no_watchers:
            stop_all_watchers(pids)
        if PID_FILE.exists():
            try:
                PID_FILE.unlink()
            except OSError:
                pass
        logger.info("Orchestrator shut down")


if __name__ == "__main__":
    main()
