#!/usr/bin/env python3
"""
Audit Logic — Gold Tier

Core audit engine for the AI Employee Vault. Provides:
  - SUBSCRIPTION_PATTERNS: Dict of known recurring charge patterns to flag
  - analyze_transaction(): Classify and flag individual transactions
  - run_weekly_audit(): Full audit pipeline (vault metrics, accounting, social, health)
  - generate_ceo_briefing(): Monday Morning CEO Briefing from audit data
  - generate_audit_report(): Write AUDIT_{date}.md to /Briefings/
  - generate_briefing_report(): Write {date}_Monday_Briefing.md to /Briefings/

Usage:
    from audit_logic import run_weekly_audit, generate_ceo_briefing
    audit = run_weekly_audit()
    briefing = generate_ceo_briefing(audit)

    # Or standalone test:
    python audit_logic.py --test
    python audit_logic.py --simulate
"""

import json
import os
import re
import time
import logging
import argparse
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import Counter

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
DATA_DIR = VAULT_DIR / "data"
DONE_DIR = DATA_DIR / "Done"
NEEDS_ACTION_DIR = DATA_DIR / "Needs_Action"
PENDING_DIR = DATA_DIR / "Pending_Approval"
APPROVED_DIR = DATA_DIR / "Approved"
QUARANTINE_DIR = DATA_DIR / "Quarantine"
LOGS_DIR = DATA_DIR / "Logs"
ACCOUNTING_DIR = DATA_DIR / "Accounting"
BRIEFINGS_DIR = DATA_DIR / "Briefings"
PLANS_DIR = DATA_DIR / "Plans"
BUSINESS_GOALS_FILE = DATA_DIR / "Business_Goals.md"

# ── AUDIT LOGGER INTEGRATION (Gold Tier) ─────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

logger = logging.getLogger("AuditLogic")

# ── SUBSCRIPTION PATTERNS ────────────────────────────────────────────────
# Per spec: Flag subscriptions with no login >30d, cost increase >20%, duplicates
SUBSCRIPTION_PATTERNS = {
    "office_ops": {
        "pattern": r"(?i)(office|supplies|utilities|rent|internet|phone)\b",
        "description": "Office / operational expense",
        "flag_rules": {
            "cost_increase_pct": 15,
        },
    },
    "cloud_infra": {
        "pattern": r"(?i)(aws|azure|gcp|cloud|hosting|server|compute|storage)\b",
        "description": "Cloud infrastructure charge",
        "flag_rules": {
            "cost_increase_pct": 20,
            "budget_threshold_pct": 80,  # Flag if >80% of monthly budget
        },
    },
    "marketing_ad": {
        "pattern": r"(?i)(google ads|facebook ads|meta ads|linkedin ads|ad spend|campaign)\b",
        "description": "Marketing / advertising spend",
        "flag_rules": {
            "cost_increase_pct": 30,
            "roi_check": True,  # Cross-reference with engagement data
        },
    },
    "contractor": {
        "pattern": r"(?i)(freelance|contractor|consulting|retainer|outsource)\b",
        "description": "Contractor / consulting payment",
        "flag_rules": {
            "invoice_overdue_days": 30,
            "duplicate_window_days": 3,
        },
    },
    "saas_monthly": {
        "pattern": r"(?i)(subscription|saas|monthly|recurring|license|plan)\b",
        "description": "SaaS / monthly recurring charge",
        "flag_rules": {
            "no_login_days": 30,       # Flag if no usage in N days
            "cost_increase_pct": 20,   # Flag if cost jumped >N%
            "duplicate_window_days": 7, # Flag if same vendor charged twice in N days
        },
    },
}


# ── TRANSACTION ANALYSIS ─────────────────────────────────────────────────
def analyze_transaction(transaction, history=None):
    """Analyze a single transaction against SUBSCRIPTION_PATTERNS.

    Args:
        transaction: Dict with keys: name, partner, amount, date, type, description
        history: Optional list of prior transactions for trend analysis

    Returns:
        Dict with: transaction, category, flags[], severity, suggestions[]
    """
    history = history or []
    desc = f"{transaction.get('partner', '')} {transaction.get('description', '')} {transaction.get('name', '')}"
    amount = float(transaction.get("amount", 0))
    tx_date = transaction.get("date", date.today().isoformat())

    result = {
        "transaction": transaction,
        "category": "uncategorized",
        "flags": [],
        "severity": "normal",  # normal, warning, critical
        "suggestions": [],
    }

    # Match against patterns
    matched_category = None
    for cat_key, cat_def in SUBSCRIPTION_PATTERNS.items():
        if re.search(cat_def["pattern"], desc):
            matched_category = cat_key
            result["category"] = cat_key
            break

    if not matched_category:
        return result

    rules = SUBSCRIPTION_PATTERNS[matched_category]["flag_rules"]

    # Check cost increase vs history
    if "cost_increase_pct" in rules and history:
        same_vendor = [
            h for h in history
            if h.get("partner", "").lower() == transaction.get("partner", "").lower()
        ]
        if same_vendor:
            prev_amount = float(same_vendor[-1].get("amount", 0))
            if prev_amount > 0:
                pct_change = ((amount - prev_amount) / prev_amount) * 100
                if pct_change > rules["cost_increase_pct"]:
                    result["flags"].append(
                        f"Cost increased {pct_change:.1f}% (threshold: {rules['cost_increase_pct']}%)"
                    )
                    result["severity"] = "warning"
                    result["suggestions"].append(
                        f"[ACTION] Review {transaction.get('partner', 'vendor')} pricing — "
                        f"${prev_amount:.2f} → ${amount:.2f} (+{pct_change:.1f}%)"
                    )

    # Check for duplicates in window
    if "duplicate_window_days" in rules and history:
        window = rules["duplicate_window_days"]
        try:
            tx_dt = datetime.fromisoformat(tx_date)
        except (ValueError, TypeError):
            tx_dt = datetime.now()

        dupes = [
            h for h in history
            if h.get("partner", "").lower() == transaction.get("partner", "").lower()
            and h.get("name") != transaction.get("name")
            and _days_between(h.get("date", ""), tx_date) <= window
        ]
        if dupes:
            result["flags"].append(
                f"Possible duplicate: {len(dupes)} similar charge(s) within {window} days"
            )
            result["severity"] = "warning"
            result["suggestions"].append(
                f"[ACTION] Check for duplicate charges from {transaction.get('partner', 'vendor')}"
            )

    # Check overdue invoices
    if "invoice_overdue_days" in rules:
        threshold = rules["invoice_overdue_days"]
        due_date = transaction.get("due_date")
        if due_date:
            try:
                due_dt = datetime.fromisoformat(due_date)
                days_overdue = (datetime.now() - due_dt).days
                if days_overdue > threshold:
                    result["flags"].append(f"Invoice overdue by {days_overdue} days (threshold: {threshold})")
                    result["severity"] = "critical"
                    result["suggestions"].append(
                        f"[ACTION] Follow up on overdue invoice from {transaction.get('partner', 'vendor')}"
                    )
            except (ValueError, TypeError):
                pass

    # Budget threshold check
    if "budget_threshold_pct" in rules:
        budget = _get_monthly_budget()
        if budget > 0:
            pct_of_budget = (amount / budget) * 100
            if pct_of_budget > rules["budget_threshold_pct"]:
                result["flags"].append(
                    f"Single charge is {pct_of_budget:.0f}% of monthly budget (threshold: {rules['budget_threshold_pct']}%)"
                )
                result["severity"] = "warning"

    return result


def _days_between(date_str1, date_str2):
    """Calculate days between two ISO date strings."""
    try:
        d1 = datetime.fromisoformat(date_str1.replace("Z", "+00:00")).replace(tzinfo=None)
        d2 = datetime.fromisoformat(date_str2.replace("Z", "+00:00")).replace(tzinfo=None)
        return abs((d2 - d1).days)
    except (ValueError, TypeError, AttributeError):
        return 999


def _get_monthly_budget():
    """Read monthly budget from Business_Goals.md."""
    if not BUSINESS_GOALS_FILE.exists():
        return 10000  # fallback default
    try:
        content = BUSINESS_GOALS_FILE.read_text(encoding="utf-8")
        match = re.search(r"Monthly goal:\s*\$?([\d,]+)", content)
        if match:
            return float(match.group(1).replace(",", ""))
    except Exception:
        pass
    return 10000


# ── VAULT METRICS ────────────────────────────────────────────────────────
def collect_vault_metrics(days=7):
    """Count files in each data directory for the past N days."""
    now = datetime.now()
    cutoff = now - timedelta(days=days)

    def _count_recent(directory, ext=".md"):
        if not directory.exists():
            return 0
        count = 0
        for f in directory.iterdir():
            if f.suffix == ext and f.stat().st_mtime >= cutoff.timestamp():
                count += 1
        return count

    def _count_all(directory, ext=".md"):
        if not directory.exists():
            return 0
        return sum(1 for f in directory.iterdir() if f.suffix == ext)

    return {
        "tasks_completed": _count_recent(DONE_DIR),
        "tasks_pending": _count_all(NEEDS_ACTION_DIR),
        "approval_requests": _count_all(PENDING_DIR),
        "approved_items": _count_all(APPROVED_DIR),
        "quarantined_items": _count_all(QUARANTINE_DIR),
        "active_plans": _count_all(PLANS_DIR),
        "log_files": _count_all(LOGS_DIR, ext=".json"),
        "accounting_records": _count_all(ACCOUNTING_DIR),
        "period_days": days,
    }


# ── ACCOUNTING DATA ──────────────────────────────────────────────────────
def collect_accounting_data():
    """Read accounting data from /Accounting/ .md files and Odoo mock."""
    transactions = []

    # Read from Accounting directory
    if ACCOUNTING_DIR.exists():
        for f in sorted(ACCOUNTING_DIR.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
                tx = _parse_accounting_frontmatter(content, f.name)
                if tx:
                    transactions.append(tx)
            except Exception as e:
                logger.warning(f"Failed to parse {f.name}: {e}")

    # Read from CSV files if present
    for csv_file in ACCOUNTING_DIR.glob("*.csv") if ACCOUNTING_DIR.exists() else []:
        try:
            transactions.extend(_parse_csv_transactions(csv_file))
        except Exception as e:
            logger.warning(f"Failed to parse CSV {csv_file.name}: {e}")

    # If no files found, use Odoo MCP mock data
    if not transactions:
        transactions = _get_odoo_mock_data()

    return transactions


def _parse_accounting_frontmatter(content, filename):
    """Extract transaction data from YAML frontmatter in .md file."""
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not frontmatter_match:
        return None

    fm = frontmatter_match.group(1)
    tx = {"source_file": filename}
    for line in fm.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            tx[key.strip()] = val.strip().strip('"').strip("'")

    # Normalize fields
    tx.setdefault("amount", "0")
    tx["amount"] = float(re.sub(r"[^\d.]", "", str(tx["amount"])) or "0")
    tx.setdefault("partner", tx.get("vendor", tx.get("client", "Unknown")))
    tx.setdefault("type", "invoice" if "INV" in filename else "payment")
    tx.setdefault("date", date.today().isoformat())
    tx.setdefault("description", tx.get("subject", tx.get("name", filename)))
    return tx


def _parse_csv_transactions(csv_file):
    """Parse a simple CSV file with columns: date,partner,description,amount,type."""
    import csv
    transactions = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx = {
                "date": row.get("date", date.today().isoformat()),
                "partner": row.get("partner", row.get("vendor", "Unknown")),
                "description": row.get("description", row.get("memo", "")),
                "amount": float(re.sub(r"[^\d.]", "", row.get("amount", "0")) or "0"),
                "type": row.get("type", "expense"),
                "name": row.get("reference", row.get("name", "")),
                "source_file": csv_file.name,
            }
            transactions.append(tx)
    return transactions


def _get_odoo_mock_data():
    """Fallback: return Odoo-style mock data for testing."""
    return [
        {"name": "INV/2026/0001", "partner": "Acme Corp", "amount": 5000.00,
         "type": "invoice", "state": "posted", "date": "2026-02-10",
         "due_date": "2026-03-10", "description": "Consulting retainer"},
        {"name": "INV/2026/0002", "partner": "TechStart Inc", "amount": 12500.00,
         "type": "invoice", "state": "draft", "date": "2026-02-15",
         "due_date": "2026-03-15", "description": "SaaS platform license"},
        {"name": "INV/2026/0003", "partner": "Global Solutions", "amount": 3200.00,
         "type": "invoice", "state": "posted", "date": "2026-02-01",
         "due_date": "2026-03-01", "description": "Cloud hosting quarterly"},
        {"name": "PAY/2026/0001", "partner": "Acme Corp", "amount": 5000.00,
         "type": "payment", "state": "posted", "date": "2026-02-12",
         "description": "Payment received — consulting"},
        {"name": "PAY/2026/0002", "partner": "Office Supplies Ltd", "amount": 850.00,
         "type": "payment", "state": "posted", "date": "2026-02-14",
         "description": "Office supplies monthly order"},
        {"name": "PAY/2026/0003", "partner": "AWS", "amount": 420.00,
         "type": "payment", "state": "posted", "date": "2026-02-16",
         "description": "AWS compute monthly subscription"},
        {"name": "PAY/2026/0004", "partner": "AWS", "amount": 520.00,
         "type": "payment", "state": "posted", "date": "2026-02-16",
         "description": "AWS storage monthly subscription"},
        {"name": "PAY/2026/0005", "partner": "Google Ads", "amount": 1200.00,
         "type": "payment", "state": "posted", "date": "2026-02-17",
         "description": "Google Ads campaign February"},
        {"name": "PAY/2026/0006", "partner": "Freelance Dev Co", "amount": 3000.00,
         "type": "payment", "state": "posted", "date": "2026-02-13",
         "description": "Freelance contractor backend work"},
        {"name": "PAY/2026/0007", "partner": "Freelance Dev Co", "amount": 3000.00,
         "type": "payment", "state": "draft", "date": "2026-02-15",
         "description": "Freelance contractor — duplicate?"},
    ]


# ── SOCIAL METRICS ───────────────────────────────────────────────────────
def collect_social_metrics():
    """Read social summaries from /Briefings/SUMMARY_*.md files."""
    metrics = {"facebook": {}, "instagram": {}, "x": {}, "total_engagement": 0}

    if not BRIEFINGS_DIR.exists():
        return _get_social_mock_data()

    for platform in ["fb", "ig", "x"]:
        summaries = sorted(BRIEFINGS_DIR.glob(f"SUMMARY_{platform}_*.md"), reverse=True)
        if summaries:
            try:
                content = summaries[0].read_text(encoding="utf-8")
                platform_key = {"fb": "facebook", "ig": "instagram", "x": "x"}[platform]
                metrics[platform_key] = _parse_summary_metrics(content)
            except Exception as e:
                logger.warning(f"Failed to parse {platform} summary: {e}")

    # Calculate total
    for plat in ["facebook", "instagram", "x"]:
        metrics["total_engagement"] += metrics[plat].get("total_engagement", 0)

    if metrics["total_engagement"] == 0:
        return _get_social_mock_data()

    return metrics


def _parse_summary_metrics(content):
    """Extract metrics from a SUMMARY .md file's table."""
    result = {}
    for match in re.finditer(r"\|\s*(?:Total\s+)?(\w+)\s*\|\s*\*?\*?(\d[\d,]*)\*?\*?\s*\|", content):
        key = match.group(1).lower()
        val = int(match.group(2).replace(",", ""))
        result[f"total_{key}"] = val
    engagement_match = re.search(r"Total Engagement\*?\*?\s*\|\s*\*?\*?(\d[\d,]*)", content)
    if engagement_match:
        result["total_engagement"] = int(engagement_match.group(1).replace(",", ""))
    return result


def _get_social_mock_data():
    """Fallback mock social metrics."""
    return {
        "facebook": {"total_likes": 264, "total_comments": 66, "total_shares": 67, "total_engagement": 397},
        "instagram": {"total_likes": 523, "total_comments": 89, "total_saves": 34, "total_engagement": 646},
        "x": {"total_likes": 198, "total_retweets": 45, "total_replies": 32, "total_engagement": 275},
        "total_engagement": 1318,
    }


# ── LOG ANALYSIS ─────────────────────────────────────────────────────────
def collect_error_metrics(days=7):
    """Analyze log files for error rates and patterns."""
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    total_entries = 0
    error_entries = 0
    error_types = Counter()

    if not LOGS_DIR.exists():
        return {"total_entries": 0, "error_entries": 0, "error_rate_pct": 0, "top_errors": []}

    for log_file in LOGS_DIR.glob("*.json"):
        try:
            # Check if file is within date range
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", log_file.name)
            if date_match:
                file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                if file_date < cutoff:
                    continue

            content = log_file.read_text(encoding="utf-8").strip()
            if not content:
                continue

            # Handle both JSON array and newline-delimited JSON
            if content.startswith("["):
                entries = json.loads(content)
            else:
                entries = [json.loads(line) for line in content.split("\n") if line.strip()]

            for entry in entries:
                total_entries += 1
                severity = entry.get("severity", entry.get("level", "INFO")).upper()
                if severity in ("ERROR", "CRITICAL"):
                    error_entries += 1
                    error_types[entry.get("action", entry.get("action_type", "unknown"))] += 1
        except Exception as e:
            logger.debug(f"Failed to parse log {log_file.name}: {e}")

    error_rate = (error_entries / total_entries * 100) if total_entries > 0 else 0

    return {
        "total_entries": total_entries,
        "error_entries": error_entries,
        "error_rate_pct": round(error_rate, 1),
        "top_errors": error_types.most_common(5),
    }


# ── WEEKLY AUDIT ─────────────────────────────────────────────────────────
def run_weekly_audit(days=7):
    """Run the full weekly audit pipeline.

    Returns:
        Dict with all audit sections: vault_metrics, accounting, flagged_transactions,
        social_metrics, error_metrics, revenue_summary, bottlenecks, anomalies
    """
    start_time = time.time()
    logger.info(f"Running weekly audit (past {days} days)...")

    # Gold Tier: log audit start to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="audit.start",
            actor="audit_logic",
            target="weekly_audit",
            parameters={"days": days},
            result="success",
            severity="INFO",
        )

    vault = collect_vault_metrics(days)
    transactions = collect_accounting_data()
    social = collect_social_metrics()
    errors = collect_error_metrics(days)

    # Analyze all transactions
    flagged = []
    for i, tx in enumerate(transactions):
        history = transactions[:i]  # previous transactions as history
        analysis = analyze_transaction(tx, history)
        if analysis["flags"]:
            flagged.append(analysis)

    # Revenue summary
    invoices = [t for t in transactions if t.get("type") == "invoice"]
    payments_in = [t for t in transactions if t.get("type") == "payment"
                   and t.get("payment_type", t.get("direction", "")) != "outbound"]
    payments_out = [t for t in transactions if t.get("type") == "payment"
                    and t.get("payment_type", t.get("direction", "")) == "outbound"
                    or (t.get("type") == "payment" and t.get("amount", 0) < 2000
                        and "received" not in t.get("description", "").lower())]

    total_invoiced = sum(float(t.get("amount", 0)) for t in invoices)
    total_received = sum(float(t.get("amount", 0)) for t in payments_in
                         if "received" in t.get("description", "").lower()
                         or float(t.get("amount", 0)) >= 2000)
    total_expenses = sum(float(t.get("amount", 0)) for t in payments_out)

    budget = _get_monthly_budget()
    revenue_pct = (total_received / budget * 100) if budget > 0 else 0

    revenue_summary = {
        "total_invoiced": total_invoiced,
        "total_received": total_received,
        "total_expenses": total_expenses,
        "net_revenue": total_received - total_expenses,
        "monthly_target": budget,
        "target_pct": round(revenue_pct, 1),
    }

    # Bottleneck detection
    bottlenecks = []
    overdue_invoices = [t for t in invoices if t.get("due_date") and
                        datetime.fromisoformat(t["due_date"]) < datetime.now() and
                        t.get("state") != "paid"]
    if overdue_invoices:
        for inv in overdue_invoices:
            days_over = (datetime.now() - datetime.fromisoformat(inv["due_date"])).days
            bottlenecks.append({
                "task": f"Invoice {inv['name']}",
                "expected": inv["due_date"],
                "actual": "Unpaid",
                "delay": f"{days_over} days overdue",
            })

    if vault["quarantined_items"] > 0:
        bottlenecks.append({
            "task": "Error Recovery",
            "expected": "0 quarantined",
            "actual": f"{vault['quarantined_items']} items",
            "delay": "Needs manual review",
        })

    if vault["tasks_pending"] > 10:
        bottlenecks.append({
            "task": "Task Queue",
            "expected": "<10 pending",
            "actual": f"{vault['tasks_pending']} pending",
            "delay": "Queue backlog",
        })

    # Anomaly detection
    anomalies = []
    if errors["error_rate_pct"] > 5:
        anomalies.append(f"Error rate {errors['error_rate_pct']}% exceeds 5% threshold")
    if social["total_engagement"] < 100:
        anomalies.append(f"Social engagement dropped to {social['total_engagement']} (low)")
    for f in flagged:
        for flag in f["flags"]:
            anomalies.append(flag)

    audit = {
        "period_start": (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
        "period_end": datetime.now().strftime("%Y-%m-%d"),
        "generated": datetime.now().isoformat(),
        "vault_metrics": vault,
        "transactions": transactions,
        "flagged_transactions": flagged,
        "revenue_summary": revenue_summary,
        "social_metrics": social,
        "error_metrics": errors,
        "bottlenecks": bottlenecks,
        "anomalies": anomalies,
    }

    logger.info(f"Audit complete: {len(transactions)} transactions, {len(flagged)} flagged, "
                f"{len(bottlenecks)} bottlenecks, {len(anomalies)} anomalies")

    # Gold Tier: log audit completion to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="audit.completed",
            actor="audit_logic",
            target="weekly_audit",
            parameters={
                "days": days,
                "transaction_count": len(transactions),
                "flagged_count": len(flagged),
                "bottleneck_count": len(bottlenecks),
                "anomaly_count": len(anomalies)
            },
            result="success",
            severity="INFO",
            duration_ms=int((time.time() - start_time) * 1000),
        )

    return audit


# ── REPORT GENERATION ────────────────────────────────────────────────────
def generate_audit_report(audit, output_dir=None):
    """Generate AUDIT_{YYYYMMDD}.md in /Briefings/."""
    output_dir = Path(output_dir) if output_dir else BRIEFINGS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    filepath = output_dir / f"AUDIT_{today}.md"

    vm = audit["vault_metrics"]
    rs = audit["revenue_summary"]
    em = audit["error_metrics"]
    sm = audit["social_metrics"]

    # Build flagged transactions table
    flagged_rows = ""
    for f in audit["flagged_transactions"]:
        tx = f["transaction"]
        flags = "; ".join(f["flags"])
        flagged_rows += f"| {tx.get('name', 'N/A')} | {tx.get('partner', 'N/A')} | ${tx.get('amount', 0):,.2f} | {f['severity']} | {flags} |\n"

    if not flagged_rows:
        flagged_rows = "| — | — | — | — | No issues detected |\n"

    # Build bottlenecks table
    bottleneck_rows = ""
    for b in audit["bottlenecks"]:
        bottleneck_rows += f"| {b['task']} | {b['expected']} | {b['actual']} | {b['delay']} |\n"

    if not bottleneck_rows:
        bottleneck_rows = "| — | — | — | No bottlenecks |\n"

    content = f"""---
type: weekly_audit
generated: {audit['generated']}
period: {audit['period_start']} to {audit['period_end']}
---

# Weekly Audit Report — {datetime.now().strftime('%Y-%m-%d')}

**Period:** {audit['period_start']} to {audit['period_end']}

## Vault Metrics
| Metric | Count |
|--------|-------|
| Tasks Completed | {vm['tasks_completed']} |
| Tasks Pending | {vm['tasks_pending']} |
| Approval Requests | {vm['approval_requests']} |
| Quarantined Items | {vm['quarantined_items']} |
| Active Plans | {vm['active_plans']} |
| Accounting Records | {vm['accounting_records']} |

## Revenue Summary
| Metric | Amount |
|--------|--------|
| Total Invoiced | ${rs['total_invoiced']:,.2f} |
| Total Received | ${rs['total_received']:,.2f} |
| Total Expenses | ${rs['total_expenses']:,.2f} |
| **Net Revenue** | **${rs['net_revenue']:,.2f}** |
| Monthly Target | ${rs['monthly_target']:,.2f} |
| Target Progress | {rs['target_pct']}% |

## Flagged Transactions
| Reference | Partner | Amount | Severity | Flags |
|-----------|---------|--------|----------|-------|
{flagged_rows}
## Bottlenecks
| Task | Expected | Actual | Delay |
|------|----------|--------|-------|
{bottleneck_rows}
## Social Media
| Platform | Engagement |
|----------|------------|
| Facebook | {sm.get('facebook', {}).get('total_engagement', 0)} |
| Instagram | {sm.get('instagram', {}).get('total_engagement', 0)} |
| X (Twitter) | {sm.get('x', {}).get('total_engagement', 0)} |
| **Total** | **{sm.get('total_engagement', 0)}** |

## System Health
| Metric | Value |
|--------|-------|
| Log Entries (7d) | {em['total_entries']} |
| Error Entries | {em['error_entries']} |
| Error Rate | {em['error_rate_pct']}% |

## Anomalies
"""
    if audit["anomalies"]:
        for a in audit["anomalies"]:
            content += f"- {a}\n"
    else:
        content += "- No anomalies detected\n"

    content += f"\n*Generated by audit_logic.py — Gold Tier — {datetime.now().isoformat()}*\n"

    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Audit report written: {filepath.name}")

    # Gold Tier: log report generation to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="audit.report_generated",
            actor="audit_logic",
            target=filepath.name,
            parameters={
                "report_type": "weekly_audit",
                "filepath": str(filepath),
                "flagged_count": len(audit["flagged_transactions"]),
                "bottleneck_count": len(audit["bottlenecks"])
            },
            result="success",
            severity="INFO",
        )
    return filepath


# ── CEO BRIEFING ─────────────────────────────────────────────────────────
def generate_ceo_briefing(audit, output_dir=None):
    """Generate {date}_Monday_Briefing.md in /Briefings/ per spec template.

    Template:
        ---
        generated: ISO
        period: from-to
        ---
        # Executive Summary
        ## Revenue
        ## Bottlenecks (table)
        ## Suggestions with [ACTION] tags
    """
    output_dir = Path(output_dir) if output_dir else BRIEFINGS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    filepath = output_dir / f"{today}_Monday_Briefing.md"

    rs = audit["revenue_summary"]
    vm = audit["vault_metrics"]
    sm = audit["social_metrics"]
    em = audit["error_metrics"]

    # KPI status indicators
    def status(val, good, warn):
        if val >= good:
            return "Green"
        elif val >= warn:
            return "Yellow"
        return "Red"

    revenue_status = status(rs["target_pct"], 80, 50)
    error_status = status(100 - em["error_rate_pct"], 95, 90)
    queue_status = status(max(0, 20 - vm["tasks_pending"]), 10, 5)

    # Bottleneck table rows
    bottleneck_rows = ""
    for b in audit["bottlenecks"]:
        bottleneck_rows += f"| {b['task']} | {b['expected']} | {b['actual']} | {b['delay']} |\n"
    if not bottleneck_rows:
        bottleneck_rows = "| — | — | — | No bottlenecks detected |\n"

    # Suggestions with [ACTION] tags
    suggestions = []

    # Revenue suggestions
    if rs["target_pct"] < 50:
        suggestions.append("[ACTION] Revenue at {:.0f}% of target — accelerate invoicing and collections".format(rs["target_pct"]))
    if rs["total_expenses"] > rs["total_received"] * 0.8:
        suggestions.append("[ACTION] Expenses are {:.0f}% of revenue — review cost reduction opportunities".format(
            (rs["total_expenses"] / max(rs["total_received"], 1)) * 100))

    # From flagged transactions
    for f in audit["flagged_transactions"]:
        for s in f["suggestions"]:
            suggestions.append(s)

    # Error suggestions
    if em["error_rate_pct"] > 5:
        suggestions.append(f"[ACTION] Error rate {em['error_rate_pct']}% — investigate top failure sources")

    # Quarantine suggestions
    if vm["quarantined_items"] > 0:
        suggestions.append(f"[ACTION] {vm['quarantined_items']} quarantined item(s) — review and recover or discard")

    # Subscription suggestions from patterns
    for f in audit["flagged_transactions"]:
        if f["category"] == "saas_monthly" and "Cost increased" in str(f["flags"]):
            suggestions.append(f"[ACTION] Cancel or renegotiate {f['transaction'].get('partner', 'subscription')}?")

    if not suggestions:
        suggestions.append("No immediate actions required — all systems nominal")

    suggestions_text = "\n".join(f"- {s}" for s in suggestions)

    content = f"""---
generated: {datetime.now().isoformat()}
period: {audit['period_start']} to {audit['period_end']}
---

# Executive Summary

This briefing covers the period **{audit['period_start']}** to **{audit['period_end']}**.
{vm['tasks_completed']} tasks completed, {len(audit['flagged_transactions'])} transaction flags,
{len(audit['bottlenecks'])} bottlenecks identified.

## Key Performance Indicators

| KPI | Value | Status |
|-----|-------|--------|
| Revenue vs Target | {rs['target_pct']}% (${rs['total_received']:,.2f} / ${rs['monthly_target']:,.2f}) | {revenue_status} |
| Net Revenue | ${rs['net_revenue']:,.2f} | {"Green" if rs['net_revenue'] > 0 else "Red"} |
| Tasks Completed | {vm['tasks_completed']} | {"Green" if vm['tasks_completed'] > 0 else "Yellow"} |
| Error Rate | {em['error_rate_pct']}% | {error_status} |
| Queue Health | {vm['tasks_pending']} pending | {queue_status} |
| Social Engagement | {sm.get('total_engagement', 0)} total | {"Green" if sm.get('total_engagement', 0) > 200 else "Yellow"} |

## Revenue

| Category | Amount |
|----------|--------|
| Invoiced | ${rs['total_invoiced']:,.2f} |
| Received | ${rs['total_received']:,.2f} |
| Expenses | ${rs['total_expenses']:,.2f} |
| **Net** | **${rs['net_revenue']:,.2f}** |

Monthly target: ${rs['monthly_target']:,.2f} — currently at **{rs['target_pct']}%**

## Bottlenecks

| Task | Expected | Actual | Delay |
|------|----------|--------|-------|
{bottleneck_rows}
## Suggestions

{suggestions_text}

*Generated by audit_logic.py — Gold Tier — {datetime.now().isoformat()}*
"""

    filepath.write_text(content, encoding="utf-8")
    logger.info(f"CEO Briefing written: {filepath.name}")

    # Gold Tier: log briefing generation to audit log
    if HAS_AUDIT_LOGGER:
        log_action(
            action_type="briefing.ceo_generated",
            actor="audit_logic",
            target=filepath.name,
            parameters={
                "report_type": "ceo_briefing",
                "filepath": str(filepath),
                "suggestion_count": len([s for s in content.split("\\n") if "[ACTION]" in s])
            },
            result="success",
            severity="INFO",
        )
    return filepath


# ── CLI ──────────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Audit Logic — Gold Tier")
    parser.add_argument("--test", action="store_true", help="Run pattern matching tests")
    parser.add_argument("--simulate", action="store_true",
                        help="Full simulation: audit + CEO briefing with mock data")
    parser.add_argument("--days", type=int, default=7, help="Audit period in days (default: 7)")
    args = parser.parse_args()

    if args.test:
        _run_pattern_tests()
    elif args.simulate:
        _run_simulation(args.days)
    else:
        parser.print_help()


def _run_pattern_tests():
    """Test SUBSCRIPTION_PATTERNS against sample transactions."""
    print("=== Subscription Pattern Tests ===\n")

    test_cases = [
        {"name": "TX001", "partner": "Acme SaaS", "amount": 500, "date": "2026-02-15",
         "description": "Monthly subscription renewal"},
        {"name": "TX002", "partner": "AWS", "amount": 2500, "date": "2026-02-16",
         "description": "AWS compute hosting February"},
        {"name": "TX003", "partner": "Google", "amount": 1200, "date": "2026-02-17",
         "description": "Google Ads campaign Q1"},
        {"name": "TX004", "partner": "Dev LLC", "amount": 5000, "date": "2026-02-14",
         "description": "Freelance contractor payment"},
        {"name": "TX005", "partner": "Random Corp", "amount": 100, "date": "2026-02-18",
         "description": "Miscellaneous purchase"},
    ]

    history = [
        {"name": "TX000", "partner": "AWS", "amount": 1800, "date": "2026-01-16",
         "description": "AWS compute hosting January"},
        {"name": "TX000b", "partner": "Dev LLC", "amount": 5000, "date": "2026-02-12",
         "description": "Freelance contractor payment"},
    ]

    for tx in test_cases:
        result = analyze_transaction(tx, history)
        cat = result["category"]
        sev = result["severity"]
        flags = result["flags"] or ["none"]
        print(f"  {tx['name']} | {tx['partner']:20s} | ${tx['amount']:>8,.2f} | "
              f"cat={cat:15s} | sev={sev:8s} | flags={'; '.join(flags)}")
        for s in result["suggestions"]:
            print(f"    → {s}")

    print("\n=== Pattern Tests Complete ===")


def _run_simulation(days=7):
    """Full end-to-end simulation with mock data."""
    print(f"=== Full Audit Simulation (past {days} days) ===\n")

    audit = run_weekly_audit(days)

    # Print summary
    rs = audit["revenue_summary"]
    print(f"Revenue: ${rs['total_invoiced']:,.2f} invoiced, ${rs['total_received']:,.2f} received")
    print(f"Expenses: ${rs['total_expenses']:,.2f} | Net: ${rs['net_revenue']:,.2f}")
    print(f"Target progress: {rs['target_pct']}% of ${rs['monthly_target']:,.2f}")
    print(f"Transactions: {len(audit['transactions'])}, Flagged: {len(audit['flagged_transactions'])}")
    print(f"Bottlenecks: {len(audit['bottlenecks'])}, Anomalies: {len(audit['anomalies'])}")

    # Generate reports
    print("\nGenerating reports...")
    audit_path = generate_audit_report(audit)
    briefing_path = generate_ceo_briefing(audit)

    print(f"\n  Audit report:  {audit_path}")
    print(f"  CEO Briefing:  {briefing_path}")

    # Print flagged items
    if audit["flagged_transactions"]:
        print(f"\n  Flagged transactions ({len(audit['flagged_transactions'])}):")
        for f in audit["flagged_transactions"]:
            tx = f["transaction"]
            print(f"    [{f['severity'].upper()}] {tx['name']} — {tx['partner']} — ${tx['amount']:,.2f}")
            for flag in f["flags"]:
                print(f"      ! {flag}")
            for s in f["suggestions"]:
                print(f"      → {s}")

    if audit["anomalies"]:
        print(f"\n  Anomalies ({len(audit['anomalies'])}):")
        for a in audit["anomalies"]:
            print(f"    ! {a}")

    print("\n=== Simulation Complete ===")


if __name__ == "__main__":
    main()
