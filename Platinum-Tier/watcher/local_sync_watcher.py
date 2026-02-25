#!/usr/bin/env python3
"""
Local Sync Watcher — Platinum Tier

Watches for changes in the local system and handles Git synchronization
between local and cloud systems. Part of the Local Executive service suite.

This watcher monitors:
- Local task completions that need to be synced to cloud
- Cloud updates that need to be merged locally
- Dashboard changes that should be propagated
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import subprocess
from typing import Dict, List, Optional

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
LOCAL_SYNC_WATCHER_LOG_FILE = LOG_DIR / "local_sync_watcher.log"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - LocalSyncWatcher - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOCAL_SYNC_WATCHER_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("LocalSyncWatcher")

# ── LOCAL SYNC WATCHER ────────────────────────────────────────────────────
class LocalSyncWatcher:
    """Watches for local synchronization needs and handles Git operations."""

    def __init__(self):
        self.running = False
        self.last_sync_time = 0
        self.sync_interval = 600  # 10 minutes between syncs
        self.active = True

    def run_sync_cycle(self):
        """Execute a single sync cycle."""
        try:
            logger.info("Starting local sync cycle")

            # Check if enough time has passed since last sync
            current_time = time.time()
            if current_time - self.last_sync_time < self.sync_interval:
                logger.debug("Sync interval not reached, skipping cycle")
                return

            # Pull any cloud updates first
            logger.info("Pulling cloud updates...")
            self.pull_cloud_updates()

            # Process any cloud updates that were pulled
            logger.info("Processing cloud updates...")
            self.process_cloud_updates()

            # Push local changes to cloud
            logger.info("Pushing local changes...")
            self.push_local_changes()

            # Update last sync time
            self.last_sync_time = current_time
            logger.info("Completed sync cycle successfully")

        except Exception as e:
            logger.error(f"Error in sync cycle: {e}")
            # Continue running despite individual errors

    def pull_cloud_updates(self):
        """Pull updates from cloud via Git."""
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("Git pull successful")
            else:
                logger.warning(f"Git pull failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            logger.error("Git pull timed out")
        except Exception as e:
            logger.error(f"Git pull error: {e}")

    def process_cloud_updates(self):
        """Process any updates received from cloud."""
        try:
            updates_dir = VAULT_DIR / "data" / "Updates"
            if not updates_dir.exists():
                logger.debug("No Updates directory found")
                return

            update_files = list(updates_dir.glob("*.md"))
            if not update_files:
                logger.debug("No update files to process")
                return

            logger.info(f"Processing {len(update_files)} cloud update files")

            for update_file in update_files:
                try:
                    self.process_single_update(update_file)

                    # Move processed update to Done/local/
                    done_dir = VAULT_DIR / "data" / "Done" / "local"
                    done_dir.mkdir(parents=True, exist_ok=True)
                    done_file = done_dir / f"processed_{update_file.name}"

                    # First try to process the update, then move it
                    update_file.rename(done_file)
                    logger.info(f"Processed and moved update: {update_file.name}")

                except Exception as e:
                    logger.error(f"Error processing update {update_file.name}: {e}")

        except Exception as e:
            logger.error(f"Error in process_cloud_updates: {e}")

    def process_single_update(self, update_file: Path):
        """Process a single update file from cloud."""
        try:
            # This would use the merge-updater skill in a full implementation
            logger.info(f"Processing cloud update file: {update_file.name}")

            # Read the update file
            with open(update_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Merge into local dashboard
            self.merge_to_dashboard(content, update_file.name)

        except Exception as e:
            logger.error(f"Error processing update file {update_file.name}: {e}")

    def merge_to_dashboard(self, update_content: str, update_source: str):
        """Merge update content into local dashboard."""
        try:
            dashboard_path = VAULT_DIR / "data" / "Dashboard.md"

            # Read current dashboard
            current_content = ""
            if dashboard_path.exists():
                with open(dashboard_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()

            # Create timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Add update to existing content
            if current_content:
                updated_content = current_content + f"\n\n## Update from {update_source}\n- Merged: {timestamp}\n"
            else:
                updated_content = f"# Dashboard - Local System\n\n## Update from {update_source}\n- Merged: {timestamp}\n"

            # Write back to dashboard
            with open(dashboard_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            logger.info(f"Successfully merged update {update_source} to dashboard")

        except Exception as e:
            logger.error(f"Error merging update to dashboard: {e}")

    def push_local_changes(self):
        """Push local changes to cloud via Git."""
        try:
            # Add all changes
            add_result = subprocess.run(
                ["git", "add", "."],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )

            if add_result.returncode != 0:
                logger.warning(f"Git add failed: {add_result.stderr}")
                return

            # Commit changes if there are any
            commit_result = subprocess.run(
                ["git", "commit", "-m", f"Local sync - {datetime.now().isoformat()}"],
                cwd=VAULT_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )

            if commit_result.returncode in [0, 1]:  # 1 means nothing to commit
                if commit_result.returncode == 0:
                    # Push changes
                    push_result = subprocess.run(
                        ["git", "push"],
                        cwd=VAULT_DIR,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )

                    if push_result.returncode == 0:
                        logger.info("Git push successful")
                    else:
                        logger.warning(f"Git push failed: {push_result.stderr}")
                else:
                    logger.info("No changes to commit")
            else:
                logger.warning(f"Git commit failed: {commit_result.stderr}")

        except Exception as e:
            logger.error(f"Error in push_local_changes: {e}")

    def start(self):
        """Start the sync watcher."""
        logger.info("Starting Local Sync Watcher (Platinum Tier)")
        logger.info("Monitoring for local/cloud synchronization needs")

        self.running = True

        while self.running:
            try:
                if self.active:
                    self.run_sync_cycle()

                # Sleep between cycles
                time.sleep(30)  # Check every 30 seconds for sync opportunities

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)  # Brief pause before continuing

    def stop(self):
        """Stop the sync watcher."""
        logger.info("Stopping Local Sync Watcher")
        self.running = False

def main():
    """Main entry point for local sync watcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Local Sync Watcher (Platinum Tier)")
    parser.add_argument("--single-run", action="store_true", help="Run one sync cycle then exit")
    args = parser.parse_args()

    watcher = LocalSyncWatcher()

    if args.single_run:
        logger.info("Running single sync cycle")
        try:
            watcher.run_sync_cycle()
            logger.info("Single sync cycle completed")
        except Exception as e:
            logger.error(f"Error in single sync cycle: {e}")
            sys.exit(1)
    else:
        # Continuous operation
        try:
            watcher.start()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            watcher.stop()

if __name__ == "__main__":
    main()