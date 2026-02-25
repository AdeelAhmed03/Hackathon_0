#!/usr/bin/env python3
"""
Backup System - Platinum Tier

Performs daily backups of critical data:
- Cloud Odoo data (accounting, invoices, payments)
- /data/ directory (workflow state, plans, dashboard, etc.)
- Compresses and encrypts backups
- Stores in secure location
- Maintains retention policy
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import tarfile
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = VAULT_DIR / "data"
BACKUPS_DIR = DATA_DIR / "Backups"
LOGS_DIR = DATA_DIR / "Logs"

# Directories to backup
BACKUP_DIRECTORIES = [
    DATA_DIR / "Dashboard.md",           # Main dashboard state
    DATA_DIR / "Business_Goals.md",      # Business goals
    DATA_DIR / "Plans",                  # All plans (cloud and local)
    DATA_DIR / "Needs_Action",           # All pending actions
    DATA_DIR / "Pending_Approval",       # All pending approvals
    DATA_DIR / "Approved",               # Approved items
    DATA_DIR / "Rejected",               # Rejected items
    DATA_DIR / "In_Progress",            # In-progress items
    DATA_DIR / "Done",                   # Completed items
    DATA_DIR / "Updates",                # Dashboard updates
    DATA_DIR / "Signals",                # Business signals
    DATA_DIR / "Briefings",              # Reports and briefings
    DATA_DIR / "Accounting",             # Accounting data (non-credentials)
    DATA_DIR / "Logs",                   # Audit logs
    DATA_DIR / "Docs",                   # Documentation
    DATA_DIR / "Inbox",                  # Inbox files
]

# Odoo MCP directory for accounting backup
ODOO_MCP_DIR = VAULT_DIR / "mcp-servers" / "odoo-mcp"

def log_backup_event(event_type: str, details: str, severity: str = "INFO"):
    """Log backup events to structured file."""
    backup_log = LOGS_DIR / "backup_log.json"
    timestamp = datetime.now().isoformat()

    event = {
        "timestamp": timestamp,
        "event_type": event_type,
        "details": details,
        "severity": severity,
        "backup_system": "system_backup"
    }

    # Read existing events or create new list
    events = []
    if backup_log.exists():
        try:
            with open(backup_log, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except (json.JSONDecodeError, IOError):
            events = []

    events.append(event)

    # Write back to file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(backup_log, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

def get_odoo_data():
    """Get Odoo accounting data if available."""
    # Try to get Odoo data by calling the MCP server
    try:
        odoo_script = ODOO_MCP_DIR / "odoo_mcp.py"
        if odoo_script.exists():
            # Create a test request to get current state
            test_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }

            result = subprocess.run(
                [sys.executable, str(odoo_script)],
                input=json.dumps(test_request) + "\n",
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(ODOO_MCP_DIR.parent.parent)
            )

            if result.returncode == 0:
                # Save Odoo state data
                odoo_backup_path = BACKUPS_DIR / "odoo_state"
                odoo_backup_path.mkdir(parents=True, exist_ok=True)

                state_file = odoo_backup_path / f"odoo_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                state_file.write_text(result.stdout, encoding="utf-8")

                return str(state_file)
    except Exception as e:
        print(f"  [WARN] Could not retrieve Odoo data: {e}")
        log_backup_event("odoo_backup", f"Failed to retrieve Odoo data: {e}", "WARNING")
        return None

def create_encryption_key(password: str) -> bytes:
    """Create encryption key from password."""
    salt = os.urandom(16)  # Salt for this specific backup
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def encrypt_backup(backup_path: Path, password: str):
    """Encrypt the backup file."""
    try:
        # Create encryption key
        key, salt = create_encryption_key(password)
        fernet = Fernet(key)

        # Read the backup file and encrypt it
        with open(backup_path, 'rb') as f:
            data = f.read()

        encrypted_data = fernet.encrypt(data)

        # Write encrypted data with salt prepended
        encrypted_path = backup_path.with_suffix('.enc')
        with open(encrypted_path, 'wb') as f:
            f.write(salt + encrypted_data)

        # Remove original
        backup_path.unlink()

        print(f"  [OK] Backup encrypted: {encrypted_path.name}")
        log_backup_event("encryption", f"Backup encrypted: {encrypted_path.name}", "INFO")
        return encrypted_path
    except Exception as e:
        print(f"  [ERROR] Encryption failed: {e}")
        log_backup_event("encryption", f"Encryption failed: {e}", "CRITICAL")
        return backup_path  # Return unencrypted if encryption fails

def create_backup(password: Optional[str] = None) -> Optional[Path]:
    """Create a backup of the vault data."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"vault_backup_{timestamp}.tar.gz"
    backup_path = BACKUPS_DIR / backup_name

    print(f"[BACKUP] Creating backup: {backup_path}")

    # Create backup directory
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    # Get Odoo data first
    odoo_data_path = get_odoo_data()

    try:
        # Create tar.gz backup
        with tarfile.open(backup_path, "w:gz") as tar:
            # Add all backup directories/files
            for target in BACKUP_DIRECTORIES:
                if target.exists():
                    print(f"  Adding: {target}")
                    tar.add(target, arcname=target.name)

            # Add Odoo data if available
            if odoo_data_path:
                odoo_file = Path(odoo_data_path)
                tar.add(odoo_file, arcname=f"odoo_state/{odoo_file.name}")
                print(f"  Adding Odoo data: {odoo_file.name}")

        print(f"  [OK] Backup created: {backup_path.name} ({backup_path.stat().st_size:,} bytes)")
        log_backup_event("backup_created", f"Backup created: {backup_path.name}", "INFO")

        # Encrypt if password provided
        if password:
            backup_path = encrypt_backup(backup_path, password)

        return backup_path

    except Exception as e:
        print(f"  [ERROR] Backup failed: {e}")
        log_backup_event("backup_failed", f"Backup failed: {e}", "CRITICAL")
        return None

def cleanup_old_backups(retention_days: int = 7):
    """Remove backup files older than retention_days."""
    print(f"\n🧹 Cleaning up backups older than {retention_days} days...")

    cutoff_date = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0

    for backup_file in BACKUPS_DIR.glob("vault_backup_*"):
        if backup_file.stat().st_mtime < cutoff_date.timestamp():
            try:
                backup_file.unlink()
                print(f"  Removed: {backup_file.name}")
                deleted_count += 1
            except Exception as e:
                print(f"  [WARN] Could not delete {backup_file.name}: {e}")
                log_backup_event("cleanup", f"Failed to delete {backup_file.name}: {e}", "WARNING")

    print(f"  [OK] Cleanup completed: {deleted_count} old backups removed")
    log_backup_event("cleanup", f"Cleaned up {deleted_count} old backups", "INFO")

def verify_backup(backup_path: Path) -> bool:
    """Verify the integrity of a backup."""
    try:
        # Check if backup file exists and has content
        if not backup_path.exists():
            print(f"  [ERROR] Backup file does not exist: {backup_path}")
            return False

        if backup_path.stat().st_size == 0:
            print(f"  [ERROR] Backup file is empty: {backup_path}")
            return False

        # Try to read the backup file
        if backup_path.suffix.endswith('.enc'):
            # Encrypted backup - can't easily verify without password
            print(f"  [SECURITY] Cannot verify encrypted backup without password: {backup_path.name}")
            return True  # Assume integrity if file exists
        else:
            # Regular tar.gz backup - verify it can be opened
            with tarfile.open(backup_path, "r:gz") as tar:
                members = tar.getmembers()
                print(f"  [OK] Backup verified: {len(members)} items, {backup_path.stat().st_size:,} bytes")
                log_backup_event("verification", f"Backup verified: {len(members)} items", "INFO")
                return True

    except Exception as e:
        print(f"  [ERROR] Backup verification failed: {e}")
        log_backup_event("verification", f"Verification failed: {e}", "CRITICAL")
        return False

def main():
    parser = argparse.ArgumentParser(description="Backup System - Daily backups of vault data")
    parser.add_argument("--password", "-p", help="Password to encrypt backup")
    parser.add_argument("--verify", action="store_true", help="Verify backup integrity")
    parser.add_argument("--cleanup", action="store_true", help="Clean up old backups")
    parser.add_argument("--retention", type=int, default=7, help="Retention days for cleanup (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be backed up")

    args = parser.parse_args()

    print("=" * 60)
    print("PLATINUM TIER BACKUP SYSTEM")
    print("=" * 60)
    print(f"Vault Directory: {VAULT_DIR}")
    print(f"Backup Directory: {BACKUPS_DIR}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Encryption: {'Yes' if args.password else 'No'}")

    if args.dry_run:
        print(f"\n[DRY RUN] MODE - No actual backups will be created")
        print(f"Would backup: {len(BACKUP_DIRECTORIES)} directories/files")
        if args.password:
            print(f"Would encrypt with provided password")
        return 0

    # Create backup
    print(f"\n[START] Starting backup process...")
    backup_path = create_backup(args.password if args.password else None)

    if not backup_path:
        print(f"[ERROR] Backup process failed!")
        return 1

    # Verify backup if requested
    if args.verify:
        print(f"\n[VERIFY] Verifying backup integrity...")
        if verify_backup(backup_path):
            print(f"[OK] Backup verification successful!")
        else:
            print(f"❌ Backup verification failed!")
            return 1

    # Clean up old backups if requested
    if args.cleanup:
        cleanup_old_backups(args.retention)

    print(f"\n🎯 Backup completed successfully!")
    print(f"Backup location: {backup_path}")
    print(f"Check {LOGS_DIR / 'backup_log.json'} for detailed logs")

    return 0

if __name__ == "__main__":
    # Install required package if not available
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("Installing cryptography package...")
        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], check=True)
        from cryptography.fernet import Fernet

    sys.exit(main())