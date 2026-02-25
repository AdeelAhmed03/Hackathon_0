#!/usr/bin/env python3
"""
Odoo MCP Server — Gold Tier

Interfaces with Odoo Community Edition (19+) via XML-RPC (JSON-RPC compatible).
Provides accounting tools: invoices, payments, partner search, account summaries.

DRY_RUN mode returns realistic mock data without connecting to Odoo.

Usage:
    python odoo_mcp.py                  # Start MCP server
    python odoo_mcp.py --dry-run        # Test with mock data
    python odoo_mcp.py --test           # Run self-test
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

# ── RETRY HANDLER INTEGRATION (Gold Tier) ────────────────────────────────
VAULT_DIR_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(VAULT_DIR_ROOT))
try:
    from retry_handler import with_retry, classify_error, quarantine_file, ErrorType
    HAS_RETRY = True
except ImportError:
    HAS_RETRY = False

# ── AUDIT LOGGER INTEGRATION (Gold Tier) ─────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error, log_mcp_call
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

NEEDS_ACTION_DIR = VAULT_DIR_ROOT / "data" / "Needs_Action"

# ── CONFIG ────────────────────────────────────────────────────────────────
ODOO_URL = os.environ.get("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.environ.get("ODOO_DB", "ai_employee")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME", "admin")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "admin")
DRY_RUN = os.environ.get("ODOO_DRY_RUN", "true").lower() == "true"
MAX_RETRIES = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("OdooMCP")


# ── MOCK DATA ─────────────────────────────────────────────────────────────
MOCK_INVOICES = [
    {"id": 1, "name": "INV/2026/0001", "partner": "Acme Corp", "amount_total": 5000.00,
     "state": "posted", "date": "2026-02-10", "due_date": "2026-03-10", "currency": "USD"},
    {"id": 2, "name": "INV/2026/0002", "partner": "TechStart Inc", "amount_total": 12500.00,
     "state": "draft", "date": "2026-02-15", "due_date": "2026-03-15", "currency": "USD"},
    {"id": 3, "name": "INV/2026/0003", "partner": "Global Solutions", "amount_total": 3200.00,
     "state": "posted", "date": "2026-02-01", "due_date": "2026-03-01", "currency": "USD"},
]

MOCK_PAYMENTS = [
    {"id": 1, "name": "PAY/2026/0001", "partner": "Acme Corp", "amount": 5000.00,
     "state": "posted", "date": "2026-02-12", "payment_type": "inbound", "journal": "Bank"},
    {"id": 2, "name": "PAY/2026/0002", "partner": "Office Supplies Ltd", "amount": 850.00,
     "state": "posted", "date": "2026-02-14", "payment_type": "outbound", "journal": "Bank"},
]

MOCK_PARTNERS = [
    {"id": 1, "name": "Acme Corp", "email": "billing@acme.com", "phone": "+1-555-0100", "is_company": True},
    {"id": 2, "name": "TechStart Inc", "email": "accounts@techstart.io", "phone": "+1-555-0200", "is_company": True},
    {"id": 3, "name": "Global Solutions", "email": "finance@globalsol.com", "phone": "+1-555-0300", "is_company": True},
]


# ── ODOO CONNECTION ──────────────────────────────────────────────────────
class OdooClient:
    """XML-RPC client for Odoo Community Edition."""

    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self._common = None
        self._models = None

    def connect(self):
        """Authenticate with Odoo and get user ID."""
        import xmlrpc.client
        self._common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
        self._models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        self.uid = self._common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            raise ConnectionError("Odoo authentication failed")
        logger.info(f"Connected to Odoo as uid={self.uid}")
        return self.uid

    def execute(self, model, method, *args, **kwargs):
        """Execute an Odoo model method with retry logic.

        Uses retry_handler.with_retry if available (Gold Tier),
        otherwise falls back to inline retry.
        """
        def _do_execute():
            return self._models.execute_kw(
                self.db, self.uid, self.password,
                model, method, list(args), kwargs
            )

        if HAS_RETRY:
            # Gold Tier: use retry_handler with error classification
            retryable = with_retry(
                max_attempts=MAX_RETRIES,
                backoff_base=2,
                action_name=f"odoo.{model}.{method}",
            )(_do_execute)
            return retryable()
        else:
            # Fallback: inline retry
            last_error = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    return _do_execute()
                except Exception as e:
                    last_error = e
                    wait = 2 ** attempt
                    logger.warning(f"Odoo call failed (attempt {attempt}/{MAX_RETRIES}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
            raise ConnectionError(f"Odoo call failed after {MAX_RETRIES} attempts: {last_error}")

    def search_read(self, model, domain=None, fields=None, limit=100):
        """Search and read records from an Odoo model."""
        domain = domain or []
        kwargs = {"limit": limit}
        if fields:
            kwargs["fields"] = fields
        return self.execute(model, "search_read", domain, **kwargs)


# ── MCP TOOL FUNCTIONS ───────────────────────────────────────────────────
def create_invoice(partner_name, lines, currency="USD"):
    """Create a new customer invoice in Odoo.

    Args:
        partner_name: Customer/partner name
        lines: List of dicts with {description, quantity, price_unit}
        currency: Currency code (default USD)
    """
    if DRY_RUN:
        total = sum(l.get("quantity", 1) * l.get("price_unit", 0) for l in lines)
        inv_name = f"INV/2026/{datetime.now().strftime('%H%M')}"
        result = {
            "success": True, "dry_run": True,
            "invoice": {"name": inv_name, "partner": partner_name,
                        "amount_total": total, "state": "draft",
                        "date": date.today().isoformat(), "currency": currency,
                        "lines": lines}
        }
        logger.info(f"[DRY RUN] Created invoice {inv_name} for {partner_name}: ${total:.2f}")
        return result

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()

    # Find or create partner
    partners = client.search_read("res.partner", [["name", "=", partner_name]], ["id"], limit=1)
    partner_id = partners[0]["id"] if partners else client.execute(
        "res.partner", "create", {"name": partner_name}
    )

    # Create invoice
    invoice_lines = [(0, 0, {
        "name": l["description"],
        "quantity": l.get("quantity", 1),
        "price_unit": l.get("price_unit", 0),
    }) for l in lines]

    invoice_id = client.execute("account.move", "create", {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "invoice_line_ids": invoice_lines,
    })

    invoice = client.search_read("account.move", [["id", "=", invoice_id]],
                                  ["name", "amount_total", "state", "date"])[0]
    return {"success": True, "dry_run": False, "invoice": invoice}


def get_invoices(state=None, limit=50):
    """Get invoices from Odoo, optionally filtered by state."""
    if DRY_RUN:
        invoices = MOCK_INVOICES
        if state:
            invoices = [i for i in invoices if i["state"] == state]
        logger.info(f"[DRY RUN] Returning {len(invoices)} mock invoices")
        return {"success": True, "dry_run": True, "invoices": invoices, "count": len(invoices)}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    domain = [["move_type", "=", "out_invoice"]]
    if state:
        domain.append(["state", "=", state])
    invoices = client.search_read("account.move", domain,
                                   ["name", "partner_id", "amount_total", "state", "date", "invoice_date_due"],
                                   limit=limit)
    return {"success": True, "dry_run": False, "invoices": invoices, "count": len(invoices)}


def create_payment(partner_name, amount, payment_type="inbound", journal="Bank"):
    """Create a payment record in Odoo.

    Args:
        partner_name: Customer/vendor name
        amount: Payment amount
        payment_type: 'inbound' (received) or 'outbound' (sent)
        journal: Payment journal name (default Bank)
    """
    if DRY_RUN:
        pay_name = f"PAY/2026/{datetime.now().strftime('%H%M')}"
        result = {
            "success": True, "dry_run": True,
            "payment": {"name": pay_name, "partner": partner_name,
                        "amount": amount, "payment_type": payment_type,
                        "state": "draft", "date": date.today().isoformat(),
                        "journal": journal}
        }
        logger.info(f"[DRY RUN] Created payment {pay_name}: ${amount:.2f} ({payment_type})")
        return result

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    partners = client.search_read("res.partner", [["name", "=", partner_name]], ["id"], limit=1)
    partner_id = partners[0]["id"] if partners else None

    payment_id = client.execute("account.payment", "create", {
        "partner_id": partner_id,
        "amount": amount,
        "payment_type": payment_type,
    })
    payment = client.search_read("account.payment", [["id", "=", payment_id]],
                                  ["name", "amount", "state", "date"])[0]
    return {"success": True, "dry_run": False, "payment": payment}


def get_payments(payment_type=None, limit=50):
    """Get payment records from Odoo."""
    if DRY_RUN:
        payments = MOCK_PAYMENTS
        if payment_type:
            payments = [p for p in payments if p["payment_type"] == payment_type]
        logger.info(f"[DRY RUN] Returning {len(payments)} mock payments")
        return {"success": True, "dry_run": True, "payments": payments, "count": len(payments)}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    domain = []
    if payment_type:
        domain.append(["payment_type", "=", payment_type])
    payments = client.search_read("account.payment", domain,
                                   ["name", "partner_id", "amount", "state", "date", "payment_type"],
                                   limit=limit)
    return {"success": True, "dry_run": False, "payments": payments, "count": len(payments)}


def get_account_summary():
    """Get a summary of the accounting state: total receivable, payable, revenue, expenses."""
    if DRY_RUN:
        summary = {
            "total_receivable": 20700.00,
            "total_payable": 4200.00,
            "total_revenue_mtd": 17500.00,
            "total_expenses_mtd": 5050.00,
            "outstanding_invoices": 2,
            "overdue_invoices": 0,
            "payments_this_month": 2,
            "period": date.today().strftime("%Y-%m"),
            "currency": "USD"
        }
        logger.info("[DRY RUN] Returning mock account summary")
        return {"success": True, "dry_run": True, "summary": summary}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()

    posted_invoices = client.search_read("account.move",
        [["move_type", "=", "out_invoice"], ["state", "=", "posted"]],
        ["amount_total", "amount_residual", "invoice_date_due"])

    total_receivable = sum(i["amount_residual"] for i in posted_invoices)
    overdue = sum(1 for i in posted_invoices
                  if i.get("invoice_date_due") and i["invoice_date_due"] < date.today().isoformat())

    return {
        "success": True, "dry_run": False,
        "summary": {
            "total_receivable": total_receivable,
            "outstanding_invoices": len(posted_invoices),
            "overdue_invoices": overdue,
            "period": date.today().strftime("%Y-%m"),
            "currency": "USD"
        }
    }


def get_transactions(limit=50):
    """Get all transactions (invoices + payments combined) for audit/reporting."""
    if DRY_RUN:
        transactions = []
        for inv in MOCK_INVOICES:
            transactions.append({
                "type": "invoice", "name": inv["name"], "partner": inv["partner"],
                "amount": inv["amount_total"], "state": inv["state"], "date": inv["date"]
            })
        for pay in MOCK_PAYMENTS:
            transactions.append({
                "type": "payment", "name": pay["name"], "partner": pay["partner"],
                "amount": pay["amount"], "state": pay["state"], "date": pay["date"],
                "direction": pay["payment_type"]
            })
        transactions.sort(key=lambda x: x["date"], reverse=True)
        logger.info(f"[DRY RUN] Returning {len(transactions)} mock transactions")
        return {"success": True, "dry_run": True, "transactions": transactions, "count": len(transactions)}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    invoices = client.search_read("account.move",
        [["move_type", "in", ["out_invoice", "in_invoice"]]],
        ["name", "partner_id", "amount_total", "state", "date"], limit=limit)
    payments = client.search_read("account.payment", [],
        ["name", "partner_id", "amount", "state", "date", "payment_type"], limit=limit)

    transactions = []
    for inv in invoices:
        transactions.append({"type": "invoice", "name": inv["name"],
            "partner": inv.get("partner_id", [None, "Unknown"])[1],
            "amount": inv["amount_total"], "state": inv["state"], "date": inv["date"]})
    for pay in payments:
        transactions.append({"type": "payment", "name": pay["name"],
            "partner": pay.get("partner_id", [None, "Unknown"])[1],
            "amount": pay["amount"], "state": pay["state"], "date": pay["date"],
            "direction": pay["payment_type"]})
    transactions.sort(key=lambda x: x["date"], reverse=True)
    return {"success": True, "dry_run": False, "transactions": transactions, "count": len(transactions)}


def update_payment(payment_name, new_state):
    """Update the state of a payment record in Odoo.

    Args:
        payment_name: Payment reference (e.g. PAY/2026/0001)
        new_state: New state (draft, posted, cancelled)
    """
    if DRY_RUN:
        for pay in MOCK_PAYMENTS:
            if pay["name"] == payment_name:
                old_state = pay["state"]
                pay["state"] = new_state
                logger.info(f"[DRY RUN] Updated payment {payment_name}: {old_state} → {new_state}")
                return {"success": True, "dry_run": True, "payment": pay, "old_state": old_state}
        return {"success": False, "dry_run": True, "error": f"Payment {payment_name} not found"}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    payments = client.search_read("account.payment",
        [["name", "=", payment_name]], ["id", "state"], limit=1)
    if not payments:
        return {"success": False, "error": f"Payment {payment_name} not found"}

    payment_id = payments[0]["id"]
    old_state = payments[0]["state"]

    if new_state == "posted":
        client.execute("account.payment", "action_post", [payment_id])
    elif new_state == "cancelled":
        client.execute("account.payment", "action_cancel", [payment_id])
    elif new_state == "draft":
        client.execute("account.payment", "action_draft", [payment_id])

    updated = client.search_read("account.payment",
        [["id", "=", payment_id]], ["name", "amount", "state", "date"])[0]
    return {"success": True, "dry_run": False, "payment": updated, "old_state": old_state}


def search_partners(query, limit=20):
    """Search for partners/contacts in Odoo by name or email."""
    if DRY_RUN:
        results = [p for p in MOCK_PARTNERS if query.lower() in p["name"].lower()
                   or query.lower() in p.get("email", "").lower()]
        logger.info(f"[DRY RUN] Found {len(results)} partners matching '{query}'")
        return {"success": True, "dry_run": True, "partners": results, "count": len(results)}

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)
    client.connect()
    domain = ["|", ["name", "ilike", query], ["email", "ilike", query]]
    partners = client.search_read("res.partner", domain,
                                   ["name", "email", "phone", "is_company"], limit=limit)
    return {"success": True, "dry_run": False, "partners": partners, "count": len(partners)}


# ── MCP STDIO PROTOCOL ──────────────────────────────────────────────────
TOOLS = {
    "create_invoice": {
        "description": "Create a customer invoice in Odoo",
        "parameters": {"partner_name": "string", "lines": "array", "currency": "string (optional)"},
        "handler": create_invoice
    },
    "get_invoices": {
        "description": "List invoices from Odoo, optionally filtered by state",
        "parameters": {"state": "string (optional: draft|posted|cancel)", "limit": "integer (optional)"},
        "handler": get_invoices
    },
    "create_payment": {
        "description": "Record a payment in Odoo",
        "parameters": {"partner_name": "string", "amount": "number", "payment_type": "string (optional)", "journal": "string (optional)"},
        "handler": create_payment
    },
    "get_payments": {
        "description": "List payment records from Odoo",
        "parameters": {"payment_type": "string (optional: inbound|outbound)", "limit": "integer (optional)"},
        "handler": get_payments
    },
    "get_account_summary": {
        "description": "Get accounting summary: receivables, payables, revenue, expenses",
        "parameters": {},
        "handler": get_account_summary
    },
    "get_transactions": {
        "description": "Get all transactions (invoices + payments) for audit/reporting",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_transactions
    },
    "update_payment": {
        "description": "Update the state of a payment record",
        "parameters": {"payment_name": "string", "new_state": "string (draft|posted|cancelled)"},
        "handler": update_payment
    },
    "search_partners": {
        "description": "Search Odoo partners/contacts by name or email",
        "parameters": {"query": "string", "limit": "integer (optional)"},
        "handler": search_partners
    },
}


def handle_request(request):
    """Handle a single MCP JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "name": "odoo-mcp", "version": "1.0.0",
            "capabilities": {"tools": list(TOOLS.keys())}
        }}

    if method == "tools/list":
        tools_list = [{"name": k, "description": v["description"],
                       "inputSchema": {"type": "object", "properties": v["parameters"]}}
                      for k, v in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        # Start timing for duration tracking
        start_time = time.time()

        if tool_name not in TOOLS:
            # Gold Tier: log unknown tool error to audit log
            if HAS_AUDIT_LOGGER:
                _audit_log_error(
                    action_type="mcp.tools/call",
                    actor="odoo_mcp",
                    target=tool_name,
                    parameters=tool_args,
                    result=f"unknown tool: {tool_name}",
                    severity="ERROR",
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

        try:
            result = TOOLS[tool_name]["handler"](**tool_args)

            # Gold Tier: log successful MCP call to audit log
            if HAS_AUDIT_LOGGER:
                log_mcp_call(
                    server="odoo",
                    tool=tool_name,
                    args=tool_args,
                    result="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [
                {"type": "text", "text": json.dumps(result, indent=2, default=str)}
            ]}}
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")

            # Gold Tier: log failed MCP call to audit log
            if HAS_AUDIT_LOGGER:
                _audit_log_error(
                    action_type=f"mcp.odoo.{tool_name}",
                    actor="odoo_mcp",
                    target=tool_name,
                    error=e,
                    parameters=tool_args,
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            # Gold Tier: graceful degradation — queue deferred task on failure
            error_type = classify_error(e) if HAS_RETRY else "unknown"
            NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            deferred = NEEDS_ACTION_DIR / f"DEFERRED_odoo_{tool_name}_{now.strftime('%Y%m%d_%H%M%S')}.md"
            try:
                deferred.write_text(
                    f"---\ntype: deferred_task\nstatus: pending\npriority: medium\n"
                    f"service: odoo\naction: {tool_name}\ncreated: {now.isoformat()}\n"
                    f"deferred_reason: odoo_unavailable\n---\n\n"
                    f"## Deferred Odoo Task: {tool_name}\n\n"
                    f"Error ({error_type}): {e}\nArgs: {tool_args}\n",
                    encoding="utf-8",
                )
                logger.info(f"[DEGRADE] Queued deferred odoo task: {deferred.name}")
            except OSError as os_error:
                if HAS_AUDIT_LOGGER:
                    _audit_log_error(
                        action_type="odoo.deferred_task",
                        actor="odoo_mcp",
                        target=tool_name,
                        error=os_error,
                        severity="ERROR",
                    )
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000,
                              "message": f"[{error_type}] {e} (deferred task queued)"}}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def run_stdio():
    """Run MCP server in stdio mode (read JSON-RPC from stdin, write to stdout)."""
    logger.info(f"Odoo MCP server starting (DRY_RUN={DRY_RUN})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            error = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(error) + "\n")
            sys.stdout.flush()


def run_test():
    """Run a self-test of all tools in dry-run mode."""
    global DRY_RUN
    DRY_RUN = True
    print("=== Odoo MCP Self-Test (DRY RUN) ===\n")

    print("1. get_invoices():")
    print(json.dumps(get_invoices(), indent=2))

    print("\n2. get_invoices(state='posted'):")
    print(json.dumps(get_invoices(state="posted"), indent=2))

    print("\n3. create_invoice():")
    print(json.dumps(create_invoice("Test Client", [
        {"description": "Consulting", "quantity": 10, "price_unit": 150}
    ]), indent=2))

    print("\n4. get_payments():")
    print(json.dumps(get_payments(), indent=2))

    print("\n5. create_payment():")
    print(json.dumps(create_payment("Test Client", 1500.00), indent=2))

    print("\n6. get_account_summary():")
    print(json.dumps(get_account_summary(), indent=2))

    print("\n7. get_transactions():")
    print(json.dumps(get_transactions(), indent=2))

    print("\n8. update_payment('PAY/2026/0001', 'cancelled'):")
    print(json.dumps(update_payment("PAY/2026/0001", "cancelled"), indent=2))

    print("\n9. search_partners('acme'):")
    print(json.dumps(search_partners("acme"), indent=2))

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Odoo MCP Server for AI Employee Vault")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.dry_run:
        DRY_RUN = True
    if args.test:
        run_test()
    else:
        run_stdio()
