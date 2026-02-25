#!/usr/bin/env python3
"""
Enhanced Needs Action Watcher (Bronze+ Edition)

Watches data/Needs_Action/ for new .md files and automatically runs the Ralph Wiggum agent.
Also supports data/Inbox/ for future drop-folder style input.
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
VAULT_DIR = Path(__file__).parent.parent.resolve()    # project root (one level up from watcher/)
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "watcher.log"

# Default Ralph command - can be overridden via environment variable
DEFAULT_RALPH_COMMAND = os.environ.get(
    "RALPH_COMMAND", 
    'claude /ralph-loop "Process all files in data/Needs_Action/ using Agent_Core" --max-iterations 30 --completion-promise "TASK_COMPLETE"'
)


# ── LOGGING SETUP ─────────────────────────────────────────────────────────
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("NeedsActionWatcher")


# ── UTILITY FUNCTIONS ─────────────────────────────────────────────────────
def check_claude_available():
    """Check if claude command is available in PATH."""
    try:
        result = subprocess.run(['which', 'claude'], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        try:
            # Alternative check for Windows
            result = subprocess.run(['where', 'claude'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False


def parse_ralph_command(command_str):
    """Parse the Ralph command string into a list for subprocess."""
    # Simple parsing that handles quoted arguments
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
                app_name="AI Employee Vault",
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
    else:
        logger.debug(f"Notification: {title} - {message}")


def cleanup_empty_files(directory):
    """Remove empty .md files from the specified directory."""
    if not directory.exists():
        return
        
    removed_count = 0
    for file_path in directory.glob("*.md"):
        if file_path.stat().st_size == 0:  # File is empty
            try:
                file_path.unlink()
                logger.info(f"Removed empty file: {file_path.name}")
                removed_count += 1
            except Exception as e:
                logger.error(f"Failed to remove empty file {file_path.name}: {e}")
    
    if removed_count > 0:
        logger.info(f"Cleanup completed: removed {removed_count} empty files")


def health_check_loop():
    """Background thread that logs health check messages every 10 minutes."""
    while not stop_event.is_set():
        time.sleep(600)  # Sleep for 10 minutes
        if not stop_event.is_set():  # Double-check after sleep
            logger.info("Watcher alive - health check")


# ── EVENT HANDLER ─────────────────────────────────────────────────────────
class NeedsActionHandler(FileSystemEventHandler):
    def __init__(self, dry_run=False, ralph_command=None, needs_action_dir=None, inbox_dir=None, cleanup_enabled=False):
        self.dry_run = dry_run
        self.ralph_command = ralph_command or DEFAULT_RALPH_COMMAND
        self.needs_action_dir = needs_action_dir
        self.inbox_dir = inbox_dir
        self.cleanup_enabled = cleanup_enabled
        self.parsed_command = parse_ralph_command(self.ralph_command)

    def _matches_dir(self, file_path, target_dir):
        """Compare paths reliably on Windows (case-insensitive, resolved)."""
        if target_dir is None:
            return False
        return file_path.resolve().parent == target_dir.resolve()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == '.md':
            if self._matches_dir(path, self.needs_action_dir):
                logger.info(f"New task file detected in Needs_Action: {path.name}")
                self.trigger_agent(path, "Needs_Action")
            elif self._matches_dir(path, self.inbox_dir):
                logger.info(f"New file detected in Inbox: {path.name}")
                self.trigger_agent(path, "Inbox")

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == '.md':
            if self._matches_dir(path, self.needs_action_dir) or \
               self._matches_dir(path, self.inbox_dir):
                logger.info(f"Task file modified: {path.name}")
                self.trigger_agent(path, "Modified")

    def trigger_agent(self, file_path, source_dir):
        try:
            # Prevent multiple overlapping runs (simple lock)
            lock_file = VAULT_DIR / ".agent_running.lock"
            if lock_file.exists():
                logger.info("Agent already running → skipping")
                return

            if self.dry_run:
                logger.info(f"[DRY RUN] Would process: {file_path.name} from {source_dir}")
                logger.info(f"[DRY RUN] Would run command: {' '.join(self.parsed_command)}")
                return

            lock_file.touch()
            logger.info(f"Starting Ralph Wiggum agent loop for: {file_path.name} from {source_dir}")
            send_notification("Agent Started", f"Processing {file_path.name}")

            # Run claude in a subprocess (non-blocking if you want, but for now we wait)
            result = subprocess.run(
                self.parsed_command,
                cwd=VAULT_DIR,               # important: run from project root
                capture_output=True,
                text=True,
                timeout=3600                 # safety timeout 1 hour
            )

            if result.returncode == 0:
                logger.info("Agent loop completed successfully")
                send_notification("Agent Completed", "Processing completed successfully")
                
                # Perform cleanup if enabled
                if self.cleanup_enabled:
                    logger.info("Performing cleanup of empty files...")
                    cleanup_empty_files(self.needs_action_dir)
                    if self.inbox_dir:
                        cleanup_empty_files(self.inbox_dir)
            else:
                logger.error(f"Agent failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                send_notification("Agent Failed", "Processing failed - check logs")

        except subprocess.TimeoutExpired:
            logger.error("Agent loop timed out after 1h")
            send_notification("Agent Timeout", "Processing timed out after 1 hour")
        except Exception as e:
            logger.exception(f"Error starting agent: {e}")
            send_notification("Agent Error", f"Error occurred: {str(e)[:50]}...")
        finally:
            if lock_file.exists():
                lock_file.unlink()


# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    global logger, stop_event
    
    parser = argparse.ArgumentParser(description="Watch data/Needs_Action/ and data/Inbox/ for new .md files and run Ralph Wiggum agent")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Don't actually run the agent, just log what would happen")
    parser.add_argument("--command", type=str, default=DEFAULT_RALPH_COMMAND,
                       help="Custom command to run instead of default Ralph command")
    parser.add_argument("--dir", type=str, default="data/Needs_Action",
                       help="Directory to watch for new files (default: data/Needs_Action)")
    parser.add_argument("--inbox-dir", type=str, default="data/Inbox",
                       help="Additional directory to watch for new files (default: data/Inbox, set to empty to disable)")
    parser.add_argument("--max-iterations", type=int, default=30,
                       help="Max iterations for the agent (passed to command if applicable)")
    parser.add_argument("--cleanup", action="store_true",
                       help="Enable cleanup of empty .md files after successful agent run")
    parser.add_argument("--check-claude", action="store_true",
                       help="Check if claude is available and exit")
    
    args = parser.parse_args()
    
    logger = setup_logging()
    
    if args.check_claude:
        if check_claude_available():
            print("✓ claude command is available in PATH")
            return 0
        else:
            print("✗ claude command is NOT available in PATH")
            return 1
    
    if not args.dry_run and not check_claude_available():
        logger.error("claude command not found in PATH. Please install claude or check your PATH.")
        sys.exit(1)
    
    # Set up directories
    needs_action_dir = VAULT_DIR / args.dir
    inbox_dir = VAULT_DIR / args.inbox_dir if args.inbox_dir.strip() != "" else None
    
    # Create directories if they don't exist
    needs_action_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created/verified directory: {needs_action_dir}")
    
    if inbox_dir:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created/verified directory: {inbox_dir}")
    
    # Update the command with the max-iterations value if it contains the placeholder
    ralph_command = args.command
    if "--max-iterations" in ralph_command:
        # Replace the existing max-iterations value
        import re
        ralph_command = re.sub(r"--max-iterations\s+\d+", f"--max-iterations {args.max_iterations}", ralph_command)
    else:
        # Add max-iterations to the command
        ralph_command += f" --max-iterations {args.max_iterations}"

    event_handler = NeedsActionHandler(
        dry_run=args.dry_run, 
        ralph_command=ralph_command,
        needs_action_dir=needs_action_dir,
        inbox_dir=inbox_dir,
        cleanup_enabled=args.cleanup
    )
    
    observer = Observer()
    observer.schedule(event_handler, str(needs_action_dir), recursive=False)
    
    # Also watch inbox directory if it exists and is different from needs_action
    if inbox_dir and inbox_dir != needs_action_dir:
        observer.schedule(event_handler, str(inbox_dir), recursive=False)

    # Start health check thread
    stop_event = threading.Event()
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()

    observer.start()

    mode = "DRY RUN" if args.dry_run else "ACTIVE"
    logger.info(f"Started {mode} watching: {needs_action_dir}")
    if inbox_dir:
        logger.info(f"Also watching: {inbox_dir}")
    logger.info(f"Using command: {ralph_command}")
    if args.cleanup:
        logger.info("Cleanup enabled: will remove empty .md files after successful runs")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()  # Signal health thread to stop
        observer.stop()
        logger.info("Watcher stopped by user")
    observer.join()


if __name__ == "__main__":
    main()