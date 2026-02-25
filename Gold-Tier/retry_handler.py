#!/usr/bin/env python3
"""
Retry Handler & Error Recovery (Gold Tier)

Per hackathon spec Section 7.2:
  - with_retry decorator with exponential backoff (3 attempts: 2s, 4s, 8s)
  - Error classification: Transient, Auth, Logic
  - Quarantine on permanent failure (moves to data/Quarantine/)
  - Never auto-retry payments or invoice creation
  - ERROR_{id}.md alert files for human attention
  - Integrates with skill-error-recovery and skill-audit-logger

Usage:
    from retry_handler import with_retry, classify_error, quarantine_file

    @with_retry(max_attempts=3, backoff_base=2)
    def flaky_api_call():
        ...

    # Manual quarantine
    quarantine_file(Path("data/Needs_Action/bad_file.md"), reason="Parse error")

    # Classify and handle
    error_type = classify_error(some_exception)
"""

import functools
import json
import logging
import os
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ── AUDIT LOGGER INTEGRATION ─────────────────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
QUARANTINE_DIR = VAULT_DIR / "data" / "Quarantine"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"
LOGS_DIR = VAULT_DIR / "data" / "Logs"

MAX_RETRY_ATTEMPTS = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))
QUARANTINE_ON_FAILURE = os.environ.get("QUARANTINE_ON_FAILURE", "true").lower() == "true"
BACKOFF_BASE = int(os.environ.get("RETRY_BACKOFF_BASE", "2"))

# Actions that must NEVER be auto-retried (require human review)
NO_RETRY_ACTIONS = frozenset([
    "create_invoice",
    "create_payment",
    "update_payment",
    "send_email",
    "post_to_facebook",
    "post_to_instagram",
    "post_tweet",
    "approve_task",
    "delete_file",
])

logger = logging.getLogger("RetryHandler")


# ── ERROR CLASSIFICATION ──────────────────────────────────────────────────
class ErrorType:
    TRANSIENT = "transient"     # Network timeout, rate limit, 5xx — retry
    AUTH = "auth"               # 401/403, expired token — alert human
    LOGIC = "logic"             # Bad input, parse error, 4xx — review queue
    UNKNOWN = "unknown"         # Unclassified — quarantine


def classify_error(error: Exception) -> str:
    """Classify an error into Transient, Auth, Logic, or Unknown.

    Returns one of ErrorType constants to determine retry strategy.
    """
    msg = str(error).lower()
    err_type = type(error).__name__.lower()

    # Transient errors — safe to retry
    transient_signals = [
        "timeout", "timed out", "connection reset", "connection refused",
        "connection aborted", "temporary failure", "rate limit",
        "429", "500", "502", "503", "504", "service unavailable",
        "server error", "retry", "econnreset", "econnrefused",
        "network", "dns", "ssl", "handshake",
    ]
    if any(s in msg for s in transient_signals):
        return ErrorType.TRANSIENT
    if any(s in err_type for s in ["timeout", "connection", "network", "ssl"]):
        return ErrorType.TRANSIENT

    # Auth errors — never retry, alert human
    auth_signals = [
        "401", "403", "unauthorized", "forbidden", "authentication",
        "invalid token", "expired token", "access denied", "permission",
        "oauth", "credentials", "login required",
    ]
    if any(s in msg for s in auth_signals):
        return ErrorType.AUTH

    # Logic errors — bad input, don't retry
    logic_signals = [
        "400", "404", "422", "validation", "invalid", "parse error",
        "json", "malformed", "missing required", "not found",
        "type error", "value error", "key error", "index error",
        "frontmatter", "yaml",
    ]
    if any(s in msg for s in logic_signals):
        return ErrorType.LOGIC
    if isinstance(error, (ValueError, TypeError, KeyError, IndexError)):
        return ErrorType.LOGIC

    return ErrorType.UNKNOWN


# ── QUARANTINE ────────────────────────────────────────────────────────────
def quarantine_file(
    file_path: Path,
    reason: str,
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None,
) -> Optional[Path]:
    """Move a file to data/Quarantine/ and create an ERROR alert.

    Args:
        file_path: Path to the file to quarantine.
        reason: Human-readable reason for quarantine.
        error: Optional exception that caused the quarantine.
        correlation_id: Optional ID for log correlation.

    Returns:
        Path to the quarantined file, or None if quarantine failed.
    """
    if not QUARANTINE_ON_FAILURE:
        logger.warning(f"Quarantine disabled, skipping: {file_path.name}")
        return None

    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    quarantine_name = f"QUARANTINE_{file_path.stem}_{today}{file_path.suffix}"
    quarantine_path = QUARANTINE_DIR / quarantine_name

    try:
        if file_path.exists():
            shutil.move(str(file_path), str(quarantine_path))
            logger.info(f"Quarantined: {file_path.name} -> {quarantine_name}")
        else:
            # File doesn't exist, create a placeholder in quarantine
            quarantine_path.write_text(
                f"---\noriginal: {file_path.name}\nreason: {reason}\n---\n",
                encoding="utf-8",
            )
            logger.warning(f"File not found, created quarantine placeholder: {quarantine_name}")
    except OSError as e:
        logger.error(f"Failed to quarantine {file_path.name}: {e}")
        return None

    # Create ERROR alert in Needs_Action
    _create_error_alert(
        original_file=file_path.name,
        quarantine_file=quarantine_name,
        reason=reason,
        error=error,
        correlation_id=correlation_id,
    )

    # Log the quarantine event
    _log_recovery_event(
        action="quarantine",
        target=file_path.name,
        reason=reason,
        error=error,
        correlation_id=correlation_id,
    )

    return quarantine_path


def _create_error_alert(
    original_file: str,
    quarantine_file: str,
    reason: str,
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None,
):
    """Create an ERROR_{id}.md alert file in Needs_Action for human attention."""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    error_id = now.strftime("%Y%m%d_%H%M%S")
    filename = f"ERROR_{error_id}.md"
    file_path = NEEDS_ACTION_DIR / filename

    error_type = classify_error(error) if error else "unknown"
    error_trace = traceback.format_exception(type(error), error, error.__traceback__) if error else []

    content = f"""---
type: error_alert
status: pending
priority: high
error_type: {error_type}
original_file: {original_file}
quarantine_file: {quarantine_file}
correlation_id: {correlation_id or 'none'}
created: {now.strftime("%Y-%m-%dT%H:%M:%SZ")}
---

## Error Alert: {reason}

**Original File:** {original_file}
**Quarantined To:** {quarantine_file}
**Error Type:** {error_type}
**Correlation ID:** {correlation_id or 'N/A'}

### Details

{str(error) if error else 'No exception details available.'}

### Stack Trace

```
{''.join(error_trace) if error_trace else 'No stack trace available.'}
```

### Required Action

- Review the quarantined file in `data/Quarantine/{quarantine_file}`
- Determine if the issue is recoverable
- Either fix and move back to `data/Needs_Action/` or delete from quarantine
"""

    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"Created error alert: {filename}")
    except OSError as e:
        logger.error(f"Failed to create error alert: {e}")


def _log_recovery_event(
    action: str,
    target: str,
    reason: str,
    error: Optional[Exception] = None,
    correlation_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
):
    """Log a recovery event via centralized audit_logger (Spec 6.3).

    Falls back to inline JSON write if audit_logger is not importable.
    """
    severity = "WARN" if action == "retry" else "ERROR"
    result = "quarantined" if action == "quarantine" else action

    if HAS_AUDIT_LOGGER:
        if error:
            _audit_log_error(
                action_type=f"error_recovery.{action}",
                actor="retry_handler",
                target=target,
                error=error,
                parameters={"reason": reason},
                severity=severity,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
            )
        else:
            log_action(
                action_type=f"error_recovery.{action}",
                actor="retry_handler",
                target=target,
                parameters={"reason": reason},
                result=result,
                severity=severity,
                correlation_id=correlation_id,
                duration_ms=duration_ms,
            )
        return

    # Fallback: inline JSON write (pre-Gold compatibility)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"

    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action_type": f"error_recovery.{action}",
        "actor": "retry_handler",
        "target": target,
        "parameters": {"reason": reason},
        "approval_status": None,
        "approved_by": None,
        "result": result,
        "severity": severity,
        "correlation_id": correlation_id,
        "duration_ms": duration_ms,
        "error_trace": str(error) if error else None,
    }

    try:
        existing = []
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8").strip()
            if content:
                existing = json.loads(content)
        existing.append(entry)
        log_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to write recovery log: {e}")


# ── WITH_RETRY DECORATOR ─────────────────────────────────────────────────
def with_retry(
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    backoff_base: int = BACKOFF_BASE,
    action_name: Optional[str] = None,
    correlation_id: Optional[str] = None,
    on_failure: Optional[Callable] = None,
):
    """Decorator for retrying functions with exponential backoff.

    Per spec Section 7.2:
      - 3 attempts by default (2s, 4s, 8s delays)
      - Only retries Transient errors
      - Auth and Logic errors fail immediately
      - Never retries NO_RETRY_ACTIONS (payments, invoices, posts)
      - Logs each attempt
      - Calls on_failure callback on permanent failure

    Args:
        max_attempts: Maximum retry attempts (default 3).
        backoff_base: Base for exponential backoff in seconds (default 2).
        action_name: Name of the action for NO_RETRY_ACTIONS checking.
        correlation_id: Correlation ID for log entries.
        on_failure: Callback(error, attempts) on permanent failure.

    Usage:
        @with_retry(max_attempts=3, action_name="get_invoices")
        def fetch_invoices():
            return odoo_client.get_invoices()

        @with_retry(action_name="send_email")  # blocked — in NO_RETRY_ACTIONS
        def send_email():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            resolved_action = action_name or func.__name__

            # Safety check: never auto-retry sensitive actions
            if resolved_action in NO_RETRY_ACTIONS:
                logger.warning(
                    f"Action '{resolved_action}' is in NO_RETRY_ACTIONS — executing once without retry"
                )
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"[{resolved_action}] Failed (no retry allowed): {e}")
                    _log_recovery_event(
                        action="no_retry_failure",
                        target=resolved_action,
                        reason=f"NO_RETRY_ACTIONS: {e}",
                        error=e,
                        correlation_id=correlation_id,
                    )
                    if on_failure:
                        on_failure(e, 1)
                    raise

            last_error = None
            for attempt in range(1, max_attempts + 1):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        duration = int((time.time() - start_time) * 1000)
                        logger.info(
                            f"[{resolved_action}] Succeeded on attempt {attempt} ({duration}ms)"
                        )
                        _log_recovery_event(
                            action="retry_success",
                            target=resolved_action,
                            reason=f"Succeeded on attempt {attempt}",
                            correlation_id=correlation_id,
                            duration_ms=duration,
                        )
                    return result

                except Exception as e:
                    last_error = e
                    duration = int((time.time() - start_time) * 1000)
                    error_type = classify_error(e)

                    logger.warning(
                        f"[{resolved_action}] Attempt {attempt}/{max_attempts} failed "
                        f"({error_type}): {e}"
                    )

                    _log_recovery_event(
                        action="retry",
                        target=resolved_action,
                        reason=f"Attempt {attempt}/{max_attempts}: {e}",
                        error=e,
                        correlation_id=correlation_id,
                        duration_ms=duration,
                    )

                    # Only retry transient errors
                    if error_type != ErrorType.TRANSIENT:
                        logger.error(
                            f"[{resolved_action}] Non-transient error ({error_type}), "
                            f"not retrying: {e}"
                        )
                        break

                    # Don't sleep after the last attempt
                    if attempt < max_attempts:
                        delay = backoff_base ** attempt
                        logger.info(f"[{resolved_action}] Retrying in {delay}s...")
                        time.sleep(delay)

            # All attempts exhausted or non-transient error
            logger.error(
                f"[{resolved_action}] Permanently failed after {attempt} attempt(s): {last_error}"
            )
            _log_recovery_event(
                action="permanent_failure",
                target=resolved_action,
                reason=f"All {attempt} attempts exhausted: {last_error}",
                error=last_error,
                correlation_id=correlation_id,
            )

            if on_failure:
                on_failure(last_error, attempt)

            raise last_error

        return wrapper
    return decorator


# ── ASYNC VARIANT ─────────────────────────────────────────────────────────
def with_retry_async(
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    backoff_base: int = BACKOFF_BASE,
    action_name: Optional[str] = None,
    correlation_id: Optional[str] = None,
):
    """Async version of with_retry for use with async/await functions."""
    import asyncio

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            resolved_action = action_name or func.__name__

            if resolved_action in NO_RETRY_ACTIONS:
                return await func(*args, **kwargs)

            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_type = classify_error(e)
                    if error_type != ErrorType.TRANSIENT:
                        break
                    if attempt < max_attempts:
                        delay = backoff_base ** attempt
                        await asyncio.sleep(delay)

            raise last_error

        return wrapper
    return decorator


# ── STANDALONE TEST ───────────────────────────────────────────────────────
def _self_test():
    """Run self-tests for retry_handler module."""
    print("=" * 60)
    print("  RETRY HANDLER SELF-TEST")
    print("=" * 60)

    passed = 0
    total = 0

    # Test 1: classify_error — Transient
    total += 1
    e = ConnectionError("Connection refused by server")
    result = classify_error(e)
    ok = result == ErrorType.TRANSIENT
    print(f"  [{'PASS' if ok else 'FAIL'}] classify_error(ConnectionError) = {result}")
    if ok: passed += 1

    # Test 2: classify_error — Auth
    total += 1
    e = Exception("401 Unauthorized: invalid token")
    result = classify_error(e)
    ok = result == ErrorType.AUTH
    print(f"  [{'PASS' if ok else 'FAIL'}] classify_error(401 Unauthorized) = {result}")
    if ok: passed += 1

    # Test 3: classify_error — Logic
    total += 1
    e = ValueError("Invalid input: missing required field 'name'")
    result = classify_error(e)
    ok = result == ErrorType.LOGIC
    print(f"  [{'PASS' if ok else 'FAIL'}] classify_error(ValueError) = {result}")
    if ok: passed += 1

    # Test 4: with_retry — success on first try
    total += 1
    call_count = [0]

    @with_retry(max_attempts=3, backoff_base=1, action_name="test_success")
    def always_works():
        call_count[0] += 1
        return "ok"

    result = always_works()
    ok = result == "ok" and call_count[0] == 1
    print(f"  [{'PASS' if ok else 'FAIL'}] with_retry success: called {call_count[0]} time(s)")
    if ok: passed += 1

    # Test 5: with_retry — transient then success
    total += 1
    attempt_count = [0]

    @with_retry(max_attempts=3, backoff_base=1, action_name="test_transient_recovery")
    def fails_once():
        attempt_count[0] += 1
        if attempt_count[0] == 1:
            raise ConnectionError("timeout — transient")
        return "recovered"

    result = fails_once()
    ok = result == "recovered" and attempt_count[0] == 2
    print(f"  [{'PASS' if ok else 'FAIL'}] with_retry transient recovery: {attempt_count[0]} attempts")
    if ok: passed += 1

    # Test 6: with_retry — auth error no retry
    total += 1
    auth_count = [0]

    @with_retry(max_attempts=3, backoff_base=1, action_name="test_auth_fail")
    def auth_fails():
        auth_count[0] += 1
        raise Exception("403 Forbidden: access denied")

    try:
        auth_fails()
        ok = False
    except Exception:
        ok = auth_count[0] == 1  # Should NOT have retried
    print(f"  [{'PASS' if ok else 'FAIL'}] with_retry auth fail: {auth_count[0]} attempt(s) (no retry)")
    if ok: passed += 1

    # Test 7: NO_RETRY_ACTIONS blocks retry
    total += 1
    pay_count = [0]

    @with_retry(max_attempts=3, backoff_base=1, action_name="create_payment")
    def risky_payment():
        pay_count[0] += 1
        raise ConnectionError("timeout")

    try:
        risky_payment()
        ok = False
    except ConnectionError:
        ok = pay_count[0] == 1  # Executed once, not retried
    print(f"  [{'PASS' if ok else 'FAIL'}] NO_RETRY_ACTIONS (create_payment): {pay_count[0]} attempt(s)")
    if ok: passed += 1

    # Test 8: quarantine_file
    total += 1
    test_file = VAULT_DIR / "data" / "Needs_Action" / "_test_quarantine_target.md"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("---\ntype: test\n---\nTest file for quarantine\n", encoding="utf-8")

    q_path = quarantine_file(
        test_file,
        reason="Self-test quarantine",
        error=ValueError("test error"),
        correlation_id="TEST_001",
    )
    ok = q_path is not None and q_path.exists() and not test_file.exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] quarantine_file: {'moved' if ok else 'failed'}")
    if ok:
        passed += 1
        # Cleanup
        try:
            q_path.unlink()
        except OSError:
            pass

    # Cleanup error alert
    for f in NEEDS_ACTION_DIR.glob("ERROR_*.md"):
        try:
            f.unlink()
        except OSError:
            pass

    print(f"\n  Result: {passed}/{total} tests passed\n")
    return passed == total


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if "--test" in sys.argv or "--self-test" in sys.argv:
        success = _self_test()
        sys.exit(0 if success else 1)
    else:
        print("Retry Handler (Gold Tier)")
        print("Usage:")
        print("  python retry_handler.py --test    Run self-tests")
        print()
        print("Import in code:")
        print("  from retry_handler import with_retry, classify_error, quarantine_file")
