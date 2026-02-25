#!/usr/bin/env python3
"""
Cloud Orchestrator — Platinum Tier

Runs as a 24/7 cloud sub-orchestrator launched by the main orchestrator.py.
Handles the Cloud Executive's core loop:

  1. Triage emails/social → categorise by priority
  2. Generate drafts in Plans/cloud/  (never send/post/pay)
  3. Create approval requests in Pending_Approval/local/
  4. Write dashboard updates to Updates/
  5. Claim-by-move to In_Progress/cloud/ (prevent double-work)
  6. Git sync push after each cycle

Cloud agent NEVER executes sends/posts/payments — draft-only.

Usage:
    python orchestrator_cloud.py                # Start cloud orchestrator
    python orchestrator_cloud.py --status       # Check service status
    python orchestrator_cloud.py --health       # Run health checks
    python orchestrator_cloud.py --sync         # Force Git synchronization
    python orchestrator_cloud.py --dry-run      # Log only, no file moves
"""

import os
import sys
import json
import time
import signal
import subprocess
import threading
import re
from pathlib import Path
from datetime import datetime
import logging
import argparse

try:
    import schedule
except ImportError:
    schedule = None

# A2A Phase 2 — optional direct messaging
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
    from a2a_messaging import A2ANode, A2AMessage, A2A_ENABLED as _A2A_ENABLED
    HAS_A2A = True
except ImportError:
    HAS_A2A = False
    _A2A_ENABLED = False

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
CLOUD_LOG_FILE = LOG_DIR / "cloud_orchestrator.log"

# Platinum directories
NEEDS_ACTION_CLOUD = VAULT_DIR / "data" / "Needs_Action" / "cloud"
IN_PROGRESS_CLOUD = VAULT_DIR / "data" / "In_Progress" / "cloud"
PLANS_CLOUD = VAULT_DIR / "data" / "Plans" / "cloud"
PENDING_APPROVAL = VAULT_DIR / "data" / "Pending_Approval" / "local"
UPDATES_DIR = VAULT_DIR / "data" / "Updates"
DONE_CLOUD = VAULT_DIR / "data" / "Done" / "cloud"
QUARANTINE_DIR = VAULT_DIR / "data" / "Quarantine"

# Ensure directories exist
for _d in (LOG_DIR, NEEDS_ACTION_CLOUD, IN_PROGRESS_CLOUD, PLANS_CLOUD,
           PENDING_APPROVAL, UPDATES_DIR, DONE_CLOUD, QUARANTINE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DRY_RUN = os.environ.get("CLOUD_DRY_RUN", "false").lower() == "true"

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - CloudOrchestrator - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(CLOUD_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("CloudOrchestrator")


# ── YAML FRONTMATTER PARSER ──────────────────────────────────────────────
def parse_frontmatter(text):
    """Parse YAML-ish frontmatter between --- delimiters."""
    meta = {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return meta, text
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    body = text[match.end():].strip()
    return meta, body


# ── PRIORITY CLASSIFIER ──────────────────────────────────────────────────
PRIORITY_KEYWORDS = {
    "urgent": "critical",
    "asap": "critical",
    "invoice": "high",
    "payment": "high",
    "partnership": "high",
    "proposal": "high",
    "meeting": "normal",
    "schedule": "normal",
    "newsletter": "low",
    "unsubscribe": "low",
}


def classify_priority(meta, body):
    """Classify task priority from metadata and body content."""
    # Explicit priority in frontmatter takes precedence
    if meta.get("priority"):
        return meta["priority"]

    combined = (meta.get("subject", "") + " " + body).lower()
    for keyword, priority in PRIORITY_KEYWORDS.items():
        if keyword in combined:
            return priority
    return "normal"


# ── DRAFT GENERATORS ─────────────────────────────────────────────────────
def generate_email_draft(meta, body, task_id):
    """Generate a draft email reply in Plans/cloud/."""
    sender = meta.get("from", meta.get("sender", "unknown@example.com"))
    subject = meta.get("subject", "Re: Your message")
    priority = classify_priority(meta, body)
    now = datetime.now()

    draft_content = f"""---
type: draft
action: reply_email
target: Email
to: {sender}
subject: Re: {subject}
priority: {priority}
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
status: pending_approval
correlation_id: {task_id}
draft_only: true
---

# Draft: Email Reply — {subject}

## Context
- **Original sender**: {sender}
- **Original subject**: {subject}
- **Triage priority**: {priority.title()}

## Draft Reply

Thank you for your email regarding "{subject}". We have reviewed your message and will follow up with a detailed response.

Please allow us to get back to you within the next business day.

Best regards,
AI Employee Vault

## Approval Required
- This draft was generated by the Cloud Executive (draft-only)
- Human approval is required before sending
- Approval file created in: `Pending_Approval/local/`
- To approve: Move approval file to `Approved/`
"""

    draft_file = PLANS_CLOUD / f"DRAFT_email_reply_{task_id}.md"
    draft_file.write_text(draft_content, encoding="utf-8")

    # Create approval request
    approval_content = f"""---
type: approval_request
action: send_email
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
correlation_id: {task_id}
draft_file: DRAFT_email_reply_{task_id}.md
priority: {priority}
---

# Approval Request: Email Reply to {sender}

**Subject**: Re: {subject}
**Priority**: {priority.title()}
**Action**: Send email reply

To approve: move this file to `Approved/`
"""
    approval_file = PENDING_APPROVAL / f"APPROVE_email_{task_id}.md"
    approval_file.write_text(approval_content, encoding="utf-8")

    logger.info(f"[DRAFT] Email reply draft created: {draft_file.name} (priority: {priority})")
    return draft_file.name, approval_file.name


def generate_social_draft(meta, body, task_id, platform="linkedin"):
    """Generate a draft social media post in Plans/cloud/."""
    now = datetime.now()
    priority = classify_priority(meta, body)

    draft_content = f"""---
type: draft
action: {platform}_post
target: {platform.title()}
priority: {priority}
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
status: pending_approval
correlation_id: {task_id}
draft_only: true
---

# Draft: {platform.title()} Post

## Context
- **Platform**: {platform.title()}
- **Post type**: scheduled
- **Triage priority**: {priority.title()}

## Draft Post

{body[:500] if body else 'AI-generated content placeholder — to be filled by agent.'}

## Approval Required
- This draft was generated by the Cloud Executive (draft-only)
- Human approval is required before posting
- Approval file created in: `Pending_Approval/local/`
"""

    draft_file = PLANS_CLOUD / f"DRAFT_{platform}_{task_id}.md"
    draft_file.write_text(draft_content, encoding="utf-8")

    approval_content = f"""---
type: approval_request
action: post_{platform}
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
correlation_id: {task_id}
draft_file: DRAFT_{platform}_{task_id}.md
priority: {priority}
---

# Approval Request: {platform.title()} Post

**Action**: Post to {platform.title()}
**Priority**: {priority.title()}

To approve: move this file to `Approved/`
"""
    approval_file = PENDING_APPROVAL / f"APPROVE_{platform}_{task_id}.md"
    approval_file.write_text(approval_content, encoding="utf-8")

    logger.info(f"[DRAFT] {platform.title()} post draft created: {draft_file.name}")
    return draft_file.name, approval_file.name


def generate_odoo_draft(meta, body, task_id):
    """Generate a draft Odoo invoice in Plans/cloud/ (uses odoo_mcp create_invoice_draft)."""
    now = datetime.now()
    partner = meta.get("partner", meta.get("from", "Unknown Partner"))
    amount = meta.get("amount", "0.00")
    priority = classify_priority(meta, body)

    draft_content = f"""---
type: draft
action: create_invoice
target: Odoo
priority: {priority}
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
status: pending_approval
correlation_id: {task_id}
draft_only: true
partner: {partner}
amount: {amount}
---

# Draft: Odoo Invoice for {partner}

## Invoice Details
- **Partner**: {partner}
- **Amount**: {amount}
- **Priority**: {priority.title()}

## Notes
{body[:300] if body else 'Auto-generated from triage.'}

## Approval Required
- This draft was generated by the Cloud Executive (draft-only)
- Human approval is required before posting to Odoo
- To approve: move approval file to `Approved/`
"""

    draft_file = PLANS_CLOUD / f"DRAFT_invoice_{task_id}.md"
    draft_file.write_text(draft_content, encoding="utf-8")

    approval_content = f"""---
type: approval_request
action: post_invoice
source: cloud-executive
created: {now.strftime('%Y-%m-%d %H:%M')}
correlation_id: {task_id}
draft_file: DRAFT_invoice_{task_id}.md
priority: {priority}
partner: {partner}
---

# Approval Request: Odoo Invoice for {partner}

**Amount**: {amount}
**Action**: Post invoice to Odoo

To approve: move this file to `Approved/`
"""
    approval_file = PENDING_APPROVAL / f"APPROVE_invoice_{task_id}.md"
    approval_file.write_text(approval_content, encoding="utf-8")

    logger.info(f"[DRAFT] Odoo invoice draft created: {draft_file.name}")
    return draft_file.name, approval_file.name


# ── ACTION ROUTER ─────────────────────────────────────────────────────────
# Maps frontmatter action/type to the appropriate draft generator
ACTION_ROUTES = {
    "reply_email":    generate_email_draft,
    "email_triage":   generate_email_draft,
    "email":          generate_email_draft,
    "linkedin_post":  lambda m, b, t: generate_social_draft(m, b, t, "linkedin"),
    "facebook_post":  lambda m, b, t: generate_social_draft(m, b, t, "facebook"),
    "instagram_post": lambda m, b, t: generate_social_draft(m, b, t, "instagram"),
    "x_post":         lambda m, b, t: generate_social_draft(m, b, t, "x"),
    "twitter_post":   lambda m, b, t: generate_social_draft(m, b, t, "x"),
    "social_post":    lambda m, b, t: generate_social_draft(m, b, t, "linkedin"),
    "create_invoice": generate_odoo_draft,
    "invoice":        generate_odoo_draft,
    "odoo":           generate_odoo_draft,
}


# ── CLOUD SERVICE MANAGER ────────────────────────────────────────────────
class CloudServiceManager:
    """Manages cloud-specific watcher subprocesses."""

    def __init__(self):
        self.services = {}
        self.service_configs = {
            "cloud_sync_watcher": {
                "script": "watcher/cloud_sync_watcher.py",
                "restart_delay": 10, "max_restarts": 3,
            },
        }
        self.restart_counts = {}
        self.last_restart = {}

    def start_service(self, name):
        if name in self.services:
            return False
        config = self.service_configs.get(name)
        if not config:
            return False
        script_path = VAULT_DIR / config["script"]
        if not script_path.exists():
            logger.warning(f"[{name}] Script not found: {script_path}")
            return False
        try:
            proc = subprocess.Popen(
                [sys.executable, str(script_path)], cwd=str(VAULT_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            self.services[name] = proc
            self.restart_counts[name] = 0
            self.last_restart[name] = time.time()
            logger.info(f"[{name}] Started (PID {proc.pid})")
            return True
        except OSError as e:
            logger.error(f"[{name}] Failed to start: {e}")
            return False

    def stop_service(self, name):
        if name not in self.services:
            return False
        proc = self.services[name]
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        del self.services[name]
        logger.info(f"[{name}] Stopped")
        return True

    def check_health(self):
        failed = []
        for name, proc in list(self.services.items()):
            if proc.poll() is not None:
                logger.warning(f"[{name}] Crashed")
                now = time.time()
                if name in self.last_restart and now - self.last_restart[name] > 300:
                    self.restart_counts[name] = 0
                if self.restart_counts.get(name, 0) < self.service_configs[name]["max_restarts"]:
                    self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
                    self.last_restart[name] = now
                    logger.info(f"[{name}] Restarting (attempt {self.restart_counts[name]})")
                    del self.services[name]
                    self.start_service(name)
                else:
                    logger.error(f"[{name}] Exceeded restart limit")
                    failed.append(name)
                    del self.services[name]
        return failed

    def get_status(self):
        return {
            name: {
                "running": proc.poll() is None,
                "pid": proc.pid if proc.poll() is None else None,
                "restarts": self.restart_counts.get(name, 0),
            }
            for name, proc in self.services.items()
        }


# ── CLOUD EXECUTIVE PROCESSOR ────────────────────────────────────────────
class CloudExecutiveProcessor:
    """Core cloud processing loop: triage → draft → approval → update."""

    def __init__(self, dry_run=False):
        self.running = False
        self.dry_run = dry_run
        self.service_manager = CloudServiceManager()
        self.heartbeat_file = VAULT_DIR / "data" / "cloud_heartbeat.json"
        self._tasks_processed = 0
        self._drafts_created = 0
        self._errors = 0

        # A2A Phase 2 node (cloud role)
        self._a2a_node = None
        if HAS_A2A:
            try:
                self._a2a_node = A2ANode(role="cloud")
            except Exception as e:
                logger.warning(f"[A2A] Failed to create cloud node: {e}")

    def start(self):
        logger.info("Starting Cloud Executive Orchestrator (Platinum Tier)")
        self.running = True

        # Start A2A Phase 2 node (listens for approval_complete, sync_request, etc.)
        if self._a2a_node:
            self._a2a_node.on_message(self._handle_a2a_message)
            self._a2a_node.start()
            logger.info("[A2A] Cloud node started (Phase 2)")

        for name in self.service_manager.service_configs:
            self.service_manager.start_service(name)

        if schedule:
            schedule.every(5).minutes.do(self.heartbeat)
            schedule.every(15).minutes.do(self.run_git_sync)
            schedule.every(1).hours.do(self.log_status)
            if self._a2a_node and _A2A_ENABLED:
                schedule.every(10).minutes.do(self._a2a_health_ping)

        self.process_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.process_thread.start()

        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

        logger.info("Cloud Executive Orchestrator started")

    def stop(self):
        logger.info("Stopping Cloud Executive Orchestrator")
        self.running = False
        if self._a2a_node:
            self._a2a_node.stop()
            logger.info("[A2A] Cloud node stopped")
        for name in list(self.service_manager.services):
            self.service_manager.stop_service(name)
        logger.info("Cloud Executive Orchestrator stopped")

    def main_loop(self):
        logger.info("Cloud Executive main loop started")
        while self.running:
            try:
                self.service_manager.check_health()
                self.process_cloud_tasks()
                time.sleep(10)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                self._errors += 1
                time.sleep(5)

    def _run_scheduler(self):
        while self.running:
            if schedule:
                schedule.run_pending()
            time.sleep(30)

    # ── Core triage/draft loop ────────────────────────────────────────────
    def process_cloud_tasks(self):
        """Process all tasks in Needs_Action/cloud/ via claim-by-move."""
        task_files = sorted(NEEDS_ACTION_CLOUD.glob("*.md"))
        if not task_files:
            return

        logger.info(f"Found {len(task_files)} cloud tasks to process")

        for task_file in task_files:
            try:
                self.run_cloud_agent(task_file)
            except Exception as e:
                logger.error(f"Error processing {task_file.name}: {e}")
                self._errors += 1
                # Quarantine on repeated failure
                try:
                    quarantine_dest = QUARANTINE_DIR / task_file.name
                    task_file.rename(quarantine_dest)
                    logger.warning(f"[QUARANTINE] Moved {task_file.name} to Quarantine/")
                except OSError:
                    pass

    def run_cloud_agent(self, task_file):
        """Run the Cloud Executive triage/draft cycle on a single task.

        Steps:
          1. Claim-by-move → In_Progress/cloud/
          2. Parse frontmatter (action, type, priority)
          3. Route to appropriate draft generator
          4. Write draft to Plans/cloud/
          5. Write approval to Pending_Approval/local/
          6. Write update to Updates/
          7. Move to Done/cloud/
        """
        now = datetime.now()
        task_id = now.strftime("%Y%m%d_%H%M%S")

        # ── Step 1: Claim-by-move ─────────────────────────────────────────
        claimed_path = IN_PROGRESS_CLOUD / task_file.name
        if claimed_path.exists():
            logger.warning(f"[SKIP] {task_file.name} already claimed in In_Progress/cloud/")
            return False

        if self.dry_run:
            logger.info(f"[DRY RUN] Would process {task_file.name}")
            return True

        task_file.rename(claimed_path)
        logger.info(f"[CLAIM] {task_file.name} → In_Progress/cloud/")

        # ── Step 2: Parse frontmatter ─────────────────────────────────────
        content = claimed_path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(content)

        action = meta.get("action", meta.get("type", "email_triage"))
        priority = classify_priority(meta, body)
        logger.info(f"[TRIAGE] {claimed_path.name}: action={action}, priority={priority}")

        # ── Step 3: Route to draft generator ──────────────────────────────
        generator = ACTION_ROUTES.get(action, generate_email_draft)
        draft_name, approval_name = generator(meta, body, task_id)

        self._drafts_created += 1
        self._tasks_processed += 1

        # ── Step 3b: Notify local via A2A (Phase 2) ──────────────────────
        if self._a2a_node:
            try:
                self._a2a_node.notify_draft_ready(
                    draft_id=task_id,
                    draft_type=action,
                    summary=f"{action} draft from {meta.get('from', 'unknown')}",
                )
            except Exception as e:
                logger.warning(f"[A2A] Failed to notify draft_ready: {e}")

        # ── Step 4: Write dashboard update to Updates/ ────────────────────
        update_file = UPDATES_DIR / f"cloud_status_{task_id}.md"
        update_file.write_text(
            f"---\ntype: cloud_status\nsource: cloud-executive\n"
            f"timestamp: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"summary: Cloud triage processed {claimed_path.name} ({priority})\n---\n\n"
            f"# Cloud Status Update — {now.strftime('%Y-%m-%d')}\n\n"
            f"## Task Processed\n"
            f"- **File**: {claimed_path.name}\n"
            f"- **Action**: {action}\n"
            f"- **Priority**: {priority}\n"
            f"- **Draft**: {draft_name}\n"
            f"- **Approval**: {approval_name}\n\n"
            f"## Metrics\n"
            f"- Tasks processed (session): {self._tasks_processed}\n"
            f"- Drafts created (session): {self._drafts_created}\n"
            f"- Errors (session): {self._errors}\n",
            encoding="utf-8",
        )

        # ── Step 5: Move to Done/cloud/ ───────────────────────────────────
        done_path = DONE_CLOUD / f"DONE_cloud_{task_id}_{claimed_path.name}"
        claimed_path.rename(done_path)
        logger.info(f"[DONE] {claimed_path.name} → Done/cloud/")

        return True

    # ── Supporting operations ─────────────────────────────────────────────
    def heartbeat(self):
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "service": "cloud_executive",
                "status": "running",
                "version": "platinum",
                "tasks_processed": self._tasks_processed,
                "drafts_created": self._drafts_created,
                "errors": self._errors,
                "services": self.service_manager.get_status(),
            }
            self.heartbeat_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")

    def run_git_sync(self):
        """Git pull → push cycle for data/ sync."""
        try:
            logger.info("[SYNC] Running Git synchronization")

            pull = subprocess.run(
                ["git", "pull", "--rebase", "--autostash"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )
            if pull.returncode != 0:
                logger.warning(f"[SYNC] Git pull failed: {pull.stderr.strip()}")
                return

            # Stage only data/ directory (no secrets)
            subprocess.run(
                ["git", "add", "data/"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )

            commit = subprocess.run(
                ["git", "commit", "-m", f"cloud sync {datetime.now().isoformat()}"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )

            if commit.returncode in (0, 1):  # 1 = nothing to commit
                push = subprocess.run(
                    ["git", "push"],
                    cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
                )
                if push.returncode == 0:
                    logger.info("[SYNC] Git sync completed")
                else:
                    logger.warning(f"[SYNC] Git push failed: {push.stderr.strip()}")

        except subprocess.TimeoutExpired:
            logger.error("[SYNC] Git sync timed out")
        except Exception as e:
            logger.error(f"[SYNC] Git sync failed: {e}")

    def log_status(self):
        try:
            status = self.service_manager.get_status()
            cloud_dirs = {
                "Needs_Action/cloud": NEEDS_ACTION_CLOUD,
                "In_Progress/cloud":  IN_PROGRESS_CLOUD,
                "Plans/cloud":        PLANS_CLOUD,
                "Done/cloud":         DONE_CLOUD,
            }
            counts = {
                name: len(list(d.glob("*.md"))) if d.exists() else 0
                for name, d in cloud_dirs.items()
            }
            logger.info(f"[STATUS] services={json.dumps(status)} files={counts} "
                        f"processed={self._tasks_processed} drafts={self._drafts_created} "
                        f"errors={self._errors}")
        except Exception as e:
            logger.error(f"Status log failed: {e}")

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Cloud Executive Orchestrator (Platinum Tier)")
    parser.add_argument("--status", action="store_true", help="Check service status")
    parser.add_argument("--health", action="store_true", help="Run health checks")
    parser.add_argument("--sync", action="store_true", help="Force Git synchronization")
    parser.add_argument("--dry-run", action="store_true", help="Log only, no file moves")
    args = parser.parse_args()

    dry_run = args.dry_run or DRY_RUN
    orchestrator = CloudExecutiveProcessor(dry_run=dry_run)

    if args.status:
        print(f"Cloud Executive Orchestrator (dry_run={dry_run})")
        status = orchestrator.service_manager.get_status()
        for svc, info in status.items():
            print(f"  {svc}: {'RUNNING' if info['running'] else 'STOPPED'} (restarts: {info['restarts']})")
        if not status:
            print("  No services running")
        return

    if args.health:
        print("Running health checks...")
        failed = orchestrator.service_manager.check_health()
        print(f"Failed services: {failed or 'none'}")
        return

    if args.sync:
        print("Running forced Git sync...")
        orchestrator.run_git_sync()
        return

    signal.signal(signal.SIGINT, orchestrator.signal_handler)
    signal.signal(signal.SIGTERM, orchestrator.signal_handler)

    try:
        orchestrator.start()
        while orchestrator.running:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    main()
