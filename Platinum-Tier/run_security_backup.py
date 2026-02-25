#!/usr/bin/env python3
"""
Platinum Tier Security & Backup Runner

This script coordinates all security scanning and backup operations for the Platinum Tier system.
It's designed to be run as part of automated cron jobs or manually for system maintenance.
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime
from pathlib import Path

def run_command(cmd, description, cwd=None):
    """Execute a command and return success status."""
    print(f"\n🚀 {description}")
    print(f"   Command: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            print(f"   ✅ Success: {result.stdout.strip() if result.stdout.strip() else 'Completed'}")
            return True
        else:
            print(f"   ❌ Failed: {result.stderr.strip()}")
            return False

    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timeout: Command took longer than 5 minutes")
        return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Platinum Tier Security & Backup Runner")
    parser.add_argument("--scan", action="store_true", help="Run security scan")
    parser.add_argument("--rotate", action="store_true", help="Rotate credentials")
    parser.add_argument("--backup", action="store_true", help="Run backup")
    parser.add_argument("--all", action="store_true", help="Run all operations")
    parser.add_argument("--password", help="Backup encryption password")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without executing")

    args = parser.parse_args()

    # Set current directory to vault root
    vault_dir = Path(__file__).parent
    os.chdir(vault_dir)

    print("=" * 70)
    print("PLATINUM TIER SECURITY & BACKUP COORDINATOR")
    print("=" * 70)
    print(f"Current Directory: {os.getcwd()}")
    print(f"Dry Run Mode: {args.dry_run}")
    print(f"Operations: {'All' if args.all else 'Custom'}")

    all_success = True

    # Run security scan
    if args.all or args.scan:
        cmd = f'python security/scan_secrets.py --report'
        if args.dry_run:
            print(f"\n[DRY RUN]: Would execute - Security Scan")
            print(f"   Command: {cmd}")
        else:
            success = run_command(cmd, "Running Security Scan", vault_dir)
            all_success = all_success and success
            time.sleep(2)  # Brief pause between operations

    # Rotate credentials
    if args.all or args.rotate:
        cmd = f'python security/rotate_credentials.py --type all --backup --test'
        if args.dry_run:
            print(f"\n[DRY RUN]: Would execute - Credential Rotation")
            print(f"   Command: {cmd}")
        else:
            success = run_command(cmd, "Rotating All Credentials", vault_dir)
            all_success = all_success and success
            time.sleep(2)

    # Run backup
    if args.all or args.backup:
        cmd = f'python backup/backup_system.py'
        if args.password:
            cmd += f' --password "{args.password}"'
        cmd += f' --verify --cleanup'

        if args.dry_run:
            print(f"\n[DRY RUN]: Would execute - Backup System")
            print(f"   Command: {cmd}")
        else:
            success = run_command(cmd, "Running Backup System", vault_dir)
            all_success = all_success and success
            time.sleep(2)

    # If no specific operations requested, show help
    if not args.all and not args.scan and not args.rotate and not args.backup:
        print(f"\n[INFO] No operations specified. Use:")
        print(f"   --all      : Run all security and backup operations")
        print(f"   --scan     : Run security scan")
        print(f"   --rotate   : Rotate credentials")
        print(f"   --backup   : Run backup")
        print(f"   --password : Backup encryption password")
        print(f"   --dry-run  : Show commands without executing")
        return 0

    # Final summary
    print(f"\n" + "=" * 70)
    print(f"EXECUTION SUMMARY")
    print(f"=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Status: {'[OK] All operations completed successfully' if all_success else '[ERROR] Some operations failed'}")

    if not args.dry_run:
        print(f"\n📊 Check security and backup logs in: data/Logs/")
        print(f"📦 Backups stored in: data/Backups/")

    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())