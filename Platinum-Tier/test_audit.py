#!/usr/bin/env python3
"""
Test Audit Simulation — Gold Tier

End-to-end test that:
  1. Tests SUBSCRIPTION_PATTERNS matching against sample transactions
  2. Runs the full weekly audit pipeline with mock data
  3. Generates AUDIT_{date}.md and {date}_Monday_Briefing.md in /Briefings/
  4. Verifies output files exist and contain expected sections
  5. Tests scheduler integration (--list-schedules)

Usage:
    python test_audit.py            # Run all tests
    python test_audit.py --verbose  # Show report contents
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from audit_logic import (
    SUBSCRIPTION_PATTERNS,
    analyze_transaction,
    run_weekly_audit,
    generate_audit_report,
    generate_ceo_briefing,
    collect_vault_metrics,
    collect_accounting_data,
    collect_social_metrics,
    collect_error_metrics,
)


def test_subscription_patterns():
    """Test 1: SUBSCRIPTION_PATTERNS dict matches correctly."""
    print("=" * 60)
    print("TEST 1: SUBSCRIPTION_PATTERNS Matching")
    print("=" * 60)

    test_data = [
        ("Monthly SaaS subscription renewal", "saas_monthly"),
        ("AWS compute hosting February", "cloud_infra"),
        ("Google Ads campaign Q1", "marketing_ad"),
        ("Freelance contractor backend work", "contractor"),
        ("Office supplies monthly order", "office_ops"),
        ("Random one-time purchase", "uncategorized"),
    ]

    import re
    passed = 0
    for desc, expected_cat in test_data:
        matched = "uncategorized"
        for cat_key, cat_def in SUBSCRIPTION_PATTERNS.items():
            if re.search(cat_def["pattern"], desc):
                matched = cat_key
                break
        status = "PASS" if matched == expected_cat else "FAIL"
        if status == "PASS":
            passed += 1
        print(f"  [{status}] '{desc}' → {matched} (expected: {expected_cat})")

    print(f"\n  Result: {passed}/{len(test_data)} patterns matched correctly\n")
    return passed == len(test_data)


def test_analyze_transaction():
    """Test 2: analyze_transaction flags issues correctly."""
    print("=" * 60)
    print("TEST 2: analyze_transaction() Flag Detection")
    print("=" * 60)

    # Transaction with cost spike (AWS $1800 → $2500 = +38.9%)
    history = [
        {"name": "TX_PREV", "partner": "AWS", "amount": 1800, "date": "2026-01-16",
         "description": "AWS compute hosting January"},
    ]
    tx_spike = {"name": "TX_CUR", "partner": "AWS", "amount": 2500, "date": "2026-02-16",
                "description": "AWS compute hosting February"}

    result = analyze_transaction(tx_spike, history)
    spike_pass = len(result["flags"]) > 0 and result["severity"] != "normal"
    print(f"  [{'PASS' if spike_pass else 'FAIL'}] Cost spike detection: "
          f"{result['flags'] or 'no flags'} (severity: {result['severity']})")

    # Transaction with duplicate (same vendor within 3 days)
    history_dup = [
        {"name": "TX_DUP1", "partner": "Freelance Dev Co", "amount": 3000, "date": "2026-02-12",
         "description": "Freelance contractor payment"},
    ]
    tx_dup = {"name": "TX_DUP2", "partner": "Freelance Dev Co", "amount": 3000, "date": "2026-02-14",
              "description": "Freelance contractor payment duplicate"}

    result_dup = analyze_transaction(tx_dup, history_dup)
    dup_pass = any("duplicate" in f.lower() for f in result_dup["flags"])
    print(f"  [{'PASS' if dup_pass else 'FAIL'}] Duplicate detection: "
          f"{result_dup['flags'] or 'no flags'}")

    # Clean transaction (no flags expected)
    tx_clean = {"name": "TX_CLEAN", "partner": "Random Corp", "amount": 100, "date": "2026-02-18",
                "description": "Miscellaneous purchase"}
    result_clean = analyze_transaction(tx_clean, [])
    clean_pass = result_clean["category"] == "uncategorized" and len(result_clean["flags"]) == 0
    print(f"  [{'PASS' if clean_pass else 'FAIL'}] Clean transaction: "
          f"category={result_clean['category']}, flags={result_clean['flags']}")

    # Check suggestions have [ACTION] tags
    action_pass = all(s.startswith("[ACTION]") for s in result["suggestions"])
    print(f"  [{'PASS' if action_pass else 'FAIL'}] Suggestions use [ACTION] tags: "
          f"{result['suggestions'] or 'none'}")

    total = sum([spike_pass, dup_pass, clean_pass, action_pass])
    print(f"\n  Result: {total}/4 flag tests passed\n")
    return total == 4


def test_data_collection():
    """Test 3: Data collection functions return valid structures."""
    print("=" * 60)
    print("TEST 3: Data Collection Functions")
    print("=" * 60)

    vault = collect_vault_metrics()
    vault_pass = all(k in vault for k in ["tasks_completed", "tasks_pending", "quarantined_items"])
    print(f"  [{'PASS' if vault_pass else 'FAIL'}] collect_vault_metrics: "
          f"{vault['tasks_completed']} done, {vault['tasks_pending']} pending, "
          f"{vault['quarantined_items']} quarantined")

    transactions = collect_accounting_data()
    tx_pass = len(transactions) > 0 and all("amount" in t for t in transactions)
    print(f"  [{'PASS' if tx_pass else 'FAIL'}] collect_accounting_data: "
          f"{len(transactions)} transactions loaded")

    social = collect_social_metrics()
    social_pass = "total_engagement" in social and social["total_engagement"] > 0
    print(f"  [{'PASS' if social_pass else 'FAIL'}] collect_social_metrics: "
          f"engagement={social['total_engagement']}")

    errors = collect_error_metrics()
    error_pass = all(k in errors for k in ["total_entries", "error_rate_pct"])
    print(f"  [{'PASS' if error_pass else 'FAIL'}] collect_error_metrics: "
          f"{errors['total_entries']} entries, {errors['error_rate_pct']}% error rate")

    total = sum([vault_pass, tx_pass, social_pass, error_pass])
    print(f"\n  Result: {total}/4 collection tests passed\n")
    return total == 4


def test_weekly_audit(verbose=False):
    """Test 4: Full weekly audit pipeline."""
    print("=" * 60)
    print("TEST 4: run_weekly_audit() Full Pipeline")
    print("=" * 60)

    audit = run_weekly_audit(days=7)

    sections = ["vault_metrics", "transactions", "flagged_transactions",
                "revenue_summary", "social_metrics", "error_metrics",
                "bottlenecks", "anomalies", "period_start", "period_end"]
    section_pass = all(k in audit for k in sections)
    print(f"  [{'PASS' if section_pass else 'FAIL'}] Audit contains all sections: "
          f"{len([k for k in sections if k in audit])}/{len(sections)}")

    rs = audit["revenue_summary"]
    revenue_pass = all(k in rs for k in ["total_invoiced", "total_received", "net_revenue", "monthly_target"])
    print(f"  [{'PASS' if revenue_pass else 'FAIL'}] Revenue summary: "
          f"invoiced=${rs.get('total_invoiced', 0):,.2f}, "
          f"net=${rs.get('net_revenue', 0):,.2f}, "
          f"target={rs.get('target_pct', 0)}%")

    flagged_pass = isinstance(audit["flagged_transactions"], list)
    print(f"  [{'PASS' if flagged_pass else 'FAIL'}] Flagged transactions: "
          f"{len(audit['flagged_transactions'])} issues found")

    bottleneck_pass = isinstance(audit["bottlenecks"], list)
    print(f"  [{'PASS' if bottleneck_pass else 'FAIL'}] Bottlenecks: "
          f"{len(audit['bottlenecks'])} detected")

    if verbose and audit["flagged_transactions"]:
        print("\n  Flagged details:")
        for f in audit["flagged_transactions"]:
            tx = f["transaction"]
            print(f"    [{f['severity'].upper()}] {tx['name']} — {tx.get('partner', '?')} — ${tx.get('amount', 0):,.2f}")
            for flag in f["flags"]:
                print(f"      ! {flag}")

    total = sum([section_pass, revenue_pass, flagged_pass, bottleneck_pass])
    print(f"\n  Result: {total}/4 audit tests passed\n")
    return total == 4, audit


def test_report_generation(audit, verbose=False):
    """Test 5: Report generation (AUDIT + CEO Briefing)."""
    print("=" * 60)
    print("TEST 5: Report Generation → /Briefings/")
    print("=" * 60)

    briefings_dir = PROJECT_ROOT / "data" / "Briefings"

    # Generate audit report
    audit_path = generate_audit_report(audit)
    audit_exists = audit_path.exists()
    audit_content = audit_path.read_text(encoding="utf-8") if audit_exists else ""
    audit_sections = all(s in audit_content for s in
                         ["Vault Metrics", "Revenue Summary", "Flagged Transactions",
                          "Bottlenecks", "Social Media", "System Health", "Anomalies"])
    print(f"  [{'PASS' if audit_exists else 'FAIL'}] AUDIT report created: {audit_path.name}")
    print(f"  [{'PASS' if audit_sections else 'FAIL'}] AUDIT contains all 7 sections")

    # Generate CEO briefing
    briefing_path = generate_ceo_briefing(audit)
    briefing_exists = briefing_path.exists()
    briefing_content = briefing_path.read_text(encoding="utf-8") if briefing_exists else ""
    briefing_sections = all(s in briefing_content for s in
                            ["Executive Summary", "Revenue", "Bottlenecks", "Suggestions"])
    briefing_has_frontmatter = briefing_content.startswith("---")
    briefing_has_actions = "[ACTION]" in briefing_content or "No immediate actions" in briefing_content
    briefing_has_tables = "| KPI" in briefing_content or "| Category" in briefing_content

    print(f"  [{'PASS' if briefing_exists else 'FAIL'}] CEO Briefing created: {briefing_path.name}")
    print(f"  [{'PASS' if briefing_sections else 'FAIL'}] Briefing has: Executive Summary, Revenue, Bottlenecks, Suggestions")
    print(f"  [{'PASS' if briefing_has_frontmatter else 'FAIL'}] Briefing has YAML frontmatter (generated, period)")
    print(f"  [{'PASS' if briefing_has_actions else 'FAIL'}] Briefing has [ACTION] suggestions")
    print(f"  [{'PASS' if briefing_has_tables else 'FAIL'}] Briefing uses tables for KPIs/Revenue")

    if verbose:
        print(f"\n  --- AUDIT REPORT ({audit_path.name}) ---")
        print(audit_content[:1500])
        print(f"\n  --- CEO BRIEFING ({briefing_path.name}) ---")
        print(briefing_content[:1500])

    total = sum([audit_exists, audit_sections, briefing_exists, briefing_sections,
                 briefing_has_frontmatter, briefing_has_actions, briefing_has_tables])
    print(f"\n  Result: {total}/7 report tests passed\n")
    return total == 7


def test_scheduler_integration():
    """Test 6: Scheduler lists Gold schedules."""
    print("=" * 60)
    print("TEST 6: Scheduler Integration")
    print("=" * 60)

    import subprocess
    scheduler_path = PROJECT_ROOT / "watcher" / "scheduler.py"

    try:
        result = subprocess.run(
            [sys.executable, str(scheduler_path), "--list-schedules"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr

        has_linkedin = "LinkedIn Draft" in output
        has_audit = "Weekly Audit" in output
        has_briefing = "CEO Briefing" in output

        print(f"  [{'PASS' if has_linkedin else 'FAIL'}] Scheduler lists LinkedIn Draft")
        print(f"  [{'PASS' if has_audit else 'FAIL'}] Scheduler lists Weekly Audit")
        print(f"  [{'PASS' if has_briefing else 'FAIL'}] Scheduler lists CEO Briefing")

        total = sum([has_linkedin, has_audit, has_briefing])
        print(f"\n  Result: {total}/3 scheduler tests passed\n")
        return total == 3
    except Exception as e:
        print(f"  [FAIL] Scheduler test error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Audit Simulation — Gold Tier")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full report contents")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("    AUDIT LOGIC TEST SIMULATION -- GOLD TIER")
    print("=" * 60)
    print()

    results = {}

    results["patterns"] = test_subscription_patterns()
    results["analyze"] = test_analyze_transaction()
    results["collection"] = test_data_collection()

    audit_pass, audit_data = test_weekly_audit(verbose=args.verbose)
    results["audit"] = audit_pass

    results["reports"] = test_report_generation(audit_data, verbose=args.verbose)
    results["scheduler"] = test_scheduler_integration()

    # Final summary
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    total_pass = sum(1 for v in results.values() if v)
    total_tests = len(results)

    for name, passed in results.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")

    print(f"\n  Overall: {total_pass}/{total_tests} test suites passed")

    if total_pass == total_tests:
        print("\n  All tests passed!")
    else:
        print(f"\n  {total_tests - total_pass} suite(s) failed — review output above")

    return 0 if total_pass == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
