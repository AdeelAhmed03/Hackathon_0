#!/usr/bin/env python3
"""
HITL Watcher (Silver Tier)

Watches data/Approved/ for new .md files and triggers the Claude agent
to process approved items via skill-hitl-watcher routing.

Pattern mirrors needs_action_watcher.py with HITL-specific prompt and configuration.
"""
import time
import logging
import subprocess
import sys
import os
import argparse
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("Warning: plyer not installed. Desktop notifications will be disabled.")

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "hitl_watcher.log"
LOCK_FILE = VAULT_DIR / ".hitl_running.lock"
APPROVED_DIR = VAULT_DIR / "data" / "Approved"

# Default check interval (can be overridden via env)
DEFAULT_CHECK_INTERVAL = int(os.environ.get("HITL_CHECK_INTERVAL_SECONDS", "30"))

# HITL-specific Ralph command
DEFAULT_HITL_COMMAND = os.environ.get(
    "HITL_RALPH_COMMAND",
    'claude /ralph-loop "Process all approved files in data/Approved/ using Functional Assistant (agents/agent-functional-assistant.md). '
    'Route each file by its action field via skill-hitl-watcher to the correct execution skill. '
    'For email actions invoke MCP email server. '
    'Update frontmatter with results and move completed files to data/Done/." '
    '--max-iterations 20 --completion-promise "TASK_COMPLETE"'
)


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
    return logging.getLogger("HITLWatcher")


# ── UTILITY FUNCTIONS ─────────────────────────────────────────────────────
def check_claude_available():
    """Check if claude command is available in PATH."""
    try:
        result = subprocess.run(
            ["which", "claude"], capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        try:
            result = subprocess.run(
                ["where", "claude"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False


def parse_command(command_str):
    """Parse a command string into a list for subprocess."""
    import shlex

    try:
        return shlex.split(command_str)
    except ValueError as e:
        logger.error(f"Error parsing command '{command_str}': {e}")
        return []


def send_notification(title, message):
    """Send a desktop notification if plyer is available."""
    if PLYER_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="AI Employee Vault - HITL",
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
    else:
        logger.debug(f"Notification: {title} - {message}")


def has_been_processed(file_path):
    """Check if a file has already been processed (has execution_result in frontmatter)."""
    try:
        content = file_path.read_text(encoding="utf-8")
        # Quick check for execution_result in YAML frontmatter
        if content.startswith("---"):
            frontmatter_end = content.find("---", 3)
            if frontmatter_end != -1:
                frontmatter = content[3:frontmatter_end]
                if "execution_result:" in frontmatter:
                    value = ""
                    for line in frontmatter.split("\n"):
                        if line.strip().startswith("execution_result:"):
                            value = line.split(":", 1)[1].strip()
                            break
                    # If execution_result has a non-empty value, it's been processed
                    if value and value not in ("", "null", "~"):
                        return True
        return False
    except Exception:
        return False


def health_check_loop():
    """Background thread that logs health check messages every 10 minutes."""
    while not stop_event.is_set():
        time.sleep(600)
        if not stop_event.is_set():
            logger.info("HITL Watcher alive - health check")
            # Also log count of files in Approved/
            if APPROVED_DIR.exists():
                md_files = list(APPROVED_DIR.glob("*.md"))
                unprocessed = [f for f in md_files if not has_been_processed(f)]
                logger.info(
                    f"  Approved/ contains {len(md_files)} files "
                    f"({len(unprocessed)} unprocessed)"
                )


# ── EVENT HANDLER ─────────────────────────────────────────────────────────
class ApprovedFileHandler(FileSystemEventHandler):
    """Handles new/moved .md files appearing in data/Approved/."""

    def __init__(self, dry_run=False, command=None):
        self.dry_run = dry_run
        self.command = command or DEFAULT_HITL_COMMAND
        self.parsed_command = parse_command(self.command)

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".md":
            logger.info(f"New approved file detected: {path.name}")
            self._process_file(path)

    def on_moved(self, event):
        """Handle files moved INTO the Approved/ directory."""
        if event.is_directory:
            return
        dest_path = Path(event.dest_path)
        if dest_path.suffix.lower() == ".md":
            # Check if the destination is in our watched directory
            try:
                if dest_path.resolve().parent == APPROVED_DIR.resolve():
                    logger.info(f"File moved to Approved/: {dest_path.name}")
                    self._process_file(dest_path)
            except Exception:
                pass

    def _process_file(self, file_path):
        """Trigger the Claude agent to process an approved file."""
        # Skip already-processed files
        if has_been_processed(file_path):
            logger.info(f"Skipping already-processed file: {file_path.name}")
            return

        # Skip empty files
        try:
            if file_path.stat().st_size == 0:
                logger.warning(f"Skipping empty file: {file_path.name}")
                return
        except FileNotFoundError:
            logger.warning(f"File disappeared before processing: {file_path.name}")
            return

        # Gold Tier: Implement claim-by-move pattern
        # Move the file from Approved to In_Progress/agent-autonomous-employee/ to claim ownership
        in_progress_dir = VAULT_DIR / "data" / "In_Progress" / "agent-autonomous-employee"
        in_progress_dir.mkdir(parents=True, exist_ok=True)

        # Try to claim the file by moving it to In_Progress
        claimed_file_path = in_progress_dir / file_path.name

        if self.dry_run:
            logger.info(f"[DRY RUN] Would claim: {file_path.name} → {claimed_file_path}")
        else:
            try:
                # Attempt to move the file to claim it
                file_path.rename(claimed_file_path)
                logger.info(f"Claimed file: {file_path.name} → {claimed_file_path}")
            except FileNotFoundError:
                # File already moved by another process, so we skip it
                logger.info(f"File {file_path.name} already claimed by another process, skipping")
                return
            except Exception as e:
                logger.error(f"Failed to claim file {file_path.name}: {e}")
                return

        # Check lock to prevent overlapping runs
        if LOCK_FILE.exists():
            logger.info("HITL agent already running - skipping (will catch on next event)")
            return

        # Update command to focus on processing the claimed file in In_Progress
        # This is a simplified approach - in reality the agent would be instructed to focus on In_Progress
        hitl_command_with_claimed_focus = self.command.replace(
            "data/Approved/",
            "data/In_Progress/agent-autonomous-employee/ data/Approved/"
        )
        parsed_claimed_command = parse_command(hitl_command_with_claimed_focus)

        if self.dry_run:
            logger.info(f"[DRY RUN] Would process approved file: {claimed_file_path.name}")
            logger.info(f"[DRY RUN] Would run command: {' '.join(parsed_claimed_command)}")
            return

        try:
            LOCK_FILE.touch()
            logger.info(f"Starting HITL agent for: {claimed_file_path.name}")
            send_notification("HITL Agent Started", f"Processing approved: {claimed_file_path.name}")

            result = subprocess.run(
                parsed_claimed_command,
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minute safety timeout
            )

            if result.returncode == 0:
                logger.info(f"HITL agent completed successfully for: {claimed_file_path.name}")
                send_notification(
                    "HITL Completed", f"Processed: {claimed_file_path.name}"
                )
            else:
                logger.error(
                    f"HITL agent failed for {claimed_file_path.name}:\n"
                    f"STDOUT: {result.stdout[:500]}\n"
                    f"STDERR: {result.stderr[:500]}"
                )
                send_notification("HITL Failed", f"Failed: {claimed_file_path.name} - check logs")

        except subprocess.TimeoutExpired:
            logger.error(f"HITL agent timed out for: {claimed_file_path.name}")
            send_notification("HITL Timeout", f"Timed out: {claimed_file_path.name}")
        except Exception as e:
            logger.exception(f"Error in HITL agent for {claimed_file_path.name}: {e}")
            send_notification("HITL Error", f"Error: {str(e)[:50]}...")
        finally:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    global logger, stop_event

    parser = argparse.ArgumentParser(
        description="Watch data/Approved/ for human-approved .md files and trigger HITL agent processing"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually run the agent, just log what would happen",
    )
    parser.add_argument(
        "--command",
        type=str,
        default=DEFAULT_HITL_COMMAND,
        help="Custom command to run instead of default HITL command",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="data/Approved",
        help="Directory to watch for approved files (default: data/Approved)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Max iterations for the HITL agent (default: 20)",
    )
    parser.add_argument(
        "--check-claude",
        action="store_true",
        help="Check if claude is available and exit",
    )

    args = parser.parse_args()

    logger = setup_logging()

    if args.check_claude:
        if check_claude_available():
            print("claude command is available in PATH")
            return 0
        else:
            print("claude command is NOT available in PATH")
            return 1

    if not args.dry_run and not check_claude_available():
        logger.error(
            "claude command not found in PATH. Please install claude or check your PATH."
        )
        sys.exit(1)

    # Set up directory
    approved_dir = VAULT_DIR / args.dir
    approved_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/verified directory: {approved_dir}")

    # Update command with max-iterations
    hitl_command = args.command
    if "--max-iterations" in hitl_command:
        import re

        hitl_command = re.sub(
            r"--max-iterations\s+\d+",
            f"--max-iterations {args.max_iterations}",
            hitl_command,
        )
    else:
        hitl_command += f" --max-iterations {args.max_iterations}"

    event_handler = ApprovedFileHandler(dry_run=args.dry_run, command=hitl_command)

    observer = Observer()
    observer.schedule(event_handler, str(approved_dir), recursive=False)

    # Start health check thread
    stop_event = threading.Event()
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()

    observer.start()

    mode = "DRY RUN" if args.dry_run else "ACTIVE"
    logger.info(f"Started HITL Watcher ({mode})")
    logger.info(f"Watching: {approved_dir}")
    logger.info(f"Using command: {hitl_command}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        observer.stop()
        logger.info("HITL Watcher stopped by user")
    observer.join()


if __name__ == "__main__":
    main()
