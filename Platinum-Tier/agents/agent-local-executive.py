#!/usr/bin/env python3
"""
Local Executive Agent — Platinum Tier

The Local Executive agent is the local approval/execution agent that complements the Cloud Executive.
This agent runs on the local machine and handles all operations requiring local execution,
human approval, and access to sensitive credentials.

Core Loop (Ralph Wiggum - Local Executive enhanced):
1. Sync pull
2. Read /Pending_Approval/local/ + /Updates/
3. Human HITL: Wait for file moves to /Approved/
4. Execute: Send/post/pay via MCP (using local secrets)
5. Merge updates to Dashboard.md
6. Log, move /Done/local/
7. Sync push
"""

import os
import sys
import time
import logging
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Optional, Any

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = VAULT_DIR / "data"
LOG_DIR = DATA_DIR / "Logs"
LOCAL_AGENT_LOG_FILE = LOG_DIR / "local_executive.log"

# Directory paths
PENDING_APPROVAL_DIR = DATA_DIR / "Pending_Approval" / "local"
APPROVED_DIR = DATA_DIR / "Approved"
REJECTED_DIR = DATA_DIR / "Rejected"
DONE_LOCAL_DIR = DATA_DIR / "Done" / "local"
UPDATES_DIR = DATA_DIR / "Updates"
IN_PROGRESS_DIR = DATA_DIR / "In_Progress" / "local"
PLANS_LOCAL_DIR = DATA_DIR / "Plans" / "local"
DASHBOARD_PATH = DATA_DIR / "Dashboard.md"

# Ensure directories exist
for d in [LOG_DIR, PENDING_APPROVAL_DIR, APPROVED_DIR, REJECTED_DIR,
          DONE_LOCAL_DIR, UPDATES_DIR, IN_PROGRESS_DIR, PLANS_LOCAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - LocalExecutive - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOCAL_AGENT_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("LocalExecutive")

# ── ACTION ROUTING MAP ────────────────────────────────────────────────────
# Maps action types from YAML frontmatter to their MCP server and handler
ACTION_ROUTES = {
    "send_email": {"mcp": "email-mcp", "command": "node", "args": ["mcp-servers/email-mcp/index.js"]},
    "reply_email": {"mcp": "email-mcp", "command": "node", "args": ["mcp-servers/email-mcp/index.js"]},
    "forward_email": {"mcp": "email-mcp", "command": "node", "args": ["mcp-servers/email-mcp/index.js"]},
    "linkedin_post": {"mcp": "social-mcp", "command": "python", "args": ["mcp-servers/social-mcp/social_mcp.py"]},
    "facebook_post": {"mcp": "social-mcp-fb", "command": "node", "args": ["mcp-servers/social-mcp-fb/social-mcp-fb.js"]},
    "instagram_post": {"mcp": "social-mcp-ig", "command": "node", "args": ["mcp-servers/social-mcp-ig/social-mcp-ig.js"]},
    "x_post": {"mcp": "social-mcp-x", "command": "node", "args": ["mcp-servers/social-mcp-x/social-mcp-x.js"]},
    "twitter_post": {"mcp": "social-mcp-x", "command": "node", "args": ["mcp-servers/social-mcp-x/social-mcp-x.js"]},
    "create_invoice": {"mcp": "odoo-mcp", "command": "python", "args": ["mcp-servers/odoo-mcp/odoo_mcp.py"]},
    "record_payment": {"mcp": "odoo-mcp", "command": "python", "args": ["mcp-servers/odoo-mcp/odoo_mcp.py"]},
    "odoo_action": {"mcp": "odoo-mcp", "command": "python", "args": ["mcp-servers/odoo-mcp/odoo_mcp.py"]},
}


def parse_yaml_frontmatter(content: str) -> Dict[str, str]:
    """Parse YAML frontmatter from a Markdown file.

    Supports the standard --- delimited frontmatter format:
    ---
    key: value
    another_key: value
    ---
    """
    frontmatter = {}
    lines = content.strip().split("\n")

    if not lines or lines[0].strip() != "---":
        return frontmatter

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        return frontmatter

    for line in lines[1:end_idx]:
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()

    return frontmatter


def write_audit_log(action: str, details: Dict[str, Any], severity: str = "INFO"):
    """Write a structured JSON audit log entry."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{today}.json"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "actor": "local-executive",
        "action_type": action,
        "severity": severity,
        "correlation_id": f"local_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "details": details,
    }

    entries = []
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []

    entries.append(entry)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    return entry["correlation_id"]


# ── LOCAL EXECUTIVE AGENT ─────────────────────────────────────────────────
class LocalExecutiveAgent:
    """Local Executive Agent implementation - handles approvals and execution."""

    def __init__(self):
        self.running = False
        self.completed_cycles = 0

    def run_ralph_loop(self):
        """Execute the Local Executive Ralph Wiggum loop."""
        logger.info("Starting Local Executive Ralph Wiggum Loop")

        while self.running:
            try:
                logger.info(f"Starting Local Executive processing cycle #{self.completed_cycles + 1}")

                # Step 1: Sync pull
                logger.info("Step 1: Sync pulling from remote repository")
                self.sync_pull()

                # Step 2: Read /Pending_Approval/local/ + /Updates/
                logger.info("Step 2: Reading Pending Approval and Updates")
                self.read_pending_approvals()
                self.process_updates()

                # Step 3: Human HITL: Wait for file moves to /Approved/
                logger.info("Step 3: Monitoring for human approvals")
                approved_files = self.check_for_approvals()

                # Step 4: Execute: Send/post/pay via MCP (using local secrets)
                if approved_files:
                    logger.info(f"Step 4: Executing {len(approved_files)} approved actions")
                    for approved_file in approved_files:
                        self.execute_approved_action(approved_file)

                # Step 5: Merge updates to Dashboard.md
                logger.info("Step 5: Merging updates to Dashboard")
                self.merge_dashboard_updates()

                # Step 6: Log, move /Done/local/
                logger.info("Step 6: Logging and moving completed tasks")
                self.process_completed_tasks()

                # Step 7: Sync push
                logger.info("Step 7: Sync pushing to remote repository")
                self.sync_push()

                self.completed_cycles += 1
                logger.info(f"Completed Local Executive processing cycle #{self.completed_cycles}")

                # Check if we should continue or exit
                if not self.should_continue():
                    logger.info("Local Executive completing tasks, preparing to exit")
                    break

                # Wait before next cycle
                time.sleep(30)  # Wait 30 seconds between cycles

            except Exception as e:
                logger.error(f"Error in Local Executive loop: {e}")
                write_audit_log("loop_error", {"error": str(e), "cycle": self.completed_cycles + 1}, "ERROR")
                time.sleep(10)  # Brief pause before continuing
                continue

    def sync_pull(self):
        """Git pull latest changes from remote repository."""
        try:
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("Git pull successful")
                write_audit_log("sync_pull", {"status": "success", "output": result.stdout.strip()})
            else:
                logger.warning(f"Git pull failed: {result.stderr}")
                write_audit_log("sync_pull", {"status": "failed", "error": result.stderr.strip()}, "WARN")
        except subprocess.TimeoutExpired:
            logger.error("Git pull timed out after 30s")
            write_audit_log("sync_pull", {"status": "timeout"}, "ERROR")
        except Exception as e:
            logger.error(f"Git pull failed: {e}")

    def read_pending_approvals(self):
        """Read files from /Pending_Approval/local/."""
        try:
            pending_files = list(PENDING_APPROVAL_DIR.glob("*.md"))
            logger.info(f"Found {len(pending_files)} pending approval files")

            for file_path in pending_files:
                logger.info(f"  - {file_path.name}")

        except Exception as e:
            logger.error(f"Error reading pending approvals: {e}")

    def process_updates(self):
        """Process cloud update files from /Updates/."""
        try:
            update_files = list(UPDATES_DIR.glob("*.md"))
            logger.info(f"Found {len(update_files)} update files to process")

            for file_path in update_files:
                logger.info(f"  - Processing update: {file_path.name}")
                self.process_update_file(file_path)

        except Exception as e:
            logger.error(f"Error processing updates: {e}")

    def process_update_file(self, update_file: Path):
        """Process a single cloud update file and extract metrics/activity for dashboard merge."""
        try:
            content = update_file.read_text(encoding="utf-8")
            frontmatter = parse_yaml_frontmatter(content)

            update_type = frontmatter.get("type", "general")
            source = frontmatter.get("source", "cloud")
            timestamp = frontmatter.get("timestamp", datetime.now().isoformat())

            # Extract update data from file body (everything after frontmatter)
            body = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()

            # Store parsed update for dashboard merge
            parsed_update = {
                "type": update_type,
                "source": source,
                "timestamp": timestamp,
                "body": body,
                "file": update_file.name,
            }

            write_audit_log("process_update", {
                "file": update_file.name,
                "type": update_type,
                "source": source,
            })

            # Archive the processed update file
            archive_name = f"processed_{update_file.name}"
            archive_path = DONE_LOCAL_DIR / archive_name
            shutil.move(str(update_file), str(archive_path))
            logger.info(f"Processed and archived update: {update_file.name} → Done/local/{archive_name}")

            return parsed_update

        except Exception as e:
            logger.error(f"Error processing update file {update_file.name}: {e}")
            return None

    def check_for_approvals(self):
        """Check for approved files in /Approved/ directory."""
        try:
            approved_files = list(APPROVED_DIR.glob("*.md"))
            logger.info(f"Found {len(approved_files)} approved files for execution")
            return approved_files

        except Exception as e:
            logger.error(f"Error checking for approvals: {e}")
            return []

    def execute_approved_action(self, approved_file: Path):
        """Execute an approved action by parsing YAML frontmatter and routing to the correct MCP server."""
        correlation_id = None
        try:
            logger.info(f"Executing approved action: {approved_file.name}")

            content = approved_file.read_text(encoding="utf-8")
            frontmatter = parse_yaml_frontmatter(content)

            # Extract action type and parameters
            action = frontmatter.get("action", "").strip()
            target = frontmatter.get("target", "").strip()
            subject = frontmatter.get("subject", "").strip()
            to_address = frontmatter.get("to", "").strip()
            priority = frontmatter.get("priority", "normal").strip()

            if not action:
                logger.warning(f"No action field in {approved_file.name}, skipping")
                write_audit_log("execute_skip", {
                    "file": approved_file.name,
                    "reason": "no_action_field",
                }, "WARN")
                return

            # Check if already executed (prevent re-execution)
            if frontmatter.get("execution_result"):
                logger.info(f"Already executed: {approved_file.name}, skipping")
                return

            correlation_id = write_audit_log("execute_start", {
                "file": approved_file.name,
                "action": action,
                "target": target,
                "priority": priority,
            })

            # Route to appropriate MCP server
            route = ACTION_ROUTES.get(action)
            if not route:
                logger.warning(f"Unknown action type '{action}' in {approved_file.name}")
                write_audit_log("execute_unknown_action", {
                    "file": approved_file.name,
                    "action": action,
                }, "WARN")
                return

            logger.info(f"Routing action '{action}' to MCP server: {route['mcp']}")

            # Extract body content (after frontmatter) for the action payload
            body = content
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    body = parts[2].strip()

            # Build execution context
            exec_context = {
                "action": action,
                "target": target,
                "subject": subject,
                "to": to_address,
                "body": body[:2000],  # Truncate for safety
                "priority": priority,
                "source_file": approved_file.name,
                "correlation_id": correlation_id,
            }

            # Execute via MCP server subprocess
            mcp_path = VAULT_DIR / route["args"][0]
            if not mcp_path.exists():
                logger.error(f"MCP server not found: {mcp_path}")
                write_audit_log("execute_error", {
                    "file": approved_file.name,
                    "error": f"MCP server not found: {route['args'][0]}",
                }, "ERROR")
                return

            # Pass execution context as JSON via stdin to the MCP server
            exec_payload = json.dumps(exec_context)

            result = subprocess.run(
                [route["command"]] + [str(VAULT_DIR / a) for a in route["args"]],
                input=exec_payload,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(VAULT_DIR),
                env={**os.environ, "MCP_ACTION": action, "MCP_EXEC_MODE": "approved"},
            )

            execution_result = "success" if result.returncode == 0 else "failed"
            execution_output = result.stdout.strip() if result.stdout else result.stderr.strip()

            # Append execution result to the file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_block = f"\n\n---\n## Execution Result\n- **status**: {execution_result}\n- **executed_by**: local-executive\n- **executed_at**: {timestamp}\n- **mcp_server**: {route['mcp']}\n- **correlation_id**: {correlation_id}\n- **output**: {execution_output[:500]}\n"

            updated_content = content + result_block
            approved_file.write_text(updated_content, encoding="utf-8")

            write_audit_log("execute_complete", {
                "file": approved_file.name,
                "action": action,
                "result": execution_result,
                "mcp": route["mcp"],
                "correlation_id": correlation_id,
            }, "INFO" if execution_result == "success" else "ERROR")

            logger.info(f"Executed action '{action}' from {approved_file.name}: {execution_result}")

            # Move to Done/local/
            done_path = DONE_LOCAL_DIR / approved_file.name
            shutil.move(str(approved_file), str(done_path))
            logger.info(f"Moved completed task to Done/local/: {approved_file.name}")

        except subprocess.TimeoutExpired:
            logger.error(f"MCP execution timed out for {approved_file.name}")
            write_audit_log("execute_timeout", {
                "file": approved_file.name,
                "correlation_id": correlation_id,
            }, "ERROR")
        except Exception as e:
            logger.error(f"Error executing approved action {approved_file.name}: {e}")
            write_audit_log("execute_error", {
                "file": approved_file.name,
                "error": str(e),
                "correlation_id": correlation_id,
            }, "ERROR")

    def merge_dashboard_updates(self):
        """Merge cloud updates into Dashboard.md using the single-writer principle.

        Reads cloud update files from /Updates/, extracts metrics and activity,
        and merges them into the local Dashboard.md while preserving local metrics.
        """
        try:
            if not DASHBOARD_PATH.exists():
                logger.warning("Dashboard.md not found, skipping merge")
                return

            current_content = DASHBOARD_PATH.read_text(encoding="utf-8")

            # Check for any remaining unprocessed update files
            update_files = list(UPDATES_DIR.glob("*.md"))
            if not update_files:
                return  # Nothing to merge

            # Collect cloud metrics from update files
            cloud_activities = []
            for uf in update_files:
                try:
                    uf_content = uf.read_text(encoding="utf-8")
                    fm = parse_yaml_frontmatter(uf_content)
                    activity_type = fm.get("type", "cloud_update")
                    timestamp = fm.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    summary = fm.get("summary", uf.stem)
                    cloud_activities.append(f"- {timestamp} | [CLOUD] {activity_type}: {summary}")
                except Exception:
                    continue

            if not cloud_activities:
                return

            # Find the "## Recent Activity" section and prepend cloud entries
            activity_header = "## Recent Activity"
            if activity_header in current_content:
                header_pos = current_content.index(activity_header)
                after_header = current_content[header_pos + len(activity_header):]
                # Insert cloud activities after the header
                cloud_block = "\n".join(cloud_activities)
                updated_content = (
                    current_content[:header_pos + len(activity_header)]
                    + "\n"
                    + cloud_block
                    + after_header
                )
            else:
                # Append a new section
                cloud_block = "\n".join(cloud_activities)
                updated_content = current_content + f"\n\n{activity_header}\n{cloud_block}\n"

            # Update the sync status in System Health
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            if "Cloud Sync:" in updated_content:
                updated_content = re.sub(
                    r"- Cloud Sync:.*",
                    f"- Cloud Sync: Last merged {timestamp} ({len(cloud_activities)} updates)",
                    updated_content,
                )
            elif "## System Health" in updated_content:
                updated_content = updated_content.replace(
                    "## System Health",
                    f"## System Health\n- Cloud Sync: Last merged {timestamp} ({len(cloud_activities)} updates)",
                )

            DASHBOARD_PATH.write_text(updated_content, encoding="utf-8")
            logger.info(f"Dashboard merged with {len(cloud_activities)} cloud updates")

            write_audit_log("dashboard_merge", {
                "updates_merged": len(cloud_activities),
                "timestamp": timestamp,
            })

        except Exception as e:
            logger.error(f"Error merging dashboard updates: {e}")
            write_audit_log("dashboard_merge_error", {"error": str(e)}, "ERROR")

    def process_completed_tasks(self):
        """Move processed tasks from In_Progress/local/ to Done/local/."""
        try:
            # Check In_Progress/local/ for completed items
            in_progress_files = list(IN_PROGRESS_DIR.glob("*.md"))
            for file_path in in_progress_files:
                content = file_path.read_text(encoding="utf-8")
                fm = parse_yaml_frontmatter(content)

                # If the file has an execution_result, it's done
                if "execution_result" in fm or "## Execution Result" in content:
                    done_path = DONE_LOCAL_DIR / file_path.name
                    shutil.move(str(file_path), str(done_path))
                    logger.info(f"Moved completed task to Done/local/: {file_path.name}")
                    write_audit_log("task_completed", {"file": file_path.name, "destination": "Done/local/"})

        except Exception as e:
            logger.error(f"Error processing completed tasks: {e}")

    def sync_push(self):
        """Git push completed work back to remote repository."""
        try:
            # Stage data/ directory changes only (not secrets)
            add_result = subprocess.run(
                ["git", "add", "data/"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if add_result.returncode != 0:
                logger.warning(f"Git add failed: {add_result.stderr}")
                return

            # Check if there are changes to commit
            status_result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if status_result.returncode == 0:
                logger.info("No changes to commit")
                return

            # Commit changes
            commit_msg = f"Local Executive cycle {self.completed_cycles} - {datetime.now().isoformat()}"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if commit_result.returncode != 0:
                logger.warning(f"Git commit failed: {commit_result.stderr}")
                return

            # Push changes
            push_result = subprocess.run(
                ["git", "push"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if push_result.returncode == 0:
                logger.info("Git push successful")
                write_audit_log("sync_push", {"status": "success"})
            else:
                logger.warning(f"Git push failed: {push_result.stderr}")
                write_audit_log("sync_push", {"status": "failed", "error": push_result.stderr.strip()}, "WARN")

        except subprocess.TimeoutExpired:
            logger.error("Git push timed out")
            write_audit_log("sync_push", {"status": "timeout"}, "ERROR")
        except Exception as e:
            logger.error(f"Git push failed: {e}")

    def should_continue(self):
        """Determine if the Local Executive should continue processing."""
        try:
            # Check if there are still tasks to process
            pending_files = list(PENDING_APPROVAL_DIR.glob("*.md"))
            if pending_files:
                logger.info(f"Still {len(pending_files)} pending approvals, continuing...")
                return True

            # Check if there are any cloud updates to process
            update_files = list(UPDATES_DIR.glob("*.md"))
            if update_files:
                logger.info(f"Still {len(update_files)} updates to process, continuing...")
                return True

            # Check for approved files awaiting execution
            approved_files = list(APPROVED_DIR.glob("*.md"))
            if approved_files:
                logger.info(f"Still {len(approved_files)} approved files to execute, continuing...")
                return True

            # Check for in-progress items
            in_progress_files = list(IN_PROGRESS_DIR.glob("*.md"))
            if in_progress_files:
                logger.info(f"Still {len(in_progress_files)} in-progress items, continuing...")
                return True

            # Local Executive typically runs continuously
            return True

        except Exception as e:
            logger.error(f"Error in should_continue check: {e}")
            return True  # Default to continuing if there's an error

    def start(self):
        """Start the Local Executive agent."""
        logger.info("Starting Local Executive Agent (Platinum Tier)")
        logger.info("Local Executive handles: Approvals, WhatsApp, Banking, Final Sends/Posts")
        logger.info("Sync: Pull Git, handle conflicts, push completed work")
        logger.info("Secrets: All local credentials, never sync to cloud")

        write_audit_log("agent_start", {
            "agent": "local-executive",
            "tier": "platinum",
            "vault_dir": str(VAULT_DIR),
        })

        self.running = True
        self.run_ralph_loop()

    def stop(self):
        """Stop the Local Executive agent."""
        logger.info("Stopping Local Executive Agent")
        write_audit_log("agent_stop", {
            "agent": "local-executive",
            "completed_cycles": self.completed_cycles,
        })
        self.running = False


def main():
    """Main entry point for Local Executive agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Local Executive Agent (Platinum Tier)")
    parser.add_argument("--single-run", action="store_true", help="Run one cycle then exit")
    args = parser.parse_args()

    agent = LocalExecutiveAgent()

    if args.single_run:
        logger.info("Running single Local Executive cycle")
        try:
            agent.sync_pull()
            agent.read_pending_approvals()
            agent.process_updates()

            approved_files = agent.check_for_approvals()
            if approved_files:
                for approved_file in approved_files:
                    agent.execute_approved_action(approved_file)

            agent.merge_dashboard_updates()
            agent.process_completed_tasks()
            agent.sync_push()

            logger.info("Local Executive single cycle completed")

        except Exception as e:
            logger.error(f"Error in single run: {e}")
    else:
        # Continuous operation
        try:
            agent.start()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            agent.stop()


if __name__ == "__main__":
    main()
