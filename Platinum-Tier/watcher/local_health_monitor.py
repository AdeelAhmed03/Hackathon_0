#!/usr/bin/env python3
"""
Local Health Monitor — Platinum Tier

Monitors the health and performance of the local system and services.
Part of the Local Executive service suite. Reports system status and
alerts on issues affecting local operations.

This monitor checks:
- System resources (CPU, memory, disk)
- Service availability
- Performance metrics
- Dashboard accessibility
"""

import os
import sys
import time
import logging
import psutil
import subprocess
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Optional, Any

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
LOCAL_HEALTH_MONITOR_LOG_FILE = LOG_DIR / "local_health_monitor.log"
HEALTH_STATUS_FILE = VAULT_DIR / "data" / "local_health_status.json"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - LocalHealthMonitor - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOCAL_HEALTH_MONITOR_LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("LocalHealthMonitor")

# ── LOCAL HEALTH MONITOR ──────────────────────────────────────────────────
class LocalHealthMonitor:
    """Monitors health and performance of local system and services."""

    def __init__(self):
        self.running = False
        self.last_check_time = 0
        self.check_interval = 300  # 5 minutes between checks
        self.active = True
        self.heartbeat_file = VAULT_DIR / "data" / "local_heartbeat.json"

    def run_health_check(self):
        """Execute a comprehensive health check."""
        try:
            logger.info("Starting local health check")

            # Check system resources
            system_health = self.check_system_resources()

            # Check service availability
            service_health = self.check_service_availability()

            # Check file system integrity
            fs_health = self.check_file_system()

            # Combine all health metrics
            overall_health = self.combine_health_metrics(system_health, service_health, fs_health)

            # Log health status
            self.log_health_status(overall_health)

            # Write health status to file
            self.write_health_status(overall_health)

            # Create dashboard update if needed
            self.create_dashboard_update(overall_health)

            logger.info("Completed health check successfully")

        except Exception as e:
            logger.error(f"Error in health check: {e}")
            # Continue running despite individual errors

    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource utilization."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage(str(VAULT_DIR))
            disk_percent = (disk.used / disk.total) * 100

            # Network I/O (for monitoring connectivity)
            net_io = psutil.net_io_counters()

            health_status = {
                "cpu": {
                    "percent": cpu_percent,
                    "status": "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 90 else "critical"
                },
                "memory": {
                    "percent": memory_percent,
                    "available_gb": round(memory.available / (1024**3), 2),
                    "status": "healthy" if memory_percent < 80 else "warning" if memory_percent < 90 else "critical"
                },
                "disk": {
                    "percent": disk_percent,
                    "free_gb": round(disk.free / (1024**3), 2),
                    "status": "healthy" if disk_percent < 80 else "warning" if disk_percent < 90 else "critical"
                },
                "timestamp": datetime.now().isoformat()
            }

            # Log system metrics
            logger.info(f"System health - CPU: {cpu_percent}%, Memory: {memory_percent}%, Disk: {disk_percent}%")

            return health_status

        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return {
                "cpu": {"percent": 0, "status": "unknown"},
                "memory": {"percent": 0, "available_gb": 0, "status": "unknown"},
                "disk": {"percent": 0, "free_gb": 0, "status": "unknown"},
                "timestamp": datetime.now().isoformat()
            }

    def check_service_availability(self) -> Dict[str, Any]:
        """Check availability of critical local services."""
        try:
            services_status = {}

            # Check if key directories exist
            critical_dirs = [
                "data/Needs_Action/local",
                "data/Pending_Approval/local",
                "data/Approved",
                "data/Done/local",
                "data/Updates",
                "data/Logs"
            ]

            for dir_path in critical_dirs:
                full_path = VAULT_DIR / dir_path
                services_status[f"{dir_path.replace('/', '_')}_access"] = {
                    "accessible": full_path.exists(),
                    "status": "healthy" if full_path.exists() else "critical"
                }

            # Check MCP servers accessibility (if running)
            mcp_servers = ["email-mcp", "odoo-mcp", "social-mcp"]
            for server in mcp_servers:
                try:
                    # Try to ping the MCP server
                    ping_result = subprocess.run(
                        ["python", "-c", f"import socket; s=socket.socket(); s.connect(('localhost', 8000)); s.close()"],
                        cwd=VAULT_DIR,
                        capture_output=True,
                        timeout=5
                    )
                    services_status[f"{server}_status"] = {
                        "accessible": ping_result.returncode == 0,
                        "status": "healthy" if ping_result.returncode == 0 else "critical"
                    }
                except:
                    services_status[f"{server}_status"] = {
                        "accessible": False,
                        "status": "critical"
                    }

            logger.info(f"Checked {len(services_status)} services")
            return services_status

        except Exception as e:
            logger.error(f"Error checking service availability: {e}")
            return {}

    def check_file_system(self) -> Dict[str, Any]:
        """Check file system integrity and access."""
        try:
            fs_status = {}

            # Check key files and directories
            check_paths = [
                "data/Dashboard.md",
                "data/.gitkeep",
                "agents/",
                "skills/",
                "watcher/"
            ]

            for path in check_paths:
                full_path = VAULT_DIR / path
                if path.endswith("/"):
                    # Directory
                    fs_status[f"dir_{path.rstrip('/')}"] = {
                        "exists": full_path.exists(),
                        "writable": full_path.exists() and os.access(full_path, os.W_OK) if full_path.exists() else False,
                        "status": "healthy" if full_path.exists() and os.access(full_path, os.W_OK) if full_path.exists() else False else "critical"
                    }
                else:
                    # File
                    fs_status[f"file_{path.replace('/', '_')}"] = {
                        "exists": full_path.exists(),
                        "readable": full_path.exists() and os.access(full_path, os.R_OK) if full_path.exists() else False,
                        "writable": full_path.exists() and os.access(full_path, os.W_OK) if full_path.exists() else False,
                        "status": "healthy" if full_path.exists() and os.access(full_path, os.W_OK) if full_path.exists() else False else "critical"
                    }

            logger.info(f"Checked {len(fs_status)} file system items")
            return fs_status

        except Exception as e:
            logger.error(f"Error checking file system: {e}")
            return {}

    def combine_health_metrics(self, system_health: Dict, service_health: Dict, fs_health: Dict) -> Dict[str, Any]:
        """Combine all health metrics into overall status."""
        try:
            # Determine overall health status
            all_health_items = []

            # Add system health items
            for key, value in system_health.items():
                if isinstance(value, dict) and "status" in value:
                    all_health_items.append(value["status"])

            # Add service health items
            for key, value in service_health.items():
                if isinstance(value, dict) and "status" in value:
                    all_health_items.append(value["status"])

            # Add file system health items
            for key, value in fs_health.items():
                if isinstance(value, dict) and "status" in value:
                    all_health_items.append(value["status"])

            # Determine overall status
            if "critical" in all_health_items:
                overall_status = "critical"
            elif "warning" in all_health_items:
                overall_status = "warning"
            else:
                overall_status = "healthy"

            combined_health = {
                "overall_status": overall_status,
                "timestamp": datetime.now().isoformat(),
                "system_health": system_health,
                "service_health": service_health,
                "file_system_health": fs_health,
                "summary": {
                    "critical_count": all_health_items.count("critical"),
                    "warning_count": all_health_items.count("warning"),
                    "healthy_count": all_health_items.count("healthy"),
                    "total_items": len(all_health_items)
                }
            }

            return combined_health

        except Exception as e:
            logger.error(f"Error combining health metrics: {e}")
            return {
                "overall_status": "unknown",
                "timestamp": datetime.now().isoformat(),
                "system_health": system_health,
                "service_health": service_health,
                "file_system_health": fs_health,
                "summary": {"critical_count": 0, "warning_count": 0, "healthy_count": 0, "total_items": 0}
            }

    def log_health_status(self, health_data: Dict[str, Any]):
        """Log health status to file."""
        try:
            # Log overall status
            overall_status = health_data.get("overall_status", "unknown")
            summary = health_data.get("summary", {})

            logger.info(f"Health status: {overall_status}")
            logger.info(f"Health summary: {summary.get('critical_count', 0)} critical, "
                       f"{summary.get('warning_count', 0)} warning, "
                       f"{summary.get('healthy_count', 0)} healthy")

        except Exception as e:
            logger.error(f"Error logging health status: {e}")

    def write_health_status(self, health_data: Dict[str, Any]):
        """Write health status to JSON file."""
        try:
            with open(HEALTH_STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(health_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error writing health status file: {e}")

    def create_dashboard_update(self, health_data: Dict[str, Any]):
        """Create a dashboard update file for cloud system."""
        try:
            if health_data.get("overall_status") == "critical":
                # Create an alert for cloud system
                alert_file = VAULT_DIR / "data" / "Updates" / f"local_health_alert_{int(time.time())}.md"

                alert_content = f"""---
type: health_alert
severity: high
source: local_health_monitor
timestamp: {datetime.now().isoformat()}
---

## Local System Health Alert

**Status**: {health_data.get('overall_status', 'unknown')}
**Time**: {health_data.get('timestamp', datetime.now().isoformat())}

### Summary
- Critical issues: {health_data.get('summary', {}).get('critical_count', 0)}
- Warning issues: {health_data.get('summary', {}).get('warning_count', 0)}
- Healthy items: {health_data.get('summary', {}).get('healthy_count', 0)}

### System Resources
- CPU: {health_data.get('system_health', {}).get('cpu', {}).get('percent', 'N/A')}%
- Memory: {health_data.get('system_health', {}).get('memory', {}).get('percent', 'N/A')}%
- Disk: {health_data.get('system_health', {}).get('disk', {}).get('percent', 'N/A')}%

This alert has been sent to cloud system for awareness.
"""

                # Ensure Updates directory exists
                updates_dir = VAULT_DIR / "data" / "Updates"
                updates_dir.mkdir(parents=True, exist_ok=True)

                with open(alert_file, 'w', encoding='utf-8') as f:
                    f.write(alert_content)

                logger.info(f"Created health alert file: {alert_file.name}")

        except Exception as e:
            logger.error(f"Error creating dashboard update: {e}")

    def update_heartbeat(self):
        """Update heartbeat file to show local system is alive."""
        try:
            heartbeat_data = {
                "timestamp": datetime.now().isoformat(),
                "service": "local_executive",
                "status": "running",
                "version": "platinum",
                "type": "health_monitor"
            }

            with open(self.heartbeat_file, 'w', encoding='utf-8') as f:
                json.dump(heartbeat_data, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")

    def start(self):
        """Start the health monitor."""
        logger.info("Starting Local Health Monitor (Platinum Tier)")
        logger.info("Monitoring system health and performance")

        self.running = True

        while self.running:
            try:
                if self.active:
                    # Update heartbeat
                    self.update_heartbeat()

                    # Check if enough time has passed since last check
                    current_time = time.time()
                    if current_time - self.last_check_time >= self.check_interval:
                        self.run_health_check()
                        self.last_check_time = current_time

                # Sleep between checks
                time.sleep(30)  # Check every 30 seconds for interval timing

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(10)  # Brief pause before continuing

    def stop(self):
        """Stop the health monitor."""
        logger.info("Stopping Local Health Monitor")
        self.running = False

def main():
    """Main entry point for local health monitor."""
    import argparse

    parser = argparse.ArgumentParser(description="Local Health Monitor (Platinum Tier)")
    parser.add_argument("--single-run", action="store_true", help="Run one health check then exit")
    args = parser.parse_args()

    monitor = LocalHealthMonitor()

    if args.single_run:
        logger.info("Running single health check")
        try:
            monitor.run_health_check()
            logger.info("Single health check completed")
        except Exception as e:
            logger.error(f"Error in single health check: {e}")
            sys.exit(1)
    else:
        # Continuous operation
        try:
            monitor.start()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            monitor.stop()

if __name__ == "__main__":
    main()