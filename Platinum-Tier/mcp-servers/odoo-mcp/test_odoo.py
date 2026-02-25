#!/usr/bin/env python3
"""
Test Odoo MCP — Create a sample invoice via JSON-RPC.

Usage:
    python test_odoo.py              # Dry-run test (default)
    python test_odoo.py --live       # Live test against running Odoo
"""

import json
import sys
import subprocess
from pathlib import Path

ODOO_MCP = Path(__file__).parent / "odoo_mcp.py"


def send_jsonrpc(request):
    """Send a single JSON-RPC request to odoo_mcp.py via stdin/stdout."""
    proc = subprocess.run(
        [sys.executable, str(ODOO_MCP)],
        input=json.dumps(request) + "\n",
        capture_output=True, text=True, timeout=30
    )
    if proc.returncode != 0 and proc.stderr:
        print(f"STDERR: {proc.stderr[:500]}")
    for line in proc.stdout.strip().split("\n"):
        if line.strip():
            return json.loads(line)
    return None


def main():
    live = "--live" in sys.argv
    mode = "LIVE" if live else "DRY_RUN"
    print(f"=== Odoo MCP Test ({mode}) ===\n")

    # ── Test 1: Initialize ──
    print("1. Initialize MCP server...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    if resp and "result" in resp:
        print(f"   Server: {resp['result']['name']} v{resp['result']['version']}")
        print(f"   Tools:  {resp['result']['capabilities']['tools']}")
    else:
        print(f"   ERROR: {resp}")
        return

    # ── Test 2: List tools ──
    print("\n2. List available tools...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    if resp and "result" in resp:
        for tool in resp["result"]["tools"]:
            print(f"   - {tool['name']}: {tool['description']}")
    else:
        print(f"   ERROR: {resp}")

    # ── Test 3: Create sample invoice ──
    print("\n3. Create sample invoice...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "create_invoice",
        "arguments": {
            "partner_name": "GIAIC Hackathon Corp",
            "lines": [
                {"description": "AI Employee Vault - Gold Tier Setup", "quantity": 1, "price_unit": 2500},
                {"description": "MCP Server Integration", "quantity": 3, "price_unit": 500}
            ],
            "currency": "USD"
        }
    }})
    if resp and "result" in resp:
        data = json.loads(resp["result"]["content"][0]["text"])
        inv = data.get("invoice", {})
        print(f"   Invoice: {inv.get('name', 'N/A')}")
        print(f"   Partner: {inv.get('partner', 'N/A')}")
        print(f"   Total:   ${inv.get('amount_total', 0):,.2f}")
        print(f"   State:   {inv.get('state', 'N/A')}")
        print(f"   DryRun:  {data.get('dry_run', 'N/A')}")
    else:
        print(f"   ERROR: {resp}")

    # ── Test 4: Get account summary ──
    print("\n4. Get account summary...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
        "name": "get_account_summary",
        "arguments": {}
    }})
    if resp and "result" in resp:
        data = json.loads(resp["result"]["content"][0]["text"])
        s = data.get("summary", {})
        print(f"   Receivable:  ${s.get('total_receivable', 0):,.2f}")
        print(f"   Revenue MTD: ${s.get('total_revenue_mtd', 0):,.2f}")
        print(f"   Outstanding: {s.get('outstanding_invoices', 0)} invoices")
        print(f"   Period:      {s.get('period', 'N/A')}")
    else:
        print(f"   ERROR: {resp}")

    # ── Test 5: Get transactions ──
    print("\n5. Get transactions...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
        "name": "get_transactions",
        "arguments": {}
    }})
    if resp and "result" in resp:
        data = json.loads(resp["result"]["content"][0]["text"])
        print(f"   Total transactions: {data.get('count', 0)}")
        for t in data.get("transactions", [])[:3]:
            print(f"   - [{t['type']}] {t['name']} | {t['partner']} | ${t['amount']:,.2f}")
    else:
        print(f"   ERROR: {resp}")

    # ── Test 6: Search partners ──
    print("\n6. Search partners for 'acme'...")
    resp = send_jsonrpc({"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {
        "name": "search_partners",
        "arguments": {"query": "acme"}
    }})
    if resp and "result" in resp:
        data = json.loads(resp["result"]["content"][0]["text"])
        for p in data.get("partners", []):
            print(f"   - {p['name']} ({p['email']})")
    else:
        print(f"   ERROR: {resp}")

    print(f"\n=== Test Complete ({mode}) ===")


if __name__ == "__main__":
    main()
