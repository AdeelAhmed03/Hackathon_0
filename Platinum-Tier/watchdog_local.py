#!/usr/bin/env python3
"""
Local Executive Watchdog — Platinum Tier

Process supervisor for Local Executive agent that ensures continuous operation.
Monitors Local Executive process, restarts failed instances, and handles system health.

Usage:
    python watchdog_local.py              # Start watchdog supervisor
    python watchdog_local.py --status    # Check supervisor status
    python watchdog_local.py --stop      # Stop all processes
"""

import os
import sys
import time
import signal
import subprocess
import threading
import logging
from pathlib import Path
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
WATCHDOG_LOG_FILE = LOG_DIR / "local_watchdog.log"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - LocalWatchdog - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(WATCHDOG_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("LocalWatchdog")

# ── LOCAL EXECUTIVE WATCHDOG ──────────────────────────────────────────────
class LocalWatchdog:
    """Supervisor for Local Executive processes."""

    def __init__(self):
        self.local_executive_process = None
        self.running = False
        self.restart_count = 0
        self.max_restarts = 5  # Max restart attempts
        self.restart_window = 300  # Time window for restart limit (5 minutes)

    def start_local_executive(self):
        """Start Local Executive process."""
        try:
            # Check if process is already running
            if self.local_executive_process and self.local_executive_process.poll() is None:
                logger.warning("Local Executive already running")
                return False

            # Start the Local Executive agent
            cmd = [sys.executable, str(VAULT_DIR / "agents" / "agent-local-executive.py")]
            self.local_executive_process = subprocess.Popen(
                cmd,
                cwd=VAULT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy()
            )

            logger.info(f"Started Local Executive process (PID: {self.local_executive_process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to start Local Executive: {e}")
            return False

    def monitor_processes(self):
        """Monitor Local Executive process and restart if needed."""
        while self.running:
            try:
                if self.local_executive_process:
                    # Check if process is still alive
                    if self.local_executive_process.poll() is not None:
                        # Process died, handle restart
                        logger.warning("Local Executive process terminated unexpectedly")

                        # Check restart limits
                        if self.restart_count < self.max_restarts:
                            self.restart_count += 1
                            logger.info(f"Restarting Local Executive (attempt {self.restart_count}/{self.max_restarts})")

                            # Wait before restart
                            time.sleep(5)

                            if not self.start_local_executive():
                                logger.error("Failed to restart Local Executive")
                        else:
                            logger.error(f"Local Executive restart limit exceeded ({self.max_restarts})")
                            break

                # Small delay to prevent busy-waiting
                time.sleep(10)

            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                time.sleep(10)

    def get_status(self):
        """Get current watchdog and process status."""
        status = {
            "watchdog_running": self.running,
            "local_executive_pid": None,
            "local_executive_running": False,
            "restart_count": self.restart_count
        }

        if self.local_executive_process:
            is_running = self.local_executive_process.poll() is None
            status["local_executive_running"] = is_running
            if is_running:
                status["local_executive_pid"] = self.local_executive_process.pid

        return status

    def start(self):
        """Start the watchdog supervisor."""
        logger.info("Starting Local Executive Watchdog (Platinum Tier)")

        if not self.start_local_executive():
            logger.error("Failed to start Local Executive, watchdog stopping")
            return False

        self.running = True
        self.restart_count = 0

        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_processes, daemon=True)
        monitor_thread.start()

        logger.info("Local Executive Watchdog started successfully")
        return True

    def stop(self):
        """Stop the watchdog and all managed processes."""
        logger.info("Stopping Local Executive Watchdog")

        self.running = False

        # Terminate Local Executive process if running
        if self.local_executive_process:
            try:
                self.local_executive_process.terminate()
                try:
                    self.local_executive_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.local_executive_process.kill()
                    self.local_executive_process.wait()

                logger.info("Local Executive process terminated")
            except Exception as e:
                logger.error(f"Error terminating Local Executive: {e}")

        logger.info("Local Executive Watchdog stopped")

def signal_handler(signum, frame, watchdog):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    watchdog.stop()
    sys.exit(0)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local Executive Watchdog (Platinum Tier)")
    parser.add_argument("--status", action="store_true", help="Check watchdog status")
    parser.add_argument("--stop", action="store_true", help="Stop watchdog supervisor")
    parser.add_argument("--restart", action="store_true", help="Restart Local Executive")
    args = parser.parse_args()

    watchdog = LocalWatchdog()

    # Set up signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, watchdog))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, watchdog))

    if args.status:
        status = watchdog.get_status()
        print("Local Executive Watchdog Status:")
        print(f"  Watchdog Running: {status['watchdog_running']}")
        print(f"  Local Executive Running: {status['local_executive_running']}")
        print(f"  Local Executive PID: {status['local_executive_pid']}")
        print(f"  Restart Count: {status['restart_count']}")
        return

    elif args.stop:
        watchdog.stop()
        print("Local Executive Watchdog stopped")
        return

    elif args.restart:
        watchdog.stop()
        time.sleep(2)
        if not watchdog.start():
            print("Failed to restart Local Executive Watchdog")
            sys.exit(1)
        print("Local Executive Watchdog restarted")
        return

    # Main operation
    if not watchdog.start():
        print("Failed to start Local Executive Watchdog")
        sys.exit(1)

    try:
        # Keep main thread alive
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        watchdog.stop()

if __name__ == "__main__":
    main()