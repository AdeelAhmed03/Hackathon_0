#!/usr/bin/env python3
"""
Git Sync Handler — Platinum Tier

Synchronizes cloud and local vault systems via Git.
Syncs only /data/ directory (markdown/state files), excludes secrets.
Implements claim-by-move conflict detection and proper synchronization flow.

Phase 1: Git-based synchronization (recommended over Syncthing)
"""

import os
import sys
import time
import logging
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import tempfile
import shutil

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
SYNC_LOG_FILE = LOG_DIR / "git_sync.log"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - GitSync - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(SYNC_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("GitSync")

class GitSyncHandler:
    """Handles Git synchronization between cloud and local systems."""

    def __init__(self, is_cloud: bool = False):
        self.is_cloud = is_cloud
        self.vault_dir = VAULT_DIR
        self.data_dir = self.vault_dir / "data"
        self.in_progress_dirs = [
            self.data_dir / "In_Progress" / "cloud",
            self.data_dir / "In_Progress" / "local"
        ]
        self.sync_interval = 900  # 15 minutes default
        self.max_conflict_time = 300  # 5 minutes to resolve conflicts

    def is_file_in_progress_by_other(self, file_path: Path) -> bool:
        """
        Check if a file is already in progress by the other system.
        Implements claim-by-move conflict detection.
        """
        if not file_path.exists():
            return False

        # Determine the opposite progress directory
        other_progress_dir = self.data_dir / "In_Progress" / ("local" if self.is_cloud else "cloud")

        if not other_progress_dir.exists():
            return False

        # Check if there's a file with the same name in the other progress directory
        for other_file in other_progress_dir.rglob("*"):
            if other_file.is_file() and other_file.name == file_path.name:
                logger.warning(f"File {file_path.name} already in progress by other system")
                return True

        return False

    def check_git_status(self) -> Tuple[bool, str]:
        """Check if Git repository is in a good state."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("Git status check timed out")
            return False, "timeout"
        except Exception as e:
            logger.error(f"Git status check failed: {e}")
            return False, str(e)

    def pull_from_remote(self) -> bool:
        """Pull latest changes from remote repository."""
        try:
            logger.info("Starting git pull from remote")

            # First, check if there are any uncommitted changes that might conflict
            has_changes, changes = self.check_git_status()
            if changes:
                logger.warning(f"Uncommitted changes before pull: {changes}")

            # Try to pull with rebase to avoid merge commits
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("Git pull successful")
                return True
            else:
                # Check if it's a merge conflict
                if "CONFLICT" in result.stdout or "CONFLICT" in result.stderr:
                    logger.warning(f"Git pull conflict detected: {result.stderr}")
                    self.flag_conflict_for_manual_resolution()
                    return False
                else:
                    logger.error(f"Git pull failed: {result.stderr}")
                    return False

        except subprocess.TimeoutExpired:
            logger.error("Git pull timed out")
            return False
        except Exception as e:
            logger.error(f"Git pull failed: {e}")
            return False

    def push_to_remote(self) -> bool:
        """Push local changes to remote repository."""
        try:
            logger.info("Starting git push to remote")

            # Add all data directory changes (excluding what's in .gitignore)
            add_result = subprocess.run(
                ["git", "add", str(self.data_dir)],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if add_result.returncode != 0:
                logger.warning(f"Git add failed: {add_result.stderr}")
                # Continue anyway, as there might be no changes to add

            # Check if there are any changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=10
            )

            if not status_result.stdout.strip():
                logger.info("No changes to commit")
                return True

            # Create commit
            commit_result = subprocess.run(
                ["git", "commit", "-m", f"{'Cloud' if self.is_cloud else 'Local'} sync - {datetime.now().isoformat()}"],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if commit_result.returncode not in [0, 1]:  # 1 means nothing to commit (already checked)
                logger.error(f"Git commit failed: {commit_result.stderr}")
                return False

            # Push changes
            push_result = subprocess.run(
                ["git", "push"],
                cwd=self.vault_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            if push_result.returncode == 0:
                logger.info("Git push successful")
                return True
            else:
                logger.error(f"Git push failed: {push_result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Git push timed out")
            return False
        except Exception as e:
            logger.error(f"Git push failed: {e}")
            return False

    def flag_conflict_for_manual_resolution(self):
        """Create a conflict alert file for manual resolution."""
        try:
            conflicts_dir = self.data_dir / "Needs_Action"
            conflict_file = conflicts_dir / f"SYNC_CONFLICT_{int(time.time())}.md"

            conflicts_dir.mkdir(parents=True, exist_ok=True)

            conflict_content = f"""---
type: sync_conflict
severity: high
timestamp: {datetime.now().isoformat()}
---

## Git Sync Conflict Alert

**Time**: {datetime.now().isoformat()}
**System**: {'Cloud' if self.is_cloud else 'Local'}

### Issue
Git synchronization conflict detected during {'pull' if self.is_cloud else 'push'} operation.

### Manual Resolution Required
A human operator needs to:
1. Check git status manually: `cd {self.vault_dir} && git status`
2. Resolve conflicts if any
3. Commit and push changes
4. Remove this conflict notification file when resolved

### Recent Changes
Check `git log --oneline -5` to see recent commits that may have caused the conflict.
"""

            with open(conflict_file, 'w', encoding='utf-8') as f:
                f.write(conflict_content)

            logger.warning(f"Created conflict alert file: {conflict_file.name}")

        except Exception as e:
            logger.error(f"Failed to create conflict alert file: {e}")

    def sync_data_directory(self) -> bool:
        """Synchronize the data directory with remote."""
        try:
            logger.info(f"Starting {'cloud' if self.is_cloud else 'local'} sync operation")

            # For cloud: pull first, then push
            if self.is_cloud:
                if not self.pull_from_remote():
                    logger.error("Failed to pull from remote, skipping push")
                    return False
                return self.push_to_remote()
            # For local: pull only (cloud handles pushing)
            else:
                return self.pull_from_remote()

        except Exception as e:
            logger.error(f"Sync operation failed: {e}")
            return False

    def run_sync_cycle(self) -> bool:
        """Run a single synchronization cycle."""
        try:
            logger.info("Starting sync cycle")

            # Check for any files currently in progress by other system
            in_progress_files = []
            for progress_dir in self.in_progress_dirs:
                if progress_dir.exists():
                    for file_path in progress_dir.rglob("*"):
                        if file_path.is_file():
                            in_progress_files.append(file_path)

            if in_progress_files:
                logger.info(f"Found {len(in_progress_files)} files in progress by other system")

            # Perform synchronization
            success = self.sync_data_directory()

            if success:
                logger.info("Sync cycle completed successfully")
            else:
                logger.error("Sync cycle failed")

            return success

        except Exception as e:
            logger.error(f"Sync cycle failed with exception: {e}")
            return False

    def check_sync_status(self) -> Dict[str, any]:
        """Check current sync status and return status information."""
        try:
            status = {
                "timestamp": datetime.now().isoformat(),
                "is_cloud": self.is_cloud,
                "last_sync_attempt": None,
                "last_sync_success": None,
                "git_status": "unknown",
                "conflicts": [],
                "in_progress_files": []
            }

            # Check git status
            is_git_ok, git_output = self.check_git_status()
            status["git_status"] = "clean" if git_output == "" else "modified"

            # Check for conflict files
            needs_action_dir = self.data_dir / "Needs_Action"
            if needs_action_dir.exists():
                for file_path in needs_action_dir.glob("SYNC_CONFLICT_*.md"):
                    status["conflicts"].append(file_path.name)

            # Check for in-progress files
            for progress_dir in self.in_progress_dirs:
                if progress_dir.exists():
                    for file_path in progress_dir.rglob("*"):
                        if file_path.is_file():
                            status["in_progress_files"].append(str(file_path.relative_to(self.vault_dir)))

            return status

        except Exception as e:
            logger.error(f"Failed to check sync status: {e}")
            return {"error": str(e)}

    def run_daemon(self, interval: int = None):
        """Run the sync daemon in background mode."""
        if interval is None:
            interval = self.sync_interval

        logger.info(f"Starting sync daemon (interval: {interval}s, is_cloud: {self.is_cloud})")

        while True:
            try:
                success = self.run_sync_cycle()

                if not success:
                    logger.warning("Sync failed, will retry after interval")

                # Wait for interval before next sync
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Sync daemon interrupted by user")
                break
            except Exception as e:
                logger.error(f"Sync daemon error: {e}")
                time.sleep(60)  # Wait 1 minute before retry on error

def main():
    """Main entry point for git sync handler."""
    import argparse

    parser = argparse.ArgumentParser(description="Git Sync Handler for Platinum Tier")
    parser.add_argument("--cloud", action="store_true", help="Run as cloud sync (pull then push)")
    parser.add_argument("--local", action="store_true", help="Run as local sync (pull only)")
    parser.add_argument("--one-time", action="store_true", help="Run sync once then exit")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous daemon")
    parser.add_argument("--status", action="store_true", help="Check sync status")
    parser.add_argument("--interval", type=int, default=900, help="Sync interval in seconds (for daemon mode)")
    parser.add_argument("--test-mode", action="store_true", help="Test mode (no actual sync)")

    args = parser.parse_args()

    # Determine if running as cloud or local
    if args.cloud:
        is_cloud = True
    elif args.local:
        is_cloud = False
    else:
        # Auto-detect: if we're in a cloud-specific environment, assume cloud
        is_cloud = os.environ.get('VAULT_ENVIRONMENT', '').lower() == 'cloud'

    sync_handler = GitSyncHandler(is_cloud=is_cloud)

    if args.status:
        status = sync_handler.check_sync_status()
        print("Sync Status:")
        print(json.dumps(status, indent=2))
        return

    if args.test_mode:
        logger.setLevel(logging.DEBUG)
        logger.info("Running in test mode")
        # Test basic functionality
        is_git_ok, git_output = sync_handler.check_git_status()
        print(f"Git status check: {'OK' if is_git_ok else 'Failed'}")
        print(f"Git output: {git_output}")
        return

    if args.one_time:
        success = sync_handler.run_sync_cycle()
        logger.info(f"One-time sync {'completed' if success else 'failed'}")
        sys.exit(0 if success else 1)
    elif args.daemon:
        sync_handler.run_daemon(interval=args.interval)
    else:
        # Default: run one sync cycle
        success = sync_handler.run_sync_cycle()
        logger.info(f"Sync {'completed' if success else 'failed'}")
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()