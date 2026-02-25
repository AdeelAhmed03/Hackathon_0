#!/usr/bin/env python3
"""
Orchestrator (Silver Tier)

Central process supervisor that:
  1. Ensures all watcher subprocesses stay alive (PID check + restart)
  2. Runs scheduled cron-like jobs via the `schedule` library:
     - Daily 08:00  — Ralph loop for dashboard refresh
     - Sunday 09:00 — CEO weekly brief draft in data/Plans/
  3. Exposes --dry-run, --no-watchers, and --status flags

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

POLL_INTERVAL = int(os.environ.get("ORCHESTRATOR_POLL_SECONDS", "30"))

# Watchers to supervise: name -> (script, extra_args)
# Each is started as a subprocess; orchestrator restarts if the process dies.
MANAGED_WATCHERS = {
    "gmail_watcher":        ("gmail_watcher.py",        []),
    "needs_action_watcher": ("needs_action_watcher.py", []),
    "hitl_watcher":         ("hitl_watcher.py",         []),
    "scheduler":            ("scheduler.py",            []),
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
            cmd,
            shell=True,
            cwd=str(VAULT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("[CRON] Dashboard refresh agent launched")
    except OSError as exc:
        logger.error(f"[CRON] Dashboard refresh failed to start: {exc}")


def job_ceo_brief(dry_run=False):
    """Weekly Sunday 09:00 — generate a CEO brief draft in data/Plans/."""
    logger.info("[CRON] Weekly CEO brief triggered")

    today = datetime.now().strftime("%Y%m%d")
    filename = f"CEO_BRIEF_{today}.md"
    file_path = PLANS_DIR / filename
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content = f"""---
type: plan
plan_id: CEO_BRIEF_{today}
status: draft
created: {now_iso}
skills_needed:
  - skill-dashboard-updater
  - skill-logger
approval_required: false
---

## CEO Weekly Brief — {datetime.now().strftime("%B %d, %Y")}

### Vault Metrics (to be filled by agent)
- Tasks completed this week: _pending_
- Emails processed: _pending_
- Approvals granted / rejected: _pending_
- LinkedIn posts published: _pending_

### Key Highlights
- [ ] Summarise top 3 completed tasks from data/Done/ this week
- [ ] Flag any items stuck in Pending_Approval/ > 48 hours
- [ ] Note any watcher downtime from data/Logs/

### Recommendations
- [ ] Items to prioritise next week
- [ ] Process improvements identified

### Generated
Auto-created by orchestrator.py scheduler on {now_iso}.
Populate via: `claude "Fill CEO_BRIEF_{today}.md using data/Done/ and data/Logs/ from the past 7 days."`
"""

    if dry_run:
        logger.info(f"[DRY RUN] Would create {filename} in data/Plans/")
        return

    try:
        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"[CRON] Created CEO brief draft: {filename}")
    except OSError as exc:
        logger.error(f"[CRON] Failed to create CEO brief: {exc}")


def configure_schedules(dry_run=False):
    """Wire up all cron jobs."""
    schedule.every().day.at("08:00").do(job_dashboard_refresh, dry_run=dry_run)
    schedule.every().sunday.at("09:00").do(job_ceo_brief, dry_run=dry_run)
    logger.info("Schedules configured: dashboard refresh daily@08:00, CEO brief sunday@09:00")


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
        description="Silver Tier orchestrator — supervises watchers and runs cron jobs"
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

    # Load existing PIDs (from a previous run that may have crashed)
    pids = load_pids()

    # Configure cron jobs
    configure_schedules(dry_run=args.dry_run)

    # Initial watcher launch
    if not args.no_watchers:
        ensure_watchers(pids, dry_run=args.dry_run)

    # Main loop
    try:
        while True:
            # Run any pending scheduled jobs
            schedule.run_pending()

            # Ensure watchers are alive
            if not args.no_watchers and not args.dry_run:
                ensure_watchers(pids, dry_run=False)

            time.sleep(args.interval)

    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user (Ctrl+C)")
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
