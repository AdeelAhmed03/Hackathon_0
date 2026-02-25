#!/usr/bin/env python3
"""
Scheduler (Silver Tier)

Time-based scheduler that creates task files in data/Needs_Action/ when
configured schedules fire. Uses the `schedule` library for job definitions
and a polling loop to check due jobs.

NOT a watchdog watcher — this is a time-driven loop.
Created task files are picked up by needs_action_watcher.py for agent processing.
"""
import json
import logging
import sys
import os
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import schedule
except ImportError:
    print("Error: 'schedule' package not installed. Run: pip install schedule")
    sys.exit(1)

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; env vars may be set externally

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "scheduler.log"
STATE_FILE = LOGS_DIR / "scheduler_state.json"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"
LOCK_FILE = VAULT_DIR / ".scheduler_running.lock"

DEFAULT_CHECK_INTERVAL = int(os.environ.get("SCHEDULER_CHECK_INTERVAL_SECONDS", "60"))
LINKEDIN_POST_SCHEDULE = os.environ.get("LINKEDIN_POST_SCHEDULE", "09:00")
DRY_RUN_ENV = os.environ.get("DRY_RUN", "false").lower() == "true"


# ── LOGGING SETUP ─────────────────────────────────────────────────────────
def setup_logging():
    """Configure logging to both file and stdout."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("Scheduler")


# ── STATE MANAGEMENT ──────────────────────────────────────────────────────
def load_state():
    """Load scheduler state from JSON file."""
    if STATE_FILE.exists():
        try:
            content = STATE_FILE.read_text(encoding="utf-8").strip()
            if content:
                return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"State file corrupt or unreadable, recreating: {e}")
    return {"last_triggers": {}, "last_check": None}


def save_state(state):
    """Save scheduler state to JSON file."""
    try:
        state["last_check"] = datetime.now(timezone.utc).isoformat()
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error(f"Failed to save state: {e}")


def was_triggered_today(state, task_type):
    """Check if a task type has already been triggered today."""
    today = datetime.now().strftime("%Y-%m-%d")
    last_trigger = state.get("last_triggers", {}).get(task_type)
    return last_trigger == today


def mark_triggered(state, task_type):
    """Mark a task type as triggered for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    if "last_triggers" not in state:
        state["last_triggers"] = {}
    state["last_triggers"][task_type] = today
    save_state(state)


# ── TASK FILE CREATION ────────────────────────────────────────────────────
def create_task_file(task_type, description, details, dry_run=False):
    """Create a scheduled task file in data/Needs_Action/."""
    today = datetime.now().strftime("%Y%m%d")
    filename = f"SCHEDULED_{task_type}_{today}.md"
    file_path = NEEDS_ACTION_DIR / filename

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content = f"""---
type: scheduled_task
task_type: {task_type}
status: pending
scheduled_by: scheduler
scheduled_time: {now_iso}
created: {now_iso}
---

## Scheduled Task: {description}

This task was automatically created by the scheduler.

{details}
"""

    if dry_run:
        logger.info(f"[DRY RUN] Would create task file: {filename}")
        logger.info(f"[DRY RUN] Content preview: {content[:200]}...")
        return True

    try:
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Created scheduled task file: {filename}")
        return True
    except OSError as e:
        logger.error(f"Failed to create task file {filename}: {e}")
        return False


# ── SCHEDULED JOBS ────────────────────────────────────────────────────────
def job_linkedin_draft(state, dry_run=False):
    """Create a LinkedIn draft generation task."""
    task_type = "linkedin_draft"

    if was_triggered_today(state, task_type):
        logger.info(f"Dedup: {task_type} already triggered today, skipping")
        return

    logger.info(f"Schedule fired: {task_type}")

    success = create_task_file(
        task_type=task_type,
        description="LinkedIn Draft",
        details=(
            "**Action Required:** Generate a LinkedIn post draft for today.\n\n"
            "**Post Type:** thought_leadership\n"
            "**Target:** Professional network update\n\n"
            "Use skill-linkedin-draft to generate the draft content.\n"
            "The draft will require HITL approval before posting."
        ),
        dry_run=dry_run,
    )

    if success and not dry_run:
        mark_triggered(state, task_type)


def force_trigger(task_type, state, dry_run=False):
    """Force-trigger a specific task type, bypassing dedup and time checks."""
    logger.info(f"Force-triggering: {task_type}")

    if task_type == "linkedin_draft":
        # Bypass dedup by not checking was_triggered_today
        success = create_task_file(
            task_type=task_type,
            description="LinkedIn Draft (Force-Triggered)",
            details=(
                "**Action Required:** Generate a LinkedIn post draft.\n\n"
                "**Post Type:** thought_leadership\n"
                "**Target:** Professional network update\n\n"
                "This task was force-triggered for testing.\n\n"
                "Use skill-linkedin-draft to generate the draft content."
            ),
            dry_run=dry_run,
        )
        if success and not dry_run:
            mark_triggered(state, task_type)
    else:
        logger.error(f"Unknown task type for force-trigger: {task_type}")
        logger.info(f"Available task types: linkedin_draft")


# ── SCHEDULE CONFIGURATION ────────────────────────────────────────────────
def configure_schedules(state, dry_run=False):
    """Set up all scheduled jobs using the schedule library."""
    logger.info(f"Configuring LinkedIn draft schedule at {LINKEDIN_POST_SCHEDULE}")
    schedule.every().day.at(LINKEDIN_POST_SCHEDULE).do(
        job_linkedin_draft, state=state, dry_run=dry_run
    )


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    global logger

    parser = argparse.ArgumentParser(
        description="Time-based scheduler that creates task files in data/Needs_Action/"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without creating files",
    )
    parser.add_argument(
        "--force-trigger",
        type=str,
        metavar="TASK_TYPE",
        help="Bypass dedup and time check, immediately create task (e.g., linkedin_draft)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL,
        help=f"Check interval in seconds (default: {DEFAULT_CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--list-schedules",
        action="store_true",
        help="List configured schedules and exit",
    )

    args = parser.parse_args()

    logger = setup_logging()

    dry_run = args.dry_run or DRY_RUN_ENV

    # Load state
    state = load_state()
    logger.info(f"Loaded scheduler state: {json.dumps(state, indent=2)}")

    # Handle --list-schedules
    if args.list_schedules:
        print("Configured schedules:")
        print(f"  - LinkedIn Draft: daily at {LINKEDIN_POST_SCHEDULE}")
        return 0

    # Handle --force-trigger
    if args.force_trigger:
        force_trigger(args.force_trigger, state, dry_run=dry_run)
        return 0

    # Normal operation: configure schedules and run loop
    configure_schedules(state, dry_run=dry_run)

    mode = "DRY RUN" if dry_run else "ACTIVE"
    logger.info(f"Scheduler started ({mode})")
    logger.info(f"Check interval: {args.interval}s")
    logger.info(f"LinkedIn draft schedule: daily at {LINKEDIN_POST_SCHEDULE}")

    # Create lock file
    if not dry_run:
        try:
            LOCK_FILE.touch()
        except OSError:
            pass

    try:
        while True:
            schedule.run_pending()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    finally:
        if LOCK_FILE.exists():
            try:
                LOCK_FILE.unlink()
            except OSError:
                pass
        save_state(state)
        logger.info("Final state saved")


if __name__ == "__main__":
    main()
