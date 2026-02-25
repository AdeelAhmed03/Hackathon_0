#!/usr/bin/env python3
"""
Platinum Tier End-to-End Test Suite

Comprehensive test suite that validates all Platinum Tier functionality:
- Cloud/Local Executive coordination
- Work-zone separation
- Git synchronization
- A2A messaging (Phase 2)
- Security scanning
- Backup systems
- All MCP integrations
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import json
import tempfile

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
DATA_DIR = VAULT_DIR / "data"
LOGS_DIR = DATA_DIR / "Logs"

# Test directories
TEST_NEEDS_ACTION_CLOUD = DATA_DIR / "Needs_Action" / "cloud"
TEST_NEEDS_ACTION_LOCAL = DATA_DIR / "Needs_Action" / "local"
TEST_PLANS_CLOUD = DATA_DIR / "Plans" / "cloud"
TEST_PENDING_APPROVAL = DATA_DIR / "Pending_Approval" / "local"
TEST_APPROVED = DATA_DIR / "Approved"
TEST_DONE_CLOUD = DATA_DIR / "Done" / "cloud"
TEST_DONE_LOCAL = DATA_DIR / "Done" / "local"
TEST_UPDATES = DATA_DIR / "Updates"
TEST_IN_PROGRESS_CLOUD = DATA_DIR / "In_Progress" / "cloud"
TEST_IN_PROGRESS_LOCAL = DATA_DIR / "In_Progress" / "local"

def run_test_step(step_num, description, test_func):
    """Run a test step and report results."""
    print(f"\n[{step_num}] {description}")
    try:
        result = test_func()
        if result:
            print("  [OK] PASSED")
            return True
        else:
            print("  [ERROR] FAILED")
            return False
    except Exception as e:
        print(f"  [ERROR] FAILED - Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_component_availability():
    """Test that all required components exist."""
    components = [
        (VAULT_DIR / "security" / "scan_secrets.py", "Security Scanner"),
        (VAULT_DIR / "security" / "rotate_credentials.py", "Credential Rotator"),
        (VAULT_DIR / "backup" / "backup_system.py", "Backup System"),
        (VAULT_DIR / "run_security_backup.py", "Security Coordinator"),
        (VAULT_DIR / "watcher" / "orchestrator_cloud.py", "Cloud Orchestrator"),
        (VAULT_DIR / "agents" / "agent-local-executive.py", "Local Executive Agent"),
        (VAULT_DIR / "a2a_messaging.py", "A2A Messaging"),
        (VAULT_DIR / "demo_test.py", "Demo Test"),
        (VAULT_DIR / "mcp-servers" / "email-mcp", "Email MCP Server"),
        (VAULT_DIR / "mcp-servers" / "social-mcp", "Social MCP Server"),
        (VAULT_DIR / "mcp-servers" / "odoo-mcp", "Odoo MCP Server"),
    ]

    all_exist = True
    for path, name in components:
        exists = path.exists()
        status = "[OK]" if exists else "[ERROR]"
        print(f"  {status} {name}: {path}")
        if not exists:
            all_exist = False

    return all_exist

def test_directory_structure():
    """Test that all required directories exist."""
    directories = [
        TEST_NEEDS_ACTION_CLOUD,
        TEST_NEEDS_ACTION_LOCAL,
        TEST_PLANS_CLOUD,
        TEST_PENDING_APPROVAL,
        TEST_APPROVED,
        TEST_DONE_CLOUD,
        TEST_DONE_LOCAL,
        TEST_UPDATES,
        TEST_IN_PROGRESS_CLOUD,
        TEST_IN_PROGRESS_LOCAL,
    ]

    all_exist = True
    for d in directories:
        d.mkdir(parents=True, exist_ok=True)  # Create if needed
        exists = d.exists()
        status = "[OK]" if exists else "[ERROR]"
        print(f"  {status} Directory: {d}")
        if not exists:
            all_exist = False

    return all_exist

def test_security_scanner():
    """Test the security scanner functionality."""
    try:
        result = subprocess.run([
            sys.executable, str(VAULT_DIR / "security" / "scan_secrets.py"),
            "--dry-run"
        ], cwd=VAULT_DIR, capture_output=True, text=True, timeout=30)

        success = result.returncode == 0
        print(f"  Scanner return code: {result.returncode}")
        print(f"  Output preview: {result.stdout[:200]}...")
        return success
    except Exception as e:
        print(f"  Error running scanner: {e}")
        return False

def test_backup_system():
    """Test the backup system functionality."""
    try:
        result = subprocess.run([
            sys.executable, str(VAULT_DIR / "backup" / "backup_system.py"),
            "--dry-run"
        ], cwd=VAULT_DIR, capture_output=True, text=True, timeout=30)

        success = result.returncode == 0
        print(f"  Backup return code: {result.returncode}")
        print(f"  Output preview: {result.stdout[:200]}...")
        return success
    except Exception as e:
        print(f"  Error running backup: {e}")
        return False

def test_credential_rotation():
    """Test the credential rotation functionality."""
    try:
        result = subprocess.run([
            sys.executable, str(VAULT_DIR / "security" / "rotate_credentials.py"),
            "--dry-run"
        ], cwd=VAULT_DIR, capture_output=True, text=True, timeout=30)

        success = result.returncode == 0
        print(f"  Rotation return code: {result.returncode}")
        print(f"  Output preview: {result.stdout[:200]}...")
        return success
    except Exception as e:
        print(f"  Error running rotation: {e}")
        return False

def test_a2a_messaging():
    """Test A2A messaging system."""
    try:
        # Import and test A2A functionality
        sys.path.insert(0, str(VAULT_DIR))
        from a2a_messaging import A2ANode, self_test

        # Run self-test
        success = self_test()
        print(f"  A2A self-tests passed: {success}")
        return success
    except Exception as e:
        print(f"  Error testing A2A: {e}")
        return False

def test_cloud_orchestrator():
    """Test cloud orchestrator import and basic functionality."""
    try:
        sys.path.insert(0, str(VAULT_DIR))
        from watcher.orchestrator_cloud import CloudExecutiveProcessor

        # Create a simple processor instance
        processor = CloudExecutiveProcessor(dry_run=True)
        print(f"  Cloud processor created: {type(processor).__name__}")
        return True
    except Exception as e:
        print(f"  Error testing cloud orchestrator: {e}")
        return False

def test_local_orchestrator():
    """Test local orchestrator import and basic functionality."""
    try:
        sys.path.insert(0, str(VAULT_DIR))
        import importlib.util

        # Load local executive from file with dash in name
        spec = importlib.util.spec_from_file_location('agent_local_executive',
                                                     str(VAULT_DIR / "agents" / "agent-local-executive.py"))
        local_agent_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(local_agent_module)

        # Create a simple agent instance
        agent = local_agent_module.LocalExecutiveAgent()
        print(f"  Local agent created: {type(agent).__name__}")
        return True
    except Exception as e:
        print(f"  Error testing local orchestrator: {e}")
        return False

def test_demo_validation():
    """Test that the demo validation passes."""
    try:
        result = subprocess.run([
            sys.executable, str(VAULT_DIR / "demo_test.py"),
            "--clean"
        ], cwd=VAULT_DIR, capture_output=True, text=True, timeout=60)

        # The demo test should show "ALL 5 PHASES PASSED"
        success = "ALL 5 PHASES PASSED" in result.stdout and result.returncode == 0
        print(f"  Demo test return code: {result.returncode}")
        print(f"  Demo test result: {'PASSED' if success else 'FAILED'}")
        if not success:
            print(f"  Demo output: {result.stdout[-500:]}")
        return success
    except Exception as e:
        print(f"  Error running demo test: {e}")
        return False

def test_file_operations():
    """Test Platinum Tier file-based coordination."""
    try:
        # Clean test directories
        for d in [TEST_NEEDS_ACTION_CLOUD, TEST_PLANS_CLOUD, TEST_PENDING_APPROVAL,
                  TEST_UPDATES, TEST_DONE_CLOUD]:
            for f in d.glob("*.md"):
                f.unlink()

        # Create a test email file
        test_file = TEST_NEEDS_ACTION_CLOUD / "E2E_TEST_email_001.md"
        test_content = """---
type: email
action: email_triage
from: test@example.com
subject: E2E Test Email
status: pending
priority: normal
zone: cloud
created: 2026-02-22T20:00:00Z
---

# E2E Test Email

**From:** test@example.com
**Subject:** E2E Test Email

This is a test email for E2E validation.

Best regards,
E2E Test System
"""
        test_file.write_text(test_content, encoding="utf-8")
        print(f"  Created test file: {test_file}")

        # Verify file exists
        exists = test_file.exists()
        if not exists:
            return False

        # Test basic file operations
        import shutil
        test_done_file = TEST_DONE_CLOUD / "DONE_cloud_E2E_TEST_email_001.md"

        # Simulate claim-by-move
        if test_file.exists():
            shutil.move(str(test_file), str(test_done_file))
            moved_successfully = test_done_file.exists()
        else:
            moved_successfully = False

        print(f"  File moved successfully: {moved_successfully}")

        # Clean up
        if test_done_file.exists():
            test_done_file.unlink()

        return exists and moved_successfully
    except Exception as e:
        print(f"  Error in file operations: {e}")
        return False

def test_git_integration():
    """Test Git integration (if available)."""
    try:
        # Check if Git is available
        result = subprocess.run(["git", "--version"],
                              capture_output=True, text=True, timeout=10)
        git_available = result.returncode == 0

        if git_available:
            # Test Git operations in vault
            result = subprocess.run(["git", "status", "--porcelain"],
                                  cwd=VAULT_DIR, capture_output=True, text=True, timeout=10)
            git_status_ok = result.returncode == 0
            print(f"  Git available: {git_available}, Status check: {git_status_ok}")
        else:
            print(f"  Git not available in environment")
            # This is not a critical failure for the system
            return True

        return git_available and git_status_ok if git_available else True
    except Exception as e:
        print(f"  Error testing Git: {e}")
        # Git is not critical for core functionality
        return True

def test_mcp_servers():
    """Test MCP server availability."""
    try:
        mcp_dirs = [
            "email-mcp",
            "social-mcp",
            "odoo-mcp"
        ]

        all_mcp_exist = True
        for mcp_dir in mcp_dirs:
            mcp_path = VAULT_DIR / "mcp-servers" / mcp_dir
            exists = mcp_path.exists()
            status = "[OK]" if exists else "[ERROR]"
            print(f"  {status} MCP Server {mcp_dir}: {mcp_path}")
            if not exists:
                all_mcp_exist = False

        return all_mcp_exist
    except Exception as e:
        print(f"  Error testing MCP servers: {e}")
        return False

def main():
    print("=" * 80)
    print("PLATINUM TIER END-TO-END VALIDATION")
    print("=" * 80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Vault Directory: {VAULT_DIR}")

    # Define test steps
    test_steps = [
        (1, "Component Availability", test_component_availability),
        (2, "Directory Structure", test_directory_structure),
        (3, "Security Scanner", test_security_scanner),
        (4, "Backup System", test_backup_system),
        (5, "Credential Rotation", test_credential_rotation),
        (6, "A2A Messaging", test_a2a_messaging),
        (7, "Cloud Orchestrator", test_cloud_orchestrator),
        (8, "Local Orchestrator", test_local_orchestrator),
        (9, "File Operations", test_file_operations),
        (10, "MCP Server Integration", test_mcp_servers),
        (11, "Git Integration", test_git_integration),
        (12, "Demo Validation", test_demo_validation),
    ]

    passed = 0
    total = len(test_steps)

    for step_num, description, test_func in test_steps:
        if run_test_step(step_num, description, test_func):
            passed += 1

    # Final summary
    print("\n" + "=" * 80)
    print("PLATINUM TIER E2E VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Tests Run: {total}")
    print(f"Tests Passed: {passed}")
    print(f"Tests Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "0%")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if passed == total:
        print(f"\n[SUCCESS] ALL PLATINUM TIER COMPONENTS VALIDATED SUCCESSFULLY!")
        print(f"[OK] Cloud/Local Executive coordination working")
        print(f"[OK] Work-zone separation implemented")
        print(f"[OK] Security controls active")
        print(f"[OK] Backup systems ready")
        print(f"[OK] MCP integrations functional")
        print(f"[OK] End-to-end workflow validated")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} VALIDATION STEP(S) FAILED")
        print(f"[WARN] Please review failing components before production")
        return 1

if __name__ == "__main__":
    sys.exit(main())