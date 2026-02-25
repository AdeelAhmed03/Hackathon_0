#!/usr/bin/env python3
"""
Local Orchestrator — Platinum Tier

Runs as the local sub-orchestrator launched by the main orchestrator.py.
Handles the Local Executive's core loop:

  1. Git sync pull (receive cloud drafts/updates)
  2. Merge Updates/ → Dashboard.md  (single-writer principle)
  3. Scan Approved/ → execute approved actions via MCP
  4. Delegation: write to Needs_Action/cloud/ for cloud tasks
  5. Claim-by-move to In_Progress/local/ (prevent double-work)
  6. Git sync push after each cycle

Local agent owns execution: send email, post social, pay invoice.
Cloud agent NEVER reaches this code path.

Usage:
    python orchestrator_local.py                # Start local orchestrator
    python orchestrator_local.py --status       # Check service status
    python orchestrator_local.py --health       # Run health checks
    python orchestrator_local.py --sync         # Force Git synchronization
    python orchestrator_local.py --dry-run      # Log only, no file moves
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
LOCAL_LOG_FILE = LOG_DIR / "local_orchestrator.log"

# Platinum directories
NEEDS_ACTION_LOCAL = VAULT_DIR / "data" / "Needs_Action" / "local"
NEEDS_ACTION_CLOUD = VAULT_DIR / "data" / "Needs_Action" / "cloud"
IN_PROGRESS_LOCAL = VAULT_DIR / "data" / "In_Progress" / "local"
PENDING_APPROVAL = VAULT_DIR / "data" / "Pending_Approval" / "local"
APPROVED_DIR = VAULT_DIR / "data" / "Approved"
UPDATES_DIR = VAULT_DIR / "data" / "Updates"
DONE_LOCAL = VAULT_DIR / "data" / "Done" / "local"
PLANS_CLOUD = VAULT_DIR / "data" / "Plans" / "cloud"
QUARANTINE_DIR = VAULT_DIR / "data" / "Quarantine"
DASHBOARD_FILE = VAULT_DIR / "data" / "Dashboard.md"

# Ensure directories exist
for _d in (LOG_DIR, NEEDS_ACTION_LOCAL, IN_PROGRESS_LOCAL, PENDING_APPROVAL,
           APPROVED_DIR, UPDATES_DIR, DONE_LOCAL, QUARANTINE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DRY_RUN = os.environ.get("LOCAL_DRY_RUN", "false").lower() == "true"

# MCP server directory
MCP_SERVERS_DIR = VAULT_DIR / "mcp-servers"

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - LocalOrchestrator - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOCAL_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("LocalOrchestrator")


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


# ── MCP EXECUTION ENGINE ─────────────────────────────────────────────────
# Maps action names to (mcp-server-dir, tool-name)
MCP_ACTION_MAP = {
    "send_email":       ("email-mcp",  "send_email"),
    "reply_email":      ("email-mcp",  "send_email"),
    "post_linkedin":    ("social-mcp", "post_linkedin"),
    "post_facebook":    ("social-mcp-fb", "create_post"),
    "post_instagram":   ("social-mcp-ig", "create_post"),
    "post_x":           ("social-mcp-x",  "create_post"),
    "post_invoice":     ("odoo-mcp",   "post_invoice"),
    "create_invoice":   ("odoo-mcp",   "post_invoice"),
    "create_payment":   ("odoo-mcp",   "create_payment"),
}


def execute_via_mcp(action, args_dict):
    """Execute an action by calling the appropriate MCP server via stdio JSON-RPC.

    Returns (success: bool, result: dict).
    """
    route = MCP_ACTION_MAP.get(action)
    if not route:
        logger.warning(f"[MCP] No route for action '{action}', skipping execution")
        return False, {"error": f"Unknown action: {action}"}

    server_dir, tool_name = route
    server_script = MCP_SERVERS_DIR / server_dir / f"{server_dir.replace('-', '_')}.py"

    if not server_script.exists():
        logger.warning(f"[MCP] Server script not found: {server_script}")
        return False, {"error": f"Server script missing: {server_script.name}"}

    # Build JSON-RPC request
    request = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": args_dict},
    })

    try:
        result = subprocess.run(
            [sys.executable, str(server_script)],
            input=request + "\n",
            capture_output=True, text=True,
            cwd=str(VAULT_DIR), timeout=30,
            env={**os.environ, "VAULT_ENVIRONMENT": "local"},
        )

        if result.returncode != 0:
            logger.error(f"[MCP] {server_dir}/{tool_name} exited with code {result.returncode}")
            return False, {"error": result.stderr.strip()}

        # Parse last non-empty line of stdout as JSON-RPC response
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if lines:
            response = json.loads(lines[-1])
            if "result" in response:
                logger.info(f"[MCP] {server_dir}/{tool_name} succeeded")
                return True, response["result"]
            elif "error" in response:
                logger.error(f"[MCP] {server_dir}/{tool_name} error: {response['error']}")
                return False, response["error"]

        return False, {"error": "Empty response from MCP server"}

    except subprocess.TimeoutExpired:
        logger.error(f"[MCP] {server_dir}/{tool_name} timed out")
        return False, {"error": "timeout"}
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[MCP] {server_dir}/{tool_name} failed: {e}")
        return False, {"error": str(e)}


# ── DASHBOARD MERGER (Single-Writer Principle) ────────────────────────────
def merge_updates_to_dashboard():
    """Merge all files from Updates/ into Dashboard.md, then archive them.

    Single-writer principle: only the local orchestrator writes Dashboard.md.
    Cloud writes to Updates/ via Git sync; local merges here.
    """
    update_files = sorted(UPDATES_DIR.glob("*.md"))
    if not update_files:
        return 0

    logger.info(f"[MERGE] Merging {len(update_files)} update files into Dashboard.md")

    # Read current dashboard
    if DASHBOARD_FILE.exists():
        dashboard_content = DASHBOARD_FILE.read_text(encoding="utf-8")
    else:
        dashboard_content = "# Dashboard\n\n## Activity Log\n"

    # Build merge entries
    new_entries = []
    now = datetime.now()
    for uf in update_files:
        try:
            text = uf.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)
            summary = meta.get("summary", uf.stem)
            source = meta.get("source", "unknown")
            timestamp = meta.get("timestamp", now.strftime("%Y-%m-%d %H:%M"))
            new_entries.append(f"| {timestamp} | {source} | {summary} |")
        except OSError as e:
            logger.warning(f"[MERGE] Failed to read {uf.name}: {e}")

    if new_entries:
        # Insert entries into the Activity Log table
        marker = "## Recent Activity"
        if marker in dashboard_content:
            # Insert after the table header row
            parts = dashboard_content.split(marker, 1)
            table_section = parts[1]
            # Find end of existing table header (| --- | --- | --- |)
            header_end = table_section.find("\n\n")
            if header_end == -1:
                header_end = len(table_section)
            insert_point = table_section.rfind("|", 0, header_end)
            # Find the line after the last table row
            lines = table_section.splitlines()
            table_lines = []
            non_table_lines = []
            in_table = True
            for line in lines:
                if in_table and (line.startswith("|") or line.strip() == ""):
                    table_lines.append(line)
                else:
                    in_table = False
                    non_table_lines.append(line)

            merged_table = "\n".join(table_lines).rstrip()
            merged_table += "\n" + "\n".join(new_entries) + "\n"
            dashboard_content = parts[0] + marker + "\n" + merged_table + "\n" + "\n".join(non_table_lines)
        else:
            # Add a new Activity section
            dashboard_content += (
                f"\n\n## Recent Activity\n"
                f"| Timestamp | Source | Summary |\n"
                f"| --- | --- | --- |\n"
                + "\n".join(new_entries) + "\n"
            )

        DASHBOARD_FILE.write_text(dashboard_content, encoding="utf-8")
        logger.info(f"[MERGE] Added {len(new_entries)} entries to Dashboard.md")

    # Archive processed updates to Done/local/
    for uf in update_files:
        try:
            done_path = DONE_LOCAL / f"merged_{uf.name}"
            uf.rename(done_path)
        except OSError as e:
            logger.warning(f"[MERGE] Failed to archive {uf.name}: {e}")

    return len(new_entries)


# ── APPROVED FILE EXECUTOR ────────────────────────────────────────────────
def process_approved_files():
    """Scan Approved/ for files, execute actions via MCP, move to Done/local/.

    Flow: Approved/ file → claim to In_Progress/local/ → execute → Done/local/
    """
    approved_files = sorted(APPROVED_DIR.glob("APPROVE_*.md"))
    if not approved_files:
        return 0

    logger.info(f"[EXEC] Processing {len(approved_files)} approved actions")
    executed = 0

    for af in approved_files:
        try:
            # ── Claim-by-move ─────────────────────────────────────────
            claimed_path = IN_PROGRESS_LOCAL / af.name
            if claimed_path.exists():
                logger.warning(f"[SKIP] {af.name} already claimed in In_Progress/local/")
                continue

            af.rename(claimed_path)
            logger.info(f"[CLAIM] {af.name} → In_Progress/local/")

            # ── Parse approval file ───────────────────────────────────
            content = claimed_path.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)

            action = meta.get("action", "")
            correlation_id = meta.get("correlation_id", "")
            draft_file_name = meta.get("draft_file", "")

            # Read the associated draft for execution context
            args_dict = {}
            if draft_file_name:
                draft_path = PLANS_CLOUD / draft_file_name
                if draft_path.exists():
                    draft_content = draft_path.read_text(encoding="utf-8")
                    draft_meta, draft_body = parse_frontmatter(draft_content)
                    # Build MCP arguments from draft metadata
                    args_dict = {
                        k: v for k, v in draft_meta.items()
                        if k not in ("type", "status", "source", "created",
                                     "draft_only", "correlation_id")
                    }
                    if correlation_id:
                        args_dict["draft_id"] = correlation_id

            logger.info(f"[EXEC] Executing action '{action}' (correlation: {correlation_id})")

            # ── Execute via MCP ───────────────────────────────────────
            success, result = execute_via_mcp(action, args_dict)

            if success:
                executed += 1
                logger.info(f"[EXEC] Action '{action}' succeeded for {af.name}")
            else:
                logger.error(f"[EXEC] Action '{action}' failed for {af.name}: {result}")

            # ── Move to Done (even on failure, to prevent retry loop) ─
            done_name = f"DONE_local_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{claimed_path.name}"
            done_path = DONE_LOCAL / done_name
            claimed_path.rename(done_path)

            # ── Write execution update ────────────────────────────────
            UPDATES_DIR.mkdir(parents=True, exist_ok=True)
            update_file = UPDATES_DIR / f"local_exec_{correlation_id or datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            update_file.write_text(
                f"---\ntype: execution_result\nsource: local-executive\n"
                f"timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"summary: Executed {action} — {'success' if success else 'failed'}\n---\n\n"
                f"# Execution Result — {action}\n\n"
                f"- **Action**: {action}\n"
                f"- **Correlation**: {correlation_id}\n"
                f"- **Result**: {'Success' if success else 'Failed'}\n"
                f"- **Details**: {json.dumps(result, default=str)[:500]}\n",
                encoding="utf-8",
            )

        except Exception as e:
            logger.error(f"[EXEC] Error processing {af.name}: {e}")
            # Move to quarantine on unexpected errors
            try:
                quarantine_dest = QUARANTINE_DIR / af.name
                if af.exists():
                    af.rename(quarantine_dest)
                elif claimed_path.exists():
                    claimed_path.rename(quarantine_dest)
                logger.warning(f"[QUARANTINE] Moved {af.name} to Quarantine/")
            except OSError:
                pass

    return executed


# ── DELEGATION: Route tasks to cloud ──────────────────────────────────────
def process_local_needs_action():
    """Process Needs_Action/local/ — execute directly or delegate to cloud.

    Tasks whose action belongs to cloud domain get delegated to
    Needs_Action/cloud/ instead of being executed locally.
    """
    CLOUD_ACTIONS = {"email_triage", "linkedin_post", "facebook_post",
                     "instagram_post", "x_post", "social_post", "create_draft"}

    task_files = sorted(NEEDS_ACTION_LOCAL.glob("*.md"))
    if not task_files:
        return

    for task_file in task_files:
        try:
            content = task_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            action = meta.get("action", meta.get("type", ""))

            if action in CLOUD_ACTIONS:
                # Delegate to cloud
                NEEDS_ACTION_CLOUD.mkdir(parents=True, exist_ok=True)
                delegate_path = NEEDS_ACTION_CLOUD / task_file.name
                task_file.rename(delegate_path)
                logger.info(f"[DELEGATE] {task_file.name} → Needs_Action/cloud/ (action: {action})")
            else:
                # Local handles it: move to In_Progress/local/ for direct processing
                claimed_path = IN_PROGRESS_LOCAL / task_file.name
                if claimed_path.exists():
                    logger.warning(f"[SKIP] {task_file.name} already claimed")
                    continue
                task_file.rename(claimed_path)
                logger.info(f"[LOCAL] Claimed {task_file.name} for local processing")

                # Execute directly if action has an MCP route
                if action in MCP_ACTION_MAP:
                    args_dict = {k: v for k, v in meta.items()
                                 if k not in ("type", "status", "source", "created")}
                    success, result = execute_via_mcp(action, args_dict)
                    logger.info(f"[LOCAL] Executed {action}: {'success' if success else 'failed'}")

                # Move to Done
                done_path = DONE_LOCAL / f"DONE_local_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{claimed_path.name}"
                claimed_path.rename(done_path)

        except Exception as e:
            logger.error(f"[LOCAL] Error processing {task_file.name}: {e}")


# ── LOCAL SERVICE MANAGER ─────────────────────────────────────────────────
class LocalServiceManager:
    """Manages local watcher subprocesses."""

    def __init__(self):
        self.services = {}
        self.service_configs = {
            "local_sync_watcher": {
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


# ── LOCAL EXECUTIVE PROCESSOR ─────────────────────────────────────────────
class LocalExecutiveProcessor:
    """Core local processing loop: sync → merge → approve → execute."""

    def __init__(self, dry_run=False):
        self.running = False
        self.dry_run = dry_run
        self.service_manager = LocalServiceManager()
        self.heartbeat_file = VAULT_DIR / "data" / "local_heartbeat.json"
        self._updates_merged = 0
        self._actions_executed = 0
        self._delegated = 0
        self._errors = 0

        # A2A Phase 2 node (local role)
        self._a2a_node = None
        if HAS_A2A:
            try:
                self._a2a_node = A2ANode(role="local")
            except Exception as e:
                logger.warning(f"[A2A] Failed to create local node: {e}")

    def start(self):
        logger.info("Starting Local Executive Orchestrator (Platinum Tier)")
        self.running = True

        # Start A2A Phase 2 node (listens for draft_ready, sync_request, etc.)
        if self._a2a_node:
            self._a2a_node.on_message(self._handle_a2a_message)
            self._a2a_node.start()
            logger.info("[A2A] Local node started (Phase 2)")

        for name in self.service_manager.service_configs:
            self.service_manager.start_service(name)

        if schedule:
            schedule.every(5).minutes.do(self.heartbeat)
            schedule.every(10).minutes.do(self.run_git_sync)
            schedule.every(1).hours.do(self.log_status)

        self.process_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.process_thread.start()

        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

        logger.info("Local Executive Orchestrator started")

    def stop(self):
        logger.info("Stopping Local Executive Orchestrator")
        self.running = False
        if self._a2a_node:
            self._a2a_node.stop()
            logger.info("[A2A] Local node stopped")
        for name in list(self.service_manager.services):
            self.service_manager.stop_service(name)
        logger.info("Local Executive Orchestrator stopped")

    def main_loop(self):
        logger.info("Local Executive main loop started")
        while self.running:
            try:
                self.service_manager.check_health()

                if not self.dry_run:
                    # Step 1: Merge cloud Updates/ into Dashboard.md
                    merged = merge_updates_to_dashboard()
                    self._updates_merged += merged

                    # Step 2: Process approved actions (Approved/ → execute → Done)
                    executed = process_approved_files()
                    self._actions_executed += executed

                    # Step 3: Process local Needs_Action (direct exec or delegate to cloud)
                    process_local_needs_action()

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

    def heartbeat(self):
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "service": "local_executive",
                "status": "running",
                "version": "platinum",
                "updates_merged": self._updates_merged,
                "actions_executed": self._actions_executed,
                "delegated": self._delegated,
                "errors": self._errors,
                "services": self.service_manager.get_status(),
            }
            self.heartbeat_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")

    def run_git_sync(self):
        """Git pull → merge updates → push cycle."""
        try:
            logger.info("[SYNC] Running Git synchronization")

            # Pull first (receive cloud drafts/updates)
            pull = subprocess.run(
                ["git", "pull", "--rebase", "--autostash"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )
            if pull.returncode != 0:
                logger.warning(f"[SYNC] Git pull failed: {pull.stderr.strip()}")
                return

            # After pull, merge any new updates that arrived
            merged = merge_updates_to_dashboard()
            if merged > 0:
                self._updates_merged += merged
                logger.info(f"[SYNC] Merged {merged} post-pull updates")

            # Stage only data/ (no secrets)
            subprocess.run(
                ["git", "add", "data/"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )

            commit = subprocess.run(
                ["git", "commit", "-m", f"local sync {datetime.now().isoformat()}"],
                cwd=str(VAULT_DIR), capture_output=True, text=True, timeout=30,
            )

            if commit.returncode in (0, 1):
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
            local_dirs = {
                "Needs_Action/local": NEEDS_ACTION_LOCAL,
                "In_Progress/local":  IN_PROGRESS_LOCAL,
                "Pending_Approval":   PENDING_APPROVAL,
                "Approved":           APPROVED_DIR,
                "Updates":            UPDATES_DIR,
                "Done/local":         DONE_LOCAL,
            }
            counts = {
                name: len(list(d.glob("*.md"))) if d.exists() else 0
                for name, d in local_dirs.items()
            }
            logger.info(f"[STATUS] services={json.dumps(status)} files={counts} "
                        f"merged={self._updates_merged} executed={self._actions_executed} "
                        f"delegated={self._delegated} errors={self._errors}")
        except Exception as e:
            logger.error(f"Status log failed: {e}")

    def signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Local Executive Orchestrator (Platinum Tier)")
    parser.add_argument("--status", action="store_true", help="Check service status")
    parser.add_argument("--health", action="store_true", help="Run health checks")
    parser.add_argument("--sync", action="store_true", help="Force Git synchronization")
    parser.add_argument("--dry-run", action="store_true", help="Log only, no file moves")
    args = parser.parse_args()

    dry_run = args.dry_run or DRY_RUN
    orchestrator = LocalExecutiveProcessor(dry_run=dry_run)

    if args.status:
        print(f"Local Executive Orchestrator (dry_run={dry_run})")
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
