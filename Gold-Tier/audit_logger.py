#!/usr/bin/env python3
"""
Audit Logger (Gold Tier) — Centralized Structured Logging per Spec 6.3

Every action in the vault is logged as structured JSON to data/Logs/YYYY-MM-DD.json.
This module is the SINGLE source of truth for audit logging — all skills, watchers,
MCP servers, and infrastructure call this module instead of writing JSON directly.

Features:
  - Exact Spec 6.3 JSON format (8 base fields + 4 enhanced Gold fields)
  - Thread-safe append to daily JSON log files
  - 90-day auto-retention (configurable via AUDIT_RETENTION_DAYS)
  - Convenience functions: log_action, log_error, log_approval, log_mcp_call
  - Correlation IDs link related entries across a task lifecycle
  - Duration tracking for performance metrics
  - Backward compatible: Bronze skills can still call basic log_action

Format per Spec 6.3:
    {
        "timestamp": "2026-02-18T10:00:00.000Z",
        "action_type": "email_send",
        "actor": "Autonomous_Employee",
        "target": "client@email",
        "parameters": {},
        "approval_status": "approved",
        "approved_by": "human",
        "result": "success",
        "severity": "INFO",
        "correlation_id": "TASK_20260218_001",
        "duration_ms": 1250,
        "error_trace": null
    }

Usage:
    from audit_logger import log_action, log_error, log_approval, log_mcp_call

    # Basic action log
    log_action("task_created", actor="gmail_watcher", target="EMAIL_20260218.md")

    # With all Gold fields
    log_action("invoice_created", actor="odoo_mcp", target="INV/2026/0001",
               parameters={"partner": "Acme", "amount": 5000},
               result="success", severity="INFO",
               correlation_id="TASK_001", duration_ms=340)

    # Error logging
    log_error("mcp_call_failed", actor="social_mcp", target="post_to_facebook",
              error=some_exception, correlation_id="TASK_002")

    # Approval tracking
    log_approval("email_send", target="client@email.com",
                 approved_by="human", approval_status="approved")

    # MCP tool call logging
    log_mcp_call("odoo", "get_invoices", args={"state": "posted"},
                 result="success", duration_ms=120)

    # Retention cleanup
    from audit_logger import cleanup_old_logs
    cleanup_old_logs()  # Deletes logs older than AUDIT_RETENTION_DAYS

Run standalone:
    python audit_logger.py --test      # Self-test (8 tests)
    python audit_logger.py --cleanup   # Run retention cleanup now
    python audit_logger.py --stats     # Show log statistics
"""

import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, Union

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
LOGS_DIR = VAULT_DIR / "data" / "Logs"
AUDIT_RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "90"))

# Thread lock for safe concurrent writes to the same daily log file
_write_lock = threading.Lock()

# Severity levels (ordered)
SEVERITY_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL")


# ── CORE: APPEND LOG ENTRY ───────────────────────────────────────────────
def _append_entry(entry: dict) -> bool:
    """Thread-safe append of a single JSON entry to today's log file.

    Reads the existing JSON array, appends the new entry, writes back.
    Creates the file/directory if they don't exist.

    Returns True on success, False on failure.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"

    with _write_lock:
        try:
            existing = []
            if log_file.exists():
                content = log_file.read_text(encoding="utf-8").strip()
                if content:
                    existing = json.loads(content)
                    if not isinstance(existing, list):
                        existing = [existing]
            existing.append(entry)
            log_file.write_text(
                json.dumps(existing, indent=2, default=str),
                encoding="utf-8",
            )
            return True
        except (json.JSONDecodeError, OSError) as e:
            # Last resort: try to write just this entry
            try:
                log_file.write_text(
                    json.dumps([entry], indent=2, default=str),
                    encoding="utf-8",
                )
            except OSError:
                pass
            return False


def _build_entry(
    action_type: str,
    actor: str = "system",
    target: str = "",
    parameters: Optional[dict] = None,
    approval_status: Optional[str] = None,
    approved_by: Optional[str] = None,
    result: str = "success",
    severity: str = "INFO",
    correlation_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_trace: Optional[str] = None,
) -> dict:
    """Build a Spec 6.3 compliant log entry dict."""
    severity = severity.upper() if severity else "INFO"
    if severity not in SEVERITY_LEVELS:
        severity = "INFO"

    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") +
                     f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
        "action_type": action_type,
        "actor": actor,
        "target": target,
        "parameters": parameters or {},
        "approval_status": approval_status,
        "approved_by": approved_by,
        "result": result,
        # Gold enhanced fields
        "severity": severity,
        "correlation_id": correlation_id,
        "duration_ms": duration_ms,
        "error_trace": error_trace,
    }


# ── PUBLIC API: CONVENIENCE FUNCTIONS ────────────────────────────────────
def log_action(
    action_type: str,
    actor: str = "system",
    target: str = "",
    parameters: Optional[dict] = None,
    result: str = "success",
    severity: str = "INFO",
    correlation_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> bool:
    """Log a general action (task creation, file move, MCP call, etc.).

    Args:
        action_type: What happened (e.g. "task_created", "file_moved", "invoice_created")
        actor: Who did it (e.g. "gmail_watcher", "odoo_mcp", "Autonomous_Employee")
        target: What was acted on (e.g. "EMAIL_20260218.md", "INV/2026/0001")
        parameters: Additional context as a dict
        result: Outcome ("success", "failure", "partial", "skipped")
        severity: DEBUG, INFO, WARN, ERROR, CRITICAL
        correlation_id: Links related entries for a single task lifecycle
        duration_ms: How long the action took in milliseconds

    Returns:
        True if logged successfully, False otherwise.
    """
    entry = _build_entry(
        action_type=action_type,
        actor=actor,
        target=target,
        parameters=parameters,
        result=result,
        severity=severity,
        correlation_id=correlation_id,
        duration_ms=duration_ms,
    )
    return _append_entry(entry)


def log_error(
    action_type: str,
    actor: str = "system",
    target: str = "",
    error: Optional[Exception] = None,
    parameters: Optional[dict] = None,
    severity: str = "ERROR",
    correlation_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> bool:
    """Log an error event with stack trace capture.

    Args:
        action_type: What failed (e.g. "mcp_call_failed", "watcher_crash")
        actor: Which component failed
        target: What was being acted on
        error: The exception object (stack trace auto-captured)
        parameters: Additional context
        severity: ERROR or CRITICAL (default ERROR)
        correlation_id: Task correlation ID
        duration_ms: How long before failure

    Returns:
        True if logged successfully.
    """
    error_trace = None
    if error:
        error_trace = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    entry = _build_entry(
        action_type=action_type,
        actor=actor,
        target=target,
        parameters=parameters,
        result=f"error: {error}" if error else "error",
        severity=severity,
        correlation_id=correlation_id,
        duration_ms=duration_ms,
        error_trace=error_trace,
    )
    return _append_entry(entry)


def log_approval(
    action_type: str,
    target: str = "",
    approved_by: str = "human",
    approval_status: str = "approved",
    actor: str = "hitl_watcher",
    parameters: Optional[dict] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Log an approval/rejection event (HITL actions).

    Args:
        action_type: What was approved (e.g. "email_send", "social_post", "invoice_create")
        target: The specific item (e.g. "client@email.com", "INV/2026/0001")
        approved_by: Who approved ("human", or a specific name)
        approval_status: "approved", "rejected", "pending"
        actor: Which component processed it
        parameters: Additional context
        correlation_id: Task correlation ID

    Returns:
        True if logged successfully.
    """
    entry = _build_entry(
        action_type=action_type,
        actor=actor,
        target=target,
        parameters=parameters,
        approval_status=approval_status,
        approved_by=approved_by,
        result=approval_status,
        severity="INFO" if approval_status == "approved" else "WARN",
        correlation_id=correlation_id,
    )
    return _append_entry(entry)


def log_mcp_call(
    server: str,
    tool: str,
    args: Optional[dict] = None,
    result: str = "success",
    error: Optional[Exception] = None,
    duration_ms: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> bool:
    """Log an MCP server tool call (convenience wrapper).

    Args:
        server: MCP server name (e.g. "odoo", "social", "email")
        tool: Tool name (e.g. "get_invoices", "post_to_facebook")
        args: Tool arguments
        result: Outcome
        error: Exception if failed
        duration_ms: Call duration
        correlation_id: Task correlation ID

    Returns:
        True if logged successfully.
    """
    if error:
        return log_error(
            action_type=f"mcp.{server}.{tool}",
            actor=f"{server}_mcp",
            target=tool,
            error=error,
            parameters=args,
            correlation_id=correlation_id,
            duration_ms=duration_ms,
        )

    return log_action(
        action_type=f"mcp.{server}.{tool}",
        actor=f"{server}_mcp",
        target=tool,
        parameters=args,
        result=result,
        correlation_id=correlation_id,
        duration_ms=duration_ms,
    )


# ── RETENTION: AUTO-DELETE OLD LOGS ──────────────────────────────────────
def cleanup_old_logs(retention_days: Optional[int] = None) -> dict:
    """Delete JSON audit log files older than retention_days.

    Only deletes YYYY-MM-DD.json files (not .log files or state files).

    Args:
        retention_days: Override for AUDIT_RETENTION_DAYS (default 90).

    Returns:
        Dict with "deleted" (list of filenames) and "kept" (count).
    """
    days = retention_days if retention_days is not None else AUDIT_RETENTION_DAYS
    cutoff = datetime.now() - timedelta(days=days)
    deleted = []
    kept = 0

    if not LOGS_DIR.exists():
        return {"deleted": [], "kept": 0, "retention_days": days}

    for log_file in LOGS_DIR.glob("????-??-??.json"):
        try:
            # Parse date from filename
            file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
            if file_date < cutoff:
                log_file.unlink()
                deleted.append(log_file.name)
            else:
                kept += 1
        except (ValueError, OSError):
            kept += 1  # Don't delete files we can't parse

    return {"deleted": deleted, "kept": kept, "retention_days": days}


# ── STATS ────────────────────────────────────────────────────────────────
def get_log_stats() -> dict:
    """Get statistics about the audit log files."""
    if not LOGS_DIR.exists():
        return {"total_files": 0, "total_entries": 0, "date_range": None}

    log_files = sorted(LOGS_DIR.glob("????-??-??.json"))
    total_entries = 0
    severity_counts = {s: 0 for s in SEVERITY_LEVELS}
    actor_counts = {}

    for lf in log_files:
        try:
            content = lf.read_text(encoding="utf-8").strip()
            if content:
                entries = json.loads(content)
                if isinstance(entries, list):
                    total_entries += len(entries)
                    for e in entries:
                        sev = e.get("severity", "INFO")
                        if sev in severity_counts:
                            severity_counts[sev] += 1
                        actor = e.get("actor", "unknown")
                        actor_counts[actor] = actor_counts.get(actor, 0) + 1
        except (json.JSONDecodeError, OSError):
            pass

    date_range = None
    if log_files:
        date_range = f"{log_files[0].stem} to {log_files[-1].stem}"

    return {
        "total_files": len(log_files),
        "total_entries": total_entries,
        "date_range": date_range,
        "severity_counts": severity_counts,
        "top_actors": dict(sorted(actor_counts.items(), key=lambda x: -x[1])[:10]),
        "retention_days": AUDIT_RETENTION_DAYS,
    }


# ── SELF-TEST ────────────────────────────────────────────────────────────
def _self_test() -> bool:
    """Run self-tests for audit_logger module."""
    import time as _time

    print("=" * 60)
    print("  AUDIT LOGGER SELF-TEST (Spec 6.3)")
    print("=" * 60)

    passed = 0
    total = 0

    # Test 1: log_action basic
    total += 1
    ok = log_action("test.basic_action", actor="self_test", target="test_target")
    print(f"  [{'PASS' if ok else 'FAIL'}] log_action basic write")
    if ok: passed += 1

    # Test 2: log_action with all Gold fields
    total += 1
    ok = log_action(
        "test.full_action",
        actor="self_test",
        target="full_target",
        parameters={"key": "value", "count": 42},
        result="success",
        severity="INFO",
        correlation_id="TEST_CORR_001",
        duration_ms=123,
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] log_action with all Gold fields")
    if ok: passed += 1

    # Test 3: log_error with exception
    total += 1
    try:
        raise ValueError("Test error for audit logger")
    except ValueError as e:
        ok = log_error(
            "test.error_action",
            actor="self_test",
            target="error_target",
            error=e,
            correlation_id="TEST_CORR_002",
        )
    print(f"  [{'PASS' if ok else 'FAIL'}] log_error with exception + stack trace")
    if ok: passed += 1

    # Test 4: log_approval
    total += 1
    ok = log_approval(
        "test.email_send",
        target="test@example.com",
        approved_by="human",
        approval_status="approved",
        correlation_id="TEST_CORR_003",
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] log_approval (HITL)")
    if ok: passed += 1

    # Test 5: log_mcp_call success
    total += 1
    ok = log_mcp_call(
        "odoo", "get_invoices",
        args={"state": "posted"},
        result="success",
        duration_ms=340,
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] log_mcp_call success")
    if ok: passed += 1

    # Test 6: log_mcp_call error
    total += 1
    ok = log_mcp_call(
        "social", "post_to_facebook",
        args={"message": "test"},
        error=ConnectionError("API timeout"),
        duration_ms=5000,
    )
    print(f"  [{'PASS' if ok else 'FAIL'}] log_mcp_call error")
    if ok: passed += 1

    # Test 7: Verify JSON format matches Spec 6.3
    total += 1
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"
    try:
        content = log_file.read_text(encoding="utf-8").strip()
        entries = json.loads(content)
        last = entries[-1] if entries else {}
        required_fields = [
            "timestamp", "action_type", "actor", "target",
            "parameters", "approval_status", "approved_by", "result",
            "severity", "correlation_id", "duration_ms", "error_trace",
        ]
        ok = all(field in last for field in required_fields)
        missing = [f for f in required_fields if f not in last]
        if missing:
            print(f"  [FAIL] Spec 6.3 format — missing: {missing}")
        else:
            print(f"  [PASS] Spec 6.3 format — all 12 fields present")
    except Exception as e:
        ok = False
        print(f"  [FAIL] Spec 6.3 format — {e}")
    if ok: passed += 1

    # Test 8: cleanup_old_logs (dry check — nothing should be deleted on fresh install)
    total += 1
    result = cleanup_old_logs()
    ok = isinstance(result, dict) and "deleted" in result and "kept" in result
    print(f"  [{'PASS' if ok else 'FAIL'}] cleanup_old_logs: "
          f"{len(result.get('deleted', []))} deleted, {result.get('kept', 0)} kept "
          f"({result.get('retention_days', '?')}d retention)")
    if ok: passed += 1

    print(f"\n  Result: {passed}/{total} tests passed\n")
    return passed == total


def _print_stats():
    """Print log statistics."""
    stats = get_log_stats()
    print("=" * 60)
    print("  AUDIT LOG STATISTICS")
    print("=" * 60)
    print(f"  Total log files:  {stats['total_files']}")
    print(f"  Total entries:    {stats['total_entries']}")
    print(f"  Date range:       {stats['date_range'] or 'none'}")
    print(f"  Retention:        {stats['retention_days']} days")
    print()
    print("  Severity breakdown:")
    for sev, count in stats.get("severity_counts", {}).items():
        if count > 0:
            print(f"    {sev:<10s} {count}")
    print()
    print("  Top actors:")
    for actor, count in stats.get("top_actors", {}).items():
        print(f"    {actor:<30s} {count}")
    print("=" * 60)


# ── MAIN ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audit Logger (Gold Tier) — Spec 6.3")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument("--cleanup", action="store_true", help="Run retention cleanup now")
    parser.add_argument("--stats", action="store_true", help="Show log statistics")
    args = parser.parse_args()

    if args.test:
        success = _self_test()
        sys.exit(0 if success else 1)
    elif args.cleanup:
        result = cleanup_old_logs()
        print(f"Cleanup complete: {len(result['deleted'])} deleted, {result['kept']} kept")
        for f in result["deleted"]:
            print(f"  Deleted: {f}")
    elif args.stats:
        _print_stats()
    else:
        print("Audit Logger (Gold Tier) — Spec 6.3 Centralized Logging")
        print()
        print("Usage:")
        print("  python audit_logger.py --test      Run self-tests (8 tests)")
        print("  python audit_logger.py --cleanup   Delete logs older than 90 days")
        print("  python audit_logger.py --stats     Show log statistics")
        print()
        print("Import in code:")
        print("  from audit_logger import log_action, log_error, log_approval, log_mcp_call")
