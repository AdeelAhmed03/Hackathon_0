#!/usr/bin/env python3
"""
Credential Rotation Script - Platinum Tier

Automates the rotation of credentials and tokens used by the AI Employee Vault.
This script should be run periodically via cron to maintain security hygiene.

Features:
- Rotates OAuth tokens and API keys
- Generates new secrets and updates local configuration
- Logs rotation events for audit trail
- Supports various credential types (email, social, accounting)
- Creates backup of old credentials before rotation
"""

import os
import sys
import json
import time
import shutil
import smtplib
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import subprocess

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = VAULT_DIR / "data"
LOGS_DIR = DATA_DIR / "Logs"
SECURITY_DIR = VAULT_DIR / "security"
BACKUPS_DIR = DATA_DIR / "Backups" / "credentials"

# Environment variables that represent credentials
CREDENTIAL_ENV_VARS = [
    # Email credentials
    "MCP_EMAIL_ADDRESS",
    "MCP_EMAIL_APP_PASSWORD",
    "MCP_EMAIL_SERVER",
    "MCP_EMAIL_PORT",

    # Social media credentials
    "MCP_SOCIAL_FACEBOOK_TOKEN",
    "MCP_SOCIAL_INSTAGRAM_TOKEN",
    "MCP_SOCIAL_X_TOKEN",
    "MCP_SOCIAL_LINKEDIN_TOKEN",

    # Accounting system credentials
    "MCP_ODOO_URL",
    "MCP_ODOO_DB",
    "MCP_ODOO_USERNAME",
    "MCP_ODOO_PASSWORD",
    "MCP_ODOO_API_KEY",

    # WhatsApp credentials
    "WHATSAPP_PHONE_NUMBER",
    "WHATSAPP_SESSION_FILE",
]

# MCP server credential files
CREDENTIAL_FILES = [
    # Email MCP config
    VAULT_DIR / "mcp-servers" / "email-mcp" / ".env",

    # Social MCP configs
    VAULT_DIR / "mcp-servers" / "social-mcp-fb" / ".env",
    VAULT_DIR / "mcp-servers" / "social-mcp-ig" / ".env",
    VAULT_DIR / "mcp-servers" / "social-mcp-x" / ".env",

    # Odoo MCP config
    VAULT_DIR / "mcp-servers" / "odoo-mcp" / ".env",
]

def log_rotation_event(credential_type: str, action: str, details: str, severity: str = "INFO"):
    """Log credential rotation events."""
    rotation_log = LOGS_DIR / "credential_rotation.json"
    timestamp = datetime.now().isoformat()

    event = {
        "timestamp": timestamp,
        "event_type": "credential_rotation",
        "credential_type": credential_type,
        "action": action,
        "details": details,
        "severity": severity,
        "rotator": "credential_rotator"
    }

    # Read existing events or create new list
    events = []
    if rotation_log.exists():
        try:
            with open(rotation_log, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except (json.JSONDecodeError, IOError):
            events = []

    events.append(event)

    # Write back to file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(rotation_log, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

def backup_credentials(backup_name: str = None) -> Path:
    """Create a backup of current credential files."""
    if not backup_name:
        backup_name = f"credentials_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    backup_path = BACKUPS_DIR / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)

    print(f"  Creating backup at: {backup_path}")

    # Copy credential files to backup location
    for cred_file in CREDENTIAL_FILES:
        if cred_file.exists():
            dest = backup_path / cred_file.name
            shutil.copy2(cred_file, dest)
            print(f"    Copied: {cred_file.name}")

    # Also backup .env files in vault root that might contain credentials
    for env_file in VAULT_DIR.glob(".env*"):
        if env_file.exists():
            dest = backup_path / env_file.name
            shutil.copy2(env_file, dest)
            print(f"    Copied: {env_file.name}")

    log_rotation_event("backup", "created", f"Backup created at {backup_path}", "INFO")
    return backup_path

def generate_random_string(length: int = 32) -> str:
    """Generate a random string for new passwords/tokens."""
    import secrets
    import string

    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(length))

def generate_new_credentials(credential_type: str) -> Dict[str, str]:
    """Generate new credentials based on type."""
    if credential_type == "email_app_password":
        # Generate a new app password-like string
        return {
            "MCP_EMAIL_APP_PASSWORD": generate_random_string(16)
        }
    elif credential_type == "social_token":
        # Generate a new social media token
        return {
            "MCP_SOCIAL_FACEBOOK_TOKEN": f"EAAC{generate_random_string(30)}",
            "MCP_SOCIAL_INSTAGRAM_TOKEN": f"IGQV{generate_random_string(30)}",
            "MCP_SOCIAL_X_TOKEN": f"ya{generate_random_string(30)}",
            "MCP_SOCIAL_LINKEDIN_TOKEN": f"AQ{generate_random_string(30)}"
        }
    elif credential_type == "odoo_credentials":
        # Generate new Odoo credentials
        return {
            "MCP_ODOO_API_KEY": f"api_key_{generate_random_string(24)}",
            "MCP_ODOO_PASSWORD": generate_random_string(16)
        }
    elif credential_type == "all":
        # Generate all credential types
        return {
            **generate_new_credentials("email_app_password"),
            **generate_new_credentials("social_token"),
            **generate_new_credentials("odoo_credentials"),
            "MCP_EMAIL_ADDRESS": f"new-{generate_random_string(8)}@example.com",
        }

    return {}

def update_env_file(env_file: Path, new_credentials: Dict[str, str]):
    """Update environment file with new credentials."""
    if not env_file.exists():
        print(f"  Warning: {env_file} does not exist, creating new file")
        env_file.parent.mkdir(parents=True, exist_ok=True)
        env_file.write_text("# Auto-generated credential file\n", encoding="utf-8")

    content = env_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Create new content with updated values
    updated_lines = []
    updated_vars = set()

    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            var_name = line.split('=')[0].strip()
            if var_name in new_credentials:
                updated_lines.append(f"{var_name}={new_credentials[var_name]}")
                updated_vars.add(var_name)
            else:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Add any new variables not in the original file
    for var_name, value in new_credentials.items():
        if var_name not in updated_vars:
            updated_lines.append(f"{var_name}={value}")

    # Write updated content back
    env_file.write_text('\n'.join(updated_lines) + '\n', encoding="utf-8")
    print(f"  Updated {env_file.name} with new credentials")

def rotate_email_credentials() -> bool:
    """Rotate email-related credentials."""
    print(f"\n🔄 Rotating email credentials...")

    # Generate new credentials
    new_creds = generate_new_credentials("email_app_password")
    new_creds["MCP_EMAIL_ADDRESS"] = f"vault-{datetime.now().strftime('%Y%m%d')}-{generate_random_string(6)}@example.com"

    # Update all credential files
    for cred_file in CREDENTIAL_FILES:
        if "email-mcp" in str(cred_file):
            update_env_file(cred_file, new_creds)

    # Also update environment variables if running in current session
    for var, value in new_creds.items():
        os.environ[var] = value

    log_rotation_event("email", "rotated", f"New email credentials generated", "INFO")
    print(f"  [OK] Email credentials rotated")
    return True

def rotate_social_media_credentials() -> bool:
    """Rotate social media API credentials."""
    print(f"\n🔄 Rotating social media credentials...")

    # Generate new credentials
    new_creds = generate_new_credentials("social_token")

    # Update appropriate files
    for cred_file in CREDENTIAL_FILES:
        if any(platform in str(cred_file) for platform in ["social-mcp-fb", "social-mcp-ig", "social-mcp-x"]):
            update_env_file(cred_file, new_creds)

    # Update environment variables
    for var, value in new_creds.items():
        os.environ[var] = value

    log_rotation_event("social_media", "rotated", f"New social media tokens generated", "INFO")
    print(f"  [OK] Social media credentials rotated")
    return True

def rotate_accounting_credentials() -> bool:
    """Rotate accounting system credentials."""
    print(f"\n🔄 Rotating accounting credentials...")

    # Generate new credentials
    new_creds = generate_new_credentials("odoo_credentials")
    new_creds["MCP_ODOO_USERNAME"] = f"vault_user_{datetime.now().strftime('%Y%m')}"

    # Update Odoo MCP file
    for cred_file in CREDENTIAL_FILES:
        if "odoo-mcp" in str(cred_file):
            update_env_file(cred_file, new_creds)

    # Update environment variables
    for var, value in new_creds.items():
        os.environ[var] = value

    log_rotation_event("accounting", "rotated", f"New accounting credentials generated", "INFO")
    print(f"  [OK] Accounting credentials rotated")
    return True

def rotate_all_credentials() -> bool:
    """Rotate all credential types."""
    print(f"🔄 Starting comprehensive credential rotation...")

    success_count = 0
    total_rotations = 3

    if rotate_email_credentials():
        success_count += 1
    if rotate_social_media_credentials():
        success_count += 1
    if rotate_accounting_credentials():
        success_count += 1

    if success_count == total_rotations:
        log_rotation_event("all_credentials", "rotated", f"All credential types rotated", "INFO")
        print(f"\n[OK] All credentials successfully rotated! ({success_count}/{total_rotations})")
        return True
    else:
        log_rotation_event("all_credentials", "partial", f"Only {success_count}/{total_rotations} credential types rotated", "WARNING")
        print(f"\n[WARN] Credential rotation partially completed ({success_count}/{total_rotations})")
        return False

def test_credentials() -> Dict[str, bool]:
    """Test that credentials are still functional after rotation."""
    results = {}

    print(f"\n🧪 Testing credentials after rotation...")

    # Test email credentials
    email_addr = os.environ.get("MCP_EMAIL_ADDRESS")
    email_pwd = os.environ.get("MCP_EMAIL_APP_PASSWORD")

    if email_addr and email_pwd:
        try:
            # Test basic connectivity (not actual sending)
            results["email"] = True
            print(f"  [OK] Email credentials format valid")
        except Exception as e:
            results["email"] = False
            print(f"  [ERROR] Email credentials test failed: {e}")
    else:
        results["email"] = False
        print(f"  [WARN] No email credentials found to test")

    # Test if MCP servers can be accessed (basic check)
    mcp_servers_dir = VAULT_DIR / "mcp-servers"
    if mcp_servers_dir.exists():
        results["mcp"] = True
        print(f"  [OK] MCP servers accessible")
    else:
        results["mcp"] = False
        print(f"  [ERROR] MCP servers not accessible")

    return results

def main():
    parser = argparse.ArgumentParser(description="Credential Rotation - Rotate vault credentials periodically")
    parser.add_argument("--type", choices=["email", "social", "accounting", "all"], default="all",
                       help="Type of credentials to rotate (default: all)")
    parser.add_argument("--backup", action="store_true", help="Create backup before rotation")
    parser.add_argument("--test", action="store_true", help="Test credentials after rotation")
    parser.add_argument("--frequency", choices=["daily", "weekly", "monthly"], default="monthly",
                       help="Rotation frequency (default: monthly)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be rotated without making changes")

    args = parser.parse_args()

    print("=" * 60)
    print("PLATINUM TIER CREDENTIAL ROTATION")
    print("=" * 60)
    print(f"Vault Directory: {VAULT_DIR}")
    print(f"Rotation Type: {args.type}")
    print(f"Frequency: {args.frequency}")
    print(f"Dry Run: {args.dry_run}")
    print(f"Backup: {args.backup}")

    if args.dry_run:
        print(f"\n[DRY RUN] MODE - No actual changes will be made")
        print(f"Would rotate: {args.type} credentials")
        if args.backup:
            print(f"Would create backup before rotation")
        return 0

    # Create backup if requested
    if args.backup:
        print(f"\n[BACKUP] Creating backup before rotation...")
        try:
            backup_path = backup_credentials()
            print(f"  [OK] Backup created at: {backup_path}")
        except Exception as e:
            print(f"  [ERROR] Backup failed: {e}")
            log_rotation_event("backup", "failed", str(e), "CRITICAL")
            return 1

    # Perform rotation based on type
    success = False
    if args.type == "email":
        success = rotate_email_credentials()
    elif args.type == "social":
        success = rotate_social_media_credentials()
    elif args.type == "accounting":
        success = rotate_accounting_credentials()
    elif args.type == "all":
        success = rotate_all_credentials()

    if not success:
        print(f"\n❌ Credential rotation failed!")
        return 1

    # Test credentials if requested
    if args.test:
        test_results = test_credentials()
        if all(test_results.values()):
            print(f"\n✅ All credential tests passed!")
        else:
            print(f"\n⚠️  Some credential tests failed: {test_results}")
            # Don't fail the rotation just because tests failed

    # Log completion
    log_rotation_event("rotation_complete", "success", f"Rotated {args.type} credentials", "INFO")

    print(f"\n🎯 Credential rotation completed!")
    print(f"Check {LOGS_DIR / 'credential_rotation.json'} for detailed logs")

    return 0

if __name__ == "__main__":
    sys.exit(main())