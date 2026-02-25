#!/usr/bin/env python3
"""
Orchestrator (Gold Tier)

Central process supervisor that:
  1. Ensures all watcher subprocesses stay alive (PID check + restart)
  2. Runs scheduled cron-like jobs via the `schedule` library:
     - Daily 08:00  — Ralph loop for dashboard refresh
     - Weekly (CEO_BRIEF_DAY) — Weekly audit + CEO briefing
  3. Monitors error recovery and quarantine status
  4. Manages Gold-tier MCP server health checks
  5. Exposes --dry-run, --no-watchers, and --status flags

Run:
  python orchestrator.py                   # normal mode
  python orchestrator.py --dry-run         # log only, no subprocesses or files
  python orchestrator.py --status          # print watcher health and exit
  python orchestrator.py --no-watchers     # cron jobs only, skip watcher management

Background (Windows):
  start /B python orchestrator.py > data/Logs/orchestrator.log 2>&1

Background (Unix / Git Bash):
  nohup python orchestrator.py > data/Logs/orchestrator.log 2>&1 &
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
PLANS_DIR = VAULT_DIR / "data" / "Plans"
LOG_FILE = LOGS_DIR / "orchestrator.log"
PID_FILE = VAULT_DIR / ".orchestrator.pids.json"

# ── AUDIT LOGGER INTEGRATION (Gold Tier) ─────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

POLL_INTERVAL = int(os.environ.get("ORCHESTRATOR_POLL_SECONDS", "30"))

# Gold Tier env vars
CEO_BRIEF_DAY = os.environ.get("CEO_BRIEF_DAY", "sunday").lower()
CEO_BRIEF_HOUR = int(os.environ.get("CEO_BRIEF_HOUR", "9"))
MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))
QUARANTINE_ON_FAILURE = os.environ.get("QUARANTINE_ON_FAILURE", "true").lower() == "true"

BRIEFINGS_DIR = VAULT_DIR / "data" / "Briefings"
QUARANTINE_DIR = VAULT_DIR / "data" / "Quarantine"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"

# Watchers to supervise: name -> (script, extra_args)
# Each is started as a subprocess; orchestrator restarts if the process dies.
MANAGED_WATCHERS = {
    "gmail_watcher":        ("gmail_watcher.py",        []),
    "needs_action_watcher": ("needs_action_watcher.py", []),
    "hitl_watcher":         ("hitl_watcher.py",         []),
    "scheduler":            ("scheduler.py",            []),
    # Gold Tier: social media watchers
    "facebook_watcher":     ("facebook_watcher.py",     []),
    "instagram_watcher":    ("instagram_watcher.py",    []),
    "x_watcher":            ("x_watcher.py",            []),
}

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
    """Load saved PID map from disk."""
    if PID_FILE.exists():
        try:
            data = json.loads(PID_FILE.read_text(encoding="utf-8"))
            return {k: int(v) for k, v in data.items()}
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {}


def save_pids(pids):
    """Persist current PID map."""
    try:
        PID_FILE.write_text(json.dumps(pids, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning(f"Failed to save PID file: {exc}")


def is_process_alive(pid):
    """Check whether a PID is still running (cross-platform)."""
    if pid is None or pid <= 0:
        return False
    try:
        # On Unix os.kill(pid, 0) checks existence; on Windows it raises
        # OSError if the process doesn't exist.
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# ── WATCHER SUPERVISION ──────────────────────────────────────────────────
# Store Popen objects so we can terminate cleanly on shutdown.
_child_procs: dict[str, subprocess.Popen] = {}


def start_watcher(name, script, extra_args, dry_run=False):
    """Launch a watcher subprocess and return its PID."""
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
            cmd,
            cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _child_procs[name] = proc
        logger.info(f"[{name}] Started (PID {proc.pid})")
        return proc.pid
    except OSError as exc:
        logger.error(f"[{name}] Failed to start: {exc}")
        return None


def ensure_watchers(pids, dry_run=False):
    """Check every managed watcher; restart any that have died."""
    for name, (script, args) in MANAGED_WATCHERS.items():
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


def stop_all_watchers(pids):
    """Gracefully terminate every managed subprocess."""
    for name, proc in _child_procs.items():
        if proc.poll() is None:  # still running
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


# ── CRON JOBS ─────────────────────────────────────────────────────────────
def job_dashboard_refresh(dry_run=False):
    """Daily 08:00 — trigger a Ralph loop to refresh the dashboard."""
    logger.info("[CRON] Dashboard refresh triggered")

    # Gold Tier: log cron job start to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="cron.dashboard_refresh",
            actor="orchestrator",
            target="dashboard.md",
            parameters={"dry_run": dry_run},
            result="success",
            severity="INFO",
        )

    cmd = (
        'claude "Read data/Dashboard.md, count files in every data/ subdirectory, '
        'and update Dashboard.md with accurate counts and a timestamped activity entry. '
        'Use skill-dashboard-updater." '
        '--max-turns 5'
    )

    if dry_run:
        logger.info(f"[DRY RUN] Would run: {cmd}")

        # Gold Tier: log dry-run to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="cron.dashboard_refresh",
                actor="orchestrator",
                target="dashboard.md",
                parameters={"dry_run": True, "cmd": cmd},
                result="success",
                severity="INFO",
            )
        return

    try:
        subprocess.Popen(
            cmd,
            shell=True,
            cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("[CRON] Dashboard refresh agent launched")

        # Gold Tier: log successful launch to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="cron.dashboard_refresh",
                actor="orchestrator",
                target="dashboard.md",
                parameters={"cmd": cmd},
                result="launched",
                severity="INFO",
            )
    except OSError as exc:
        logger.error(f"[CRON] Dashboard refresh failed to start: {exc}")

        # Gold Tier: log error to audit log
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="cron.dashboard_refresh",
                actor="orchestrator",
                target="dashboard.md",
                error=exc,
                parameters={"cmd": cmd},
                severity="ERROR",
            )


def job_weekly_audit(dry_run=False):
    """Weekly (CEO_BRIEF_DAY at CEO_BRIEF_HOUR) — trigger audit + CEO brief."""
    logger.info("[CRON] Weekly audit + CEO brief triggered")

    # Gold Tier: log cron job start to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="cron.weekly_audit",
            actor="orchestrator",
            target="audit_task",
            parameters={"dry_run": dry_run},
            result="success",
            severity="INFO",
        )

    today = datetime.now().strftime("%Y%m%d")
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create audit task in Needs_Action for the agent to process
    audit_filename = f"AUDIT_WEEKLY_{today}.md"
    audit_path = NEEDS_ACTION_DIR / audit_filename

    content = f"""---
type: audit_task
action: weekly_audit
status: pending
priority: high
created: {now_iso}
scheduled_by: orchestrator
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
Auto-created by orchestrator.py on {now_iso}.
"""

    if dry_run:
        logger.info(f"[DRY RUN] Would create {audit_filename} in data/Needs_Action/")

        # Gold Tier: log dry-run to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="cron.weekly_audit",
                actor="orchestrator",
                target=audit_filename,
                parameters={"dry_run": True, "filename": audit_filename},
                result="success",
                severity="INFO",
            )
        return

    try:
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
        audit_path.write_text(content, encoding="utf-8")
        logger.info(f"[CRON] Created weekly audit task: {audit_filename}")

        # Gold Tier: log successful creation to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="cron.weekly_audit",
                actor="orchestrator",
                target=audit_filename,
                parameters={"filename": audit_filename},
                result="created",
                severity="INFO",
            )
    except OSError as exc:
        logger.error(f"[CRON] Failed to create weekly audit task: {exc}")

        # Gold Tier: log error to audit log
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="cron.weekly_audit",
                actor="orchestrator",
                target=audit_filename,
                error=exc,
                parameters={"filename": audit_filename},
                severity="ERROR",
            )


def job_error_monitoring(dry_run=False):
    """Check quarantine directory for items needing attention."""

    # Gold Tier: log cron job start to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="cron.error_monitoring",
            actor="orchestrator",
            target="quarantine",
            parameters={"dry_run": dry_run},
            result="success",
            severity="INFO",
        )

    if dry_run:
        logger.debug("[DRY RUN] Would check quarantine directory")

        # Gold Tier: log dry-run to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="cron.error_monitoring",
                actor="orchestrator",
                target="quarantine",
                parameters={"dry_run": True},
                result="success",
                severity="INFO",
            )
        return

    try:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        quarantined = list(QUARANTINE_DIR.glob("*.md"))
        if quarantined:
            logger.warning(f"[MONITOR] {len(quarantined)} items in quarantine")

            # Gold Tier: log quarantine status to audit log
            if HAS_AUDIT_LOGGER:
                log_action(
                    action_type="cron.error_monitoring",
                    actor="orchestrator",
                    target="quarantine",
                    parameters={"item_count": len(quarantined), "items": [f.name for f in quarantined]},
                    result="items_found",
                    severity="WARN",
                )
        else:
            logger.debug("[MONITOR] Quarantine is empty")

            # Gold Tier: log empty quarantine to audit log
            if HAS_AUDIT_LOGGER:
                log_action(
                    action_type="cron.error_monitoring",
                    actor="orchestrator",
                    target="quarantine",
                    parameters={"item_count": 0},
                    result="empty",
                    severity="INFO",
                )
    except OSError as exc:
        logger.error(f"[MONITOR] Failed to check quarantine: {exc}")

        # Gold Tier: log error to audit log
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="cron.error_monitoring",
                actor="orchestrator",
                target="quarantine",
                error=exc,
                parameters={"error": str(exc)},
                severity="ERROR",
            )


def configure_schedules(dry_run=False):
    """Wire up all cron jobs (Gold Tier)."""
    # Daily dashboard refresh
    schedule.every().day.at("08:00").do(job_dashboard_refresh, dry_run=dry_run)

    # Weekly audit + CEO briefing (configurable day)
    audit_time = f"{CEO_BRIEF_HOUR:02d}:00"
    getattr(schedule.every(), CEO_BRIEF_DAY).at(audit_time).do(
        job_weekly_audit, dry_run=dry_run
    )

    # Error monitoring every 15 minutes
    schedule.every(15).minutes.do(job_error_monitoring, dry_run=dry_run)

    logger.info(
        f"Schedules configured: dashboard daily@08:00, "
        f"weekly audit {CEO_BRIEF_DAY}@{audit_time}, "
        f"error monitoring every 15min"
    )


# ── STATUS REPORT ─────────────────────────────────────────────────────────
def print_status():
    """Print watcher health and exit."""
    pids = load_pids()
    print("Orchestrator — Watcher Status")
    print("=" * 50)
    for name in MANAGED_WATCHERS:
        pid = pids.get(name)
        alive = is_process_alive(pid) if pid else False
        status = f"RUNNING (PID {pid})" if alive else "STOPPED"
        print(f"  {name:25s} {status}")
    print("=" * 50)
    print(f"  PID file: {PID_FILE}")
    print(f"  Log file: {LOG_FILE}")


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    global logger

    parser = argparse.ArgumentParser(
        description="Gold Tier orchestrator — supervises watchers, runs cron jobs, monitors errors"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log actions without starting processes or writing files",
    )
    parser.add_argument(
        "--no-watchers", action="store_true",
        help="Skip watcher supervision; run cron jobs only",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print watcher health report and exit",
    )
    parser.add_argument(
        "--interval", type=int, default=POLL_INTERVAL,
        help=f"Main loop poll interval in seconds (default: {POLL_INTERVAL})",
    )
    args = parser.parse_args()

    logger = setup_logging()

    # Quick status check
    if args.status:
        print_status()
        return

    mode = "DRY RUN" if args.dry_run else "ACTIVE"
    logger.info(f"Orchestrator starting ({mode})")
    logger.info(f"Vault directory: {VAULT_DIR}")
    logger.info(f"Poll interval: {args.interval}s")

    # Gold Tier: log orchestrator startup to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="orchestrator.start",
            actor="orchestrator",
            target="system",
            parameters={"mode": mode, "poll_interval": args.interval},
            result="success",
            severity="INFO",
        )

    # Load existing PIDs (from a previous run that may have crashed)
    pids = load_pids()

    # Configure cron jobs
    configure_schedules(dry_run=args.dry_run)

    # Initial watcher launch
    if not args.no_watchers:
        ensure_watchers(pids, dry_run=args.dry_run)

    # Main loop
    try:
        loop_count = 0
        while True:
            # Run any pending scheduled jobs
            schedule.run_pending()

            # Ensure watchers are alive
            if not args.no_watchers and not args.dry_run:
                ensure_watchers(pids, dry_run=False)

            loop_count += 1
            # Log health check periodically
            if loop_count % 100 == 0 and HAS_AUDIT_LOGGER:  # Every ~50 minutes at 30s interval
                log_action(
                    action_type="orchestrator.health_check",
                    actor="orchestrator",
                    target="system",
                    parameters={"loop_count": loop_count, "poll_interval": args.interval},
                    result="success",
                    severity="INFO",
                )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user (Ctrl+C)")

        # Gold Tier: log orchestrator shutdown to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="orchestrator.shutdown",
                actor="orchestrator",
                target="system",
                parameters={"reason": "user_interrupt"},
                result="success",
                severity="INFO",
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

        # Gold Tier: log final shutdown to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="orchestrator.shutdown_complete",
                actor="orchestrator",
                target="system",
                parameters={"final": True},
                result="success",
                severity="INFO",
            )


if __name__ == "__main__":
    main()
