#!/usr/bin/env python3
"""
Cloud Sync Watcher — Platinum Tier

Watches for changes in the cloud system and handles Git synchronization
between cloud and local systems. Part of the Cloud Executive service suite.

This watcher monitors:
- Cloud task completions that need to be synced to local
- Local updates that need to be processed on cloud
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
CLOUD_SYNC_WATCHER_LOG_FILE = LOG_DIR / "cloud_sync_watcher.log"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - CloudSyncWatcher - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(CLOUD_SYNC_WATCHER_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("CloudSyncWatcher")

# ── CLOUD SYNC WATCHER ────────────────────────────────────────────────────
class CloudSyncWatcher:
    """Watches for cloud synchronization needs and handles Git operations."""

    def __init__(self):
        self.running = False
        self.last_sync_time = 0
        self.sync_interval = 900  # 15 minutes between syncs
        self.active = True

    def run_sync_cycle(self):
        """Execute a single sync cycle."""
        try:
            logger.info("Starting cloud sync cycle")

            # Check if enough time has passed since last sync
            current_time = time.time()
            if current_time - self.last_sync_time < self.sync_interval:
                logger.debug("Sync interval not reached, skipping cycle")
                return

            # Pull any local updates first
            logger.info("Pulling local updates...")
            self.pull_local_updates()

            # Process any local updates that were pulled
            logger.info("Processing local updates...")
            self.process_local_updates()

            # Push cloud changes to local
            logger.info("Pushing cloud changes...")
            self.push_cloud_changes()

            # Update last sync time
            self.last_sync_time = current_time
            logger.info("Completed sync cycle successfully")

        except Exception as e:
            logger.error(f"Error in sync cycle: {e}")
            # Continue running despite individual errors

    def pull_local_updates(self):
        """Pull updates from local via Git."""
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

    def process_local_updates(self):
        """Process any updates received from local."""
        try:
            # Process any approval files that came from local
            approved_dir = VAULT_DIR / "data" / "Approved"
            if not approved_dir.exists():
                logger.debug("No Approved directory found")
                return

            approved_files = list(approved_dir.glob("*.md"))
            if not approved_files:
                logger.debug("No approved files to process")
                return

            logger.info(f"Found {len(approved_files)} approved files to process")

            for approved_file in approved_files:
                try:
                    self.process_approved_file(approved_file)

                    # Move processed file to Done/cloud/
                    done_dir = VAULT_DIR / "data" / "Done" / "cloud"
                    done_dir.mkdir(parents=True, exist_ok=True)
                    done_file = done_dir / f"executed_{approved_file.name}"

                    # Process the approved action (in real implementation)
                    logger.info(f"Processed approved file: {approved_file.name}")
                    approved_file.rename(done_file)

                except Exception as e:
                    logger.error(f"Error processing approved file {approved_file.name}: {e}")

        except Exception as e:
            logger.error(f"Error in process_local_updates: {e}")

    def process_approved_file(self, approved_file: Path):
        """Process a single approved file from local."""
        try:
            logger.info(f"Processing approved file: {approved_file.name}")

            # Read the approved file
            with open(approved_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # In a real implementation, this would execute the approved action
            # but in a draft-only mode for cloud (not actual execution)
            logger.info(f"Would execute approved action from: {approved_file.name}")

        except Exception as e:
            logger.error(f"Error processing approved file {approved_file.name}: {e}")

    def push_cloud_changes(self):
        """Push cloud changes to local via Git."""
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
                ["git", "commit", "-m", f"Cloud sync - {datetime.now().isoformat()}"],
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
            logger.error(f"Error in push_cloud_changes: {e}")

    def start(self):
        """Start the sync watcher."""
        logger.info("Starting Cloud Sync Watcher (Platinum Tier)")
        logger.info("Monitoring for cloud/local synchronization needs")

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
        logger.info("Stopping Cloud Sync Watcher")
        self.running = False

def main():
    """Main entry point for cloud sync watcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Cloud Sync Watcher (Platinum Tier)")
    parser.add_argument("--single-run", action="store_true", help="Run one sync cycle then exit")
    args = parser.parse_args()

    watcher = CloudSyncWatcher()

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