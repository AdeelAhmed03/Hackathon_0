#!/usr/bin/env python3
"""
Security Scanner - Platinum Tier

Scans the vault for potential secrets in Git-synced directories.
This script should be run regularly to ensure sensitive data is not accidentally committed.

Features:
- Scans for common credential patterns
- Checks for OAuth tokens, API keys, passwords
- Verifies .gitignore configuration
- Reports any detected secrets with remediation steps
- Runs as a cron job in production
"""

import os
import re
import sys
import subprocess
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = VAULT_DIR / "data"
LOGS_DIR = DATA_DIR / "Logs"
SECURITY_DIR = VAULT_DIR / "security"

# Directories that are Git-synced and should NOT contain secrets
SYNCED_DIRS = [
    DATA_DIR / "Needs_Action" / "cloud",
    DATA_DIR / "Needs_Action" / "local",
    DATA_DIR / "Plans" / "cloud",
    DATA_DIR / "Pending_Approval" / "local",
    DATA_DIR / "Approved",
    DATA_DIR / "Rejected",
    DATA_DIR / "In_Progress" / "cloud",
    DATA_DIR / "In_Progress" / "local",
    DATA_DIR / "Done" / "cloud",
    DATA_DIR / "Done" / "local",
    DATA_DIR / "Updates",
    DATA_DIR / "Plans",  # Some plans may be shared
    DATA_DIR / "Signals",
    DATA_DIR / "Briefings",
    DATA_DIR / "Accounting",  # Only draft/accounting data, not credentials
    DATA_DIR / "Logs",       # Audit logs may contain PII but not secrets
]

# Files that are Git-synced
SYNCED_FILES = [
    DATA_DIR / "Dashboard.md",
    DATA_DIR / "Business_Goals.md",
]

# Patterns that indicate potential secrets
SECRET_PATTERNS = [
    # API keys
    (r'["\']?(\w*_)?api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?', "API Key"),
    (r'["\']?(\w*_)?token["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?', "Token"),
    (r'\b(AKIA|ASIA)[A-Z0-9]{16}\b', "AWS Access Key ID"),
    (r'\b(ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9]{36,}\b', "GitHub Token"),
    (r'\b[0-9a-fA-F]{32,}\b', "Hexadecimal Key"),  # Generic hex key
    (r'\b(sk|pk)_(test|live)_[A-Za-z0-9]{24,}\b', "Stripe Key"),
    (r'\b(AC[a-zA-Z0-9]{32}|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b', "Twilio/ SendGrid Key"),

    # Password patterns
    (r'["\']?(\w*_)?pass(word|wd|wrd)?["\']?\s*[:=]\s*["\']?([^\s"\']{6,})["\']?', "Password"),
    (r'["\']?(\w*_)?pwd["\']?\s*[:=]\s*["\']?([^\s"\']{6,})["\']?', "Password"),

    # OAuth and authentication
    (r'\b[0-9]+-[0-9A-Za-z]{32}\.apps\.googleusercontent\.com\b', "Google OAuth Client ID"),
    (r'\bAIza[0-9A-Za-z\-_]{35}\b', "Google API Key"),
    (r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', "UUID (may be OAuth)"),

    # Certificate/key patterns
    (r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----', "Private Key"),
    (r'-----BEGIN (RSA |EC |DSA )?PUBLIC KEY-----', "Public Key"),
    (r'-----BEGIN CERTIFICATE-----', "Certificate"),

    # Environment files (should not be in synced dirs)
    (r'.*\.env.*', "Environment File"),
    (r'.*\.pem$', "PEM File"),
    (r'.*\.key$', "Key File"),
    (r'.*\.p12$', "P12 File"),
    (r'.*\.pfx$', "PFX File"),
]

# Files that should be in .gitignore
GIT_IGNORE_PATTERNS = [
    ".env*",
    "data/.env*",
    "data/whatsapp_session*",
    "data/whatsapp-session*",
    "data/session-*",
    "*.log",
    "data/Logs/*",
    "node_modules/",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "Thumbs.db",
    "data/Backups/",
    "secrets/*",
    ".vscode/",
    ".idea/",
]

def log_security_event(event_type: str, message: str, severity: str = "WARNING"):
    """Log security events to structured file."""
    security_log = LOGS_DIR / "security_scan.json"
    timestamp = datetime.now().isoformat()

    event = {
        "timestamp": timestamp,
        "event_type": event_type,
        "message": message,
        "severity": severity,
        "scanner": "secrets_scanner"
    }

    # Read existing events or create new list
    events = []
    if security_log.exists():
        try:
            with open(security_log, 'r', encoding='utf-8') as f:
                events = json.load(f)
        except (json.JSONDecodeError, IOError):
            events = []

    events.append(event)

    # Write back to file
    security_log.parent.mkdir(parents=True, exist_ok=True)
    with open(security_log, 'w', encoding='utf-8') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

def check_gitignore():
    """Check if .gitignore contains security-relevant patterns."""
    gitignore_path = VAULT_DIR / ".gitignore"
    issues = []

    if not gitignore_path.exists():
        issues.append(f"Missing .gitignore file at {gitignore_path}")
        return issues, False

    gitignore_content = gitignore_path.read_text(encoding='utf-8')

    missing_patterns = []
    for pattern in GIT_IGNORE_PATTERNS:
        if pattern not in gitignore_content:
            missing_patterns.append(pattern)

    if missing_patterns:
        issues.append(f"Missing patterns in .gitignore: {missing_patterns}")

    # Check for secrets in .gitignore content itself
    for pattern, description in SECRET_PATTERNS:
        if re.search(pattern, gitignore_content, re.IGNORECASE):
            issues.append(f"Potential {description} detected in .gitignore content")

    return issues, len(missing_patterns) == 0

def scan_file_for_secrets(file_path: Path) -> List[Tuple[str, str]]:
    """Scan a single file for potential secrets."""
    detected_secrets = []

    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')

        for pattern, description in SECRET_PATTERNS:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                detected_secrets.append((description, match.group()))

    except Exception as e:
        print(f"  ERROR: Could not read {file_path}: {e}")
        detected_secrets.append(("File Read Error", str(e)))

    return detected_secrets

def scan_synced_directories():
    """Scan all synced directories for secrets."""
    all_issues = []
    total_files = 0
    files_with_secrets = 0

    print(f"\nScanning Git-synced directories for secrets...")
    print(f"Vault Directory: {VAULT_DIR}")
    print(f"Scanning {len(SYNCED_DIRS + SYNCED_FILES)} target locations\n")

    for target in SYNCED_DIRS + SYNCED_FILES:
        if not target.exists():
            continue

        if target.is_dir():
            files = list(target.glob("**/*"))
        else:
            files = [target]

        for file_path in files:
            if file_path.is_file():
                total_files += 1
                secrets = scan_file_for_secrets(file_path)

                if secrets:
                    files_with_secrets += 1
                    for secret_type, secret_value in secrets:
                        issue = f"Potential {secret_type} in {file_path}: {secret_value[:50]}..."
                        print(f"  [ERROR] {issue}")
                        all_issues.append(issue)
                        log_security_event("secret_detected", issue, "CRITICAL")

    return all_issues, total_files, files_with_secrets

def scan_git_history():
    """Scan Git history for secrets."""
    issues = []

    try:
        # Check recent Git commits for secrets
        result = subprocess.run([
            "git", "log", "-p", "-n", "10", "--all",
            "--", "data/"
        ], cwd=VAULT_DIR, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            for pattern, description in SECRET_PATTERNS:
                matches = re.finditer(pattern, result.stdout, re.IGNORECASE)
                for match in matches:
                    issue = f"Potential {description} found in Git history: {match.group()[:50]}..."
                    issues.append(issue)
                    log_security_event("historical_secret", issue, "CRITICAL")
                    print(f"  [ERROR] {issue}")

    except subprocess.TimeoutExpired:
        print("  [WARN] Git history scan timed out (too large repository)")
    except Exception as e:
        print(f"  [WARN] Git history scan error: {e}")

    return issues

def generate_security_report(issues: List[str], git_issues: List[str],
                           total_files: int, files_with_secrets: int):
    """Generate a security report."""
    timestamp = datetime.now().isoformat()
    report = {
        "scan_timestamp": timestamp,
        "total_synced_files": total_files,
        "files_with_secrets": files_with_secrets,
        "direct_issues": len(issues),
        "git_issues": len(git_issues),
        "status": "SECURE" if (len(issues) == 0 and len(git_issues) == 0) else "ISSUES_DETECTED",
        "direct_issues_list": issues,
        "git_issues_list": git_issues
    }

    # Save report
    report_path = SECURITY_DIR / f"security_scan_report_{timestamp.replace(':', '-')}.json"
    SECURITY_DIR.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report_path

def main():
    parser = argparse.ArgumentParser(description="Security Scanner - Check for secrets in Git-synced directories")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix detected issues")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--report", action="store_true", help="Generate security report")

    args = parser.parse_args()

    print("=" * 60)
    print("PLATINUM TIER SECURITY SCANNER")
    print("=" * 60)

    # Check .gitignore configuration
    print(f"\n1. Checking .gitignore configuration...")
    gitignore_issues, gitignore_ok = check_gitignore()

    for issue in gitignore_issues:
        print(f"  [ERROR] {issue}")
        log_security_event("gitignore_issue", issue, "WARNING")

    if gitignore_ok:
        print(f"  [OK] .gitignore properly configured")
        log_security_event("gitignore_check", "Gitignore properly configured", "INFO")
    else:
        print(f"  [WARN] .gitignore issues detected")

    # Scan synced directories
    print(f"\n2. Scanning synced directories for secrets...")
    sync_issues, total_files, files_with_secrets = scan_synced_directories()

    # Scan Git history
    print(f"\n3. Scanning Git history for secrets...")
    git_history_issues = scan_git_history()

    # Generate summary
    print(f"\n" + "=" * 60)
    print("SCAN RESULTS")
    print("=" * 60)
    print(f"Total files scanned: {total_files}")
    print(f"Files with secrets: {files_with_secrets}")
    print(f"Direct issues found: {len(sync_issues)}")
    print(f"Git history issues: {len(git_history_issues)}")
    print(f"Git ignore issues: {len(gitignore_issues)}")

    total_issues = len(sync_issues) + len(git_history_issues) + len(gitignore_issues)

    if total_issues == 0:
        print(f"\n[OK] SECURITY STATUS: All clear! No secrets detected in synced directories.")
        log_security_event("security_scan", "No secrets detected", "INFO")
    else:
        print(f"\n[ERROR] SECURITY STATUS: {total_issues} issues detected!")
        log_security_event("security_scan", f"{total_issues} issues detected", "CRITICAL")

    # Generate report if requested
    if args.report or total_issues > 0:
        report_path = generate_security_report(sync_issues, git_history_issues, total_files, files_with_secrets)
        print(f"\n[REPORT] Security report generated: {report_path}")

    # Remediation suggestions
    if sync_issues or git_history_issues:
        print(f"\n[REMEDIATION] STEPS:")
        print(f"  1. Move detected secrets to environment variables")
        print(f"  2. Add sensitive files to .gitignore")
        print(f"  3. If secrets were committed, perform Git history cleanup")
        print(f"  4. Re-run this scanner to verify fixes")

    return 0 if total_issues == 0 else 1

if __name__ == "__main__":
    sys.exit(main())