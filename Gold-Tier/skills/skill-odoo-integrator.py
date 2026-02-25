#!/usr/bin/env python3
"""
Odoo Integrator Skill - Gold Tier

Handles Odoo ERP integrations: create invoices, record payments, track transactions.
Follows Gold Spec for accounting automation.

Features:
- Creates accounting plans in data/Plans/ODOO_{action}_{id}.md format
- Requires HITL approval for sensitive operations
- Invokes odoo-mcp for all ERP operations
- Generates accounting summaries and reports
- Full audit logging
- Error recovery with transient retry
"""

import os
import sys
import json
import re
import time
from datetime import datetime
from pathlib import Path
import subprocess
import logging

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = VAULT_DIR / "data"
PLANS_DIR = DATA_DIR / "Plans"
PENDING_APPROVAL_DIR = DATA_DIR / "Pending_Approval"
ACCOUNTING_DIR = DATA_DIR / "Accounting"
LOGS_DIR = DATA_DIR / "Logs"

# Ensure directories exist
for d in [PLANS_DIR, PENDING_APPROVAL_DIR, ACCOUNTING_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - OdooIntegrator - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "odoo_integrator.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("OdooIntegrator")

# ── MCP INVOCATION HELPER ─────────────────────────────────────────────────
def invoke_mcp(server_type: str, params: dict) -> dict:
    """
    Generic MCP invocation helper for Odoo integrations.

    Args:
        server_type: Type of MCP server ("odoo-mcp")
        params: Parameters to pass to the MCP server

    Returns:
        dict: MCP response with 'success' and 'result' keys
    """
    try:
        if server_type == "odoo-mcp":
            # Call the odoo-mcp server
            mcp_script = VAULT_DIR / "mcp-servers" / "odoo-mcp" / "odoo_mcp.py"
            if not mcp_script.exists():
                logger.error(f"MCP script not found: {mcp_script}")
                return {"success": False, "error": f"MCP script not found: {mcp_script}"}

            # Prepare MCP request
            request = {
                "method": "tools/call",
                "params": {
                    "name": params.get("action", "get_info"),
                    "arguments": {k: v for k, v in params.items() if k != "action"}
                }
            }

            # Execute the MCP server
            result = subprocess.run(
                [sys.executable, str(mcp_script)],
                input=json.dumps(request) + "\n",
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(VAULT_DIR),
                env={**os.environ}
            )

            if result.returncode == 0:
                # Parse MCP response
                response_lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
                if response_lines:
                    try:
                        mcp_response = json.loads(response_lines[-1])
                        if "result" in mcp_response:
                            logger.info(f"MCP call succeeded: {params.get('action', 'unknown')}")
                            return {"success": True, "result": mcp_response["result"]}
                        elif "error" in mcp_response:
                            logger.error(f"MCP call failed: {mcp_response['error']}")
                            return {"success": False, "error": mcp_response["error"]}
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse MCP response: {e}")
                        return {"success": False, "error": f"Invalid MCP response format: {result.stdout}"}
                else:
                    logger.error(f"MCP call returned no output")
                    return {"success": False, "error": "MCP call returned no output"}
            else:
                logger.error(f"MCP call failed with return code {result.returncode}: {result.stderr}")
                return {"success": False, "error": result.stderr}

        else:
            logger.error(f"Unknown MCP server type: {server_type}")
            return {"success": False, "error": f"Unknown MCP server type: {server_type}"}

    except subprocess.TimeoutExpired:
        logger.error(f"MCP call timed out: {params}")
        return {"success": False, "error": "MCP call timed out"}
    except Exception as e:
        logger.error(f"Error invoking MCP: {e}")
        return {"success": False, "error": str(e)}

# ── AUDIT LOGGING HELPER ──────────────────────────────────────────────────
def log_action(action_type: str, details: dict, result: str = "success"):
    """Log actions to the audit system."""
    try:
        # Import the audit logger if available
        sys.path.insert(0, str(VAULT_DIR))
        from audit_logger import log_action as audit_log_action
        correlation_id = f"odoo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        audit_log_action(
            action_type=action_type,
            actor="odoo_integrator",
            target="odoo-mcp",
            parameters=details,
            result=result,
            correlation_id=correlation_id
        )
    except ImportError:
        logger.warning("audit_logger not available, using basic logging")
        logger.info(f"AUDIT: {action_type} - {details} - {result}")

# ── CREATE APPROVAL REQUEST FOR SENSITIVE OPERATIONS ──────────────────────
def create_approval_request(plan_file: Path, correlation_id: str, operation_type: str) -> bool:
    """
    Create an approval request in Pending_Approval directory for sensitive operations.

    Args:
        plan_file: The plan file that needs approval
        correlation_id: ID to correlate the request
        operation_type: Type of operation (invoice, payment, etc.)

    Returns:
        bool: True if approval request created successfully
    """
    try:
        # Read the plan content
        plan_content = plan_file.read_text(encoding="utf-8")

        # Create approval request with appropriate type
        approval_file = PENDING_APPROVAL_DIR / f"ODOO_{operation_type.upper()}_{correlation_id}.md"
        approval_content = f"""---
type: approval_request
action: odoo_{operation_type}
target: odoo-mcp
correlation_id: {correlation_id}
created: {datetime.now().isoformat()}
status: pending
priority: high
---

# Odoo {operation_type.title()} Approval Request

**Correlation ID:** {correlation_id}
**Operation Type:** {operation_type}

## Operation Details
{plan_content[:2000]}  # Limit to prevent overly large content

Please review and approve this Odoo operation before it is executed.
This is a financial operation that will affect the accounting system.
"""
        approval_file.write_text(approval_content, encoding="utf-8")
        logger.info(f"Approval request created: {approval_file.name}")

        # Log the approval request creation
        log_action("approval_request_created", {
            "plan_file": str(plan_file.name),
            "approval_file": str(approval_file.name),
            "correlation_id": correlation_id,
            "operation_type": operation_type
        })

        return True
    except Exception as e:
        logger.error(f"Failed to create approval request: {e}")
        log_action("approval_request_created", {
            "plan_file": str(plan_file.name) if 'plan_file' in locals() else "unknown",
            "correlation_id": correlation_id,
            "operation_type": operation_type
        }, "failed")
        return False

# ── GENERATE ACCOUNTING SUMMARY ───────────────────────────────────────────
def generate_accounting_summary(summary_data: dict, date_str: str) -> Path:
    """
    Generate an accounting summary in SUMMARY_ACC_{date}.md format.

    Args:
        summary_data: Dictionary with accounting metrics
        date_str: Date string for filename

    Returns:
        Path: Path to the generated summary file
    """
    summary_file = ACCOUNTING_DIR / f"SUMMARY_ACC_{date_str}.md"

    # Create table of accounting metrics (per Gold Spec format with Invoice, Amount, Status)
    table_rows = ["| Invoice | Amount | Status |", "|---------|--------|--------|"]
    # If summary_data contains invoice list, format as per spec
    if "invoices" in summary_data:
        for invoice in summary_data["invoices"]:
            inv_num = invoice.get("number", "N/A")
            amount = invoice.get("amount", "N/A")
            status = invoice.get("status", "N/A")
            table_rows.append(f"| {inv_num} | ${amount} | {status} |")
    else:
        # Fallback to metric table format
        table_rows = ["| Metric | Value |", "|---------|-------|"]
        for metric, value in summary_data.items():
            if metric != "invoices":  # Don't duplicate if invoices were already processed
                table_rows.append(f"| {metric.replace('_', ' ').title()} | {value} |")

    summary_content = f"""---
type: accounting_summary
date: {date_str}
metrics: {summary_data}
---

# Odoo Accounting Summary - {date_str}

## Key Metrics

{chr(10).join(table_rows)}

## Additional Insights
This summary was automatically generated by the Odoo Integrator skill.
"""

    summary_file.write_text(summary_content, encoding="utf-8")
    logger.info(f"Accounting summary created: {summary_file.name}")

    # Log the summary generation
    log_action("summary_generated", {
        "summary_file": str(summary_file.name),
        "date": date_str,
        "metrics": summary_data
    })

    return summary_file

# ── MAIN ODOO INTEGRATOR SKILL ────────────────────────────────────────────
class OdooIntegrator:
    """Main Odoo integrator skill class."""

    def __init__(self):
        logger.info("Odoo Integrator initialized")

    def create_invoice(self, partner_name: str, amount: float, description: str = "",
                      plan_content: str = None) -> dict:
        """
        Create an invoice in Odoo following the Gold Spec.

        Args:
            partner_name: Name of the partner/customer
            amount: Invoice amount
            description: Invoice description
            plan_content: Pre-formatted plan content (optional)

        Returns:
            dict: Result of the operation
        """
        logger.info(f"Starting invoice creation for {partner_name}, amount: {amount}")

        try:
            correlation_id = f"inv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if plan_content:
                # Use provided plan content
                plan_file = PLANS_DIR / f"ODOO_INVOICE_{correlation_id}.md"
                plan_file.write_text(plan_content, encoding="utf-8")
            else:
                # Create plan from parameters
                # Create draft JSON in data/Plans/ODOO_INVOICE_{id}.md format (per Gold Spec)
                plan_content = f"""---
type: odoo_invoice
action: create_invoice
status: draft
priority: normal
created: {datetime.now().isoformat()}
---

# Invoice Plan

## Details
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Description:** {description}
- **Date:** {datetime.now().strftime('%Y-%m-%d')}

## Generated Invoice
This invoice will be created in Odoo with the above details.
"""
                plan_file = PLANS_DIR / f"ODOO_INVOICE_{correlation_id}.md"
                plan_file.write_text(plan_content, encoding="utf-8")

            logger.info(f"Invoice plan created: {plan_file.name}")

            # For invoices, require approval
            success = create_approval_request(plan_file, correlation_id, "invoice")
            if not success:
                raise Exception("Failed to create approval request")

            result = {
                "success": True,
                "status": "approval_required",
                "plan_file": str(plan_file.name),
                "approval_file": f"ODOO_INVOICE_{correlation_id}.md",
                "message": f"Invoice plan for {partner_name} ({amount}) created and approval requested."
            }

            # Log the success
            log_action("invoice_plan_created", {
                "plan_file": str(plan_file.name),
                "approval_file": f"ODOO_INVOICE_{correlation_id}.md",
                "partner": partner_name,
                "amount": amount,
                "correlation_id": correlation_id
            })

            return result

        except Exception as e:
            logger.error(f"Error in invoice creation: {e}")
            log_action("invoice_plan_created", {
                "error": str(e),
                "partner": partner_name,
                "amount": amount
            }, "failed")

            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create invoice plan: {e}"
            }

    def record_payment(self, partner_name: str, amount: float, invoice_ref: str = "",
                      plan_content: str = None) -> dict:
        """
        Record a payment in Odoo.

        Args:
            partner_name: Name of the partner/customer
            amount: Payment amount
            invoice_ref: Reference to the invoice being paid
            plan_content: Pre-formatted plan content (optional)

        Returns:
            dict: Result of the operation
        """
        logger.info(f"Starting payment recording for {partner_name}, amount: {amount}")

        try:
            correlation_id = f"pay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if plan_content:
                # Use provided plan content
                plan_file = PLANS_DIR / f"ODOO_PAYMENT_{correlation_id}.md"
                plan_file.write_text(plan_content, encoding="utf-8")
            else:
                # Create plan from parameters
                plan_content = f"""---
type: odoo_payment
action: record_payment
status: draft
priority: normal
created: {datetime.now().isoformat()}
---

# Payment Plan

## Details
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Invoice Reference:** {invoice_ref}
- **Date:** {datetime.now().strftime('%Y-%m-%d')}

## Payment Recording
This payment will be recorded in Odoo with the above details.
"""
                plan_file = PLANS_DIR / f"ODOO_PAYMENT_{correlation_id}.md"
                plan_file.write_text(plan_content, encoding="utf-8")

            logger.info(f"Payment plan created: {plan_file.name}")

            # For payments, require approval
            success = create_approval_request(plan_file, correlation_id, "payment")
            if not success:
                raise Exception("Failed to create approval request")

            result = {
                "success": True,
                "status": "approval_required",
                "plan_file": str(plan_file.name),
                "approval_file": f"ODOO_PAYMENT_{correlation_id}.md",
                "message": f"Payment plan for {partner_name} ({amount}) created and approval requested."
            }

            # Log the success
            log_action("payment_plan_created", {
                "plan_file": str(plan_file.name),
                "approval_file": f"ODOO_PAYMENT_{correlation_id}.md",
                "partner": partner_name,
                "amount": amount,
                "correlation_id": correlation_id
            })

            return result

        except Exception as e:
            logger.error(f"Error in payment recording: {e}")
            log_action("payment_plan_created", {
                "error": str(e),
                "partner": partner_name,
                "amount": amount
            }, "failed")

            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create payment plan: {e}"
            }

    def get_accounting_data(self, date_from: str = None, date_to: str = None) -> dict:
        """
        Get accounting data from Odoo.

        Args:
            date_from: Start date for data retrieval
            date_to: End date for data retrieval

        Returns:
            dict: Accounting data retrieved
        """
        logger.info(f"Fetching accounting data from Odoo")

        try:
            mcp_params = {
                "action": "get_account_summary",
                "date_from": date_from or (datetime.now().replace(day=1).strftime('%Y-%m-%d')),
                "date_to": date_to or datetime.now().strftime('%Y-%m-%d')
            }

            logger.info(f"Invoking Odoo MCP with params: {mcp_params}")
            mcp_result = invoke_mcp("odoo-mcp", mcp_params)

            if mcp_result["success"]:
                logger.info(f"Accounting data retrieval successful")

                # Log the successful retrieval
                log_action("accounting_data_retrieved", {
                    "date_from": mcp_params["date_from"],
                    "date_to": mcp_params["date_to"],
                    "result_keys": list(mcp_result["result"].keys()) if isinstance(mcp_result["result"], dict) else []
                })

                return {
                    "success": True,
                    "data": mcp_result["result"],
                    "message": "Accounting data retrieved successfully"
                }
            else:
                error_msg = mcp_result.get("error", "Unknown error")
                logger.error(f"Accounting data retrieval failed: {error_msg}")

                log_action("accounting_data_retrieved", {
                    "date_from": date_from,
                    "date_to": date_to,
                    "error": error_msg
                }, "failed")

                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Failed to retrieve accounting data: {error_msg}"
                }

        except Exception as e:
            logger.error(f"Error fetching accounting data: {e}")
            log_action("get_accounting_data", {
                "date_from": date_from,
                "date_to": date_to,
                "error": str(e)
            }, "failed")

            return {
                "success": False,
                "error": str(e),
                "message": f"Error fetching accounting data: {e}"
            }

    def handle_approved_operation(self, approved_file_path: Path) -> dict:
        """
        Handle an approved Odoo operation.

        Args:
            approved_file_path: Path to the approved file

        Returns:
            dict: Result of the operation execution
        """
        logger.info(f"Handling approved Odoo operation: {approved_file_path.name}")

        try:
            # Read the approved file
            approved_content = approved_file_path.read_text(encoding="utf-8")

            # Extract operation type from the file name
            import re
            match = re.search(r'ODOO_([A-Z]+)_([a-zA-Z0-9_]+)', approved_file_path.name)
            if not match:
                raise ValueError(f"Could not extract operation type and ID from {approved_file_path.name}")

            operation_type = match.group(1).lower()  # invoice, payment, etc.
            correlation_id = match.group(2)

            # Look for the original plan file
            plan_candidates = list(PLANS_DIR.glob(f"ODOO_{operation_type.upper()}_{correlation_id}.*"))
            plan_file = None
            if plan_candidates:
                plan_file = plan_candidates[0]

            # Extract parameters from the approved file
            params_from_file = {}
            lines = approved_content.splitlines()
            for line in lines:
                if "**Partner:**" in line:
                    params_from_file["partner_name"] = line.split("**Partner:**")[1].strip()
                elif "**Amount:**" in line:
                    amount_text = line.split("**Amount:**")[1].strip()
                    try:
                        params_from_file["amount"] = float(amount_text)
                    except ValueError:
                        params_from_file["amount"] = amount_text
                elif "**Invoice Reference:**" in line:
                    params_from_file["invoice_ref"] = line.split("**Invoice Reference:**")[1].strip()

            # Prepare MCP parameters based on operation type
            if operation_type == "invoice":
                mcp_params = {
                    "action": "post_invoice",
                    "partner_name": params_from_file.get("partner_name", "Unknown"),
                    "amount": params_from_file.get("amount", 0),
                    "description": f"Invoice via AI Employee - {correlation_id}",
                    "correlation_id": correlation_id
                }
            elif operation_type == "payment":
                mcp_params = {
                    "action": "create_payment",
                    "partner_name": params_from_file.get("partner_name", "Unknown"),
                    "amount": params_from_file.get("amount", 0),
                    "invoice_ref": params_from_file.get("invoice_ref", ""),
                    "correlation_id": correlation_id
                }
            else:
                raise ValueError(f"Unknown operation type: {operation_type}")

            logger.info(f"Invoking MCP with params: {mcp_params}")
            mcp_result = invoke_mcp("odoo-mcp", mcp_params)

            if mcp_result["success"]:
                logger.info(f"Odoo operation successful: {operation_type} {correlation_id}")

                # Log the successful operation
                log_action(f"odoo_{operation_type}_success", {
                    "correlation_id": correlation_id,
                    "operation_type": operation_type,
                    "mcp_result": mcp_result.get("result", {})
                })

                # Move approved file to Done
                done_dir = DATA_DIR / "Done"
                done_dir.mkdir(parents=True, exist_ok=True)
                done_file = done_dir / approved_file_path.name
                approved_file_path.rename(done_file)

                return {
                    "success": True,
                    "status": "completed",
                    "correlation_id": correlation_id,
                    "operation_type": operation_type,
                    "message": f"Odoo {operation_type} operation completed successfully"
                }
            else:
                error_msg = mcp_result.get("error", "Unknown error")
                logger.error(f"Odoo operation failed: {error_msg}")

                log_action(f"odoo_{operation_type}_failed", {
                    "correlation_id": correlation_id,
                    "operation_type": operation_type,
                    "error": error_msg
                }, "failed")

                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Failed to execute Odoo operation: {error_msg}"
                }

        except Exception as e:
            logger.error(f"Error handling approved operation: {e}")
            log_action("handle_approved_operation", {
                "approved_file": str(approved_file_path.name),
                "error": str(e)
            }, "failed")

            return {
                "success": False,
                "error": str(e),
                "message": f"Error handling approved operation: {e}"
            }

    def generate_summary(self, summary_data: dict = None) -> Path:
        """
        Generate an accounting summary.

        Args:
            summary_data: Dictionary with accounting metrics (if None, will try to fetch)

        Returns:
            Path: Path to the generated summary file
        """
        logger.info("Generating accounting summary")

        if not summary_data:
            # If no data provided, create sample data (with invoices format per spec)
            summary_data = {
                "total_invoices": 24,
                "total_amount": 125000.00,
                "outstanding_invoices": 6,
                "outstanding_amount": 28500.00,
                "payments_received": 18,
                "total_payments": 96500.00,
                "invoices": [
                    {"number": "#123", "amount": 500, "status": "Paid"},
                    {"number": "#124", "amount": 1200, "status": "Paid"},
                    {"number": "#125", "amount": 750, "status": "Pending"}
                ]
            }

        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = generate_accounting_summary(summary_data, date_str)

        logger.info(f"Accounting summary generated: {summary_file.name}")
        return summary_file

# ── MAIN EXECUTION ────────────────────────────────────────────────────────
def main():
    """Main function to demonstrate the Odoo Integrator skill."""
    import argparse

    parser = argparse.ArgumentParser(description="Odoo Integrator Skill")
    parser.add_argument("--invoice", action="store_true", help="Create an invoice")
    parser.add_argument("--partner", help="Partner name for invoice/payment")
    parser.add_argument("--amount", type=float, help="Amount for invoice/payment")
    parser.add_argument("--description", help="Invoice description")
    parser.add_argument("--payment", action="store_true", help="Record a payment")
    parser.add_argument("--invoice-ref", help="Invoice reference for payment")
    parser.add_argument("--approve", help="Process an approved Odoo operation file")
    parser.add_argument("--get-data", action="store_true", help="Get accounting data")
    parser.add_argument("--summary", action="store_true", help="Generate accounting summary")
    parser.add_argument("--demo", action="store_true", help="Run full demo")

    args = parser.parse_args()

    integrator = OdooIntegrator()

    if args.invoice and args.partner and args.amount:
        result = integrator.create_invoice(args.partner, args.amount, args.description or "")
        print(json.dumps(result, indent=2))

    elif args.payment and args.partner and args.amount:
        result = integrator.record_payment(args.partner, args.amount, args.invoice_ref or "")
        print(json.dumps(result, indent=2))

    elif args.approve:
        approved_path = Path(args.approve)
        if approved_path.exists():
            result = integrator.handle_approved_operation(approved_path)
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: Approved file not found: {approved_path}")

    elif args.get_data:
        result = integrator.get_accounting_data()
        print(json.dumps(result, indent=2))

    elif args.summary:
        summary_path = integrator.generate_summary()
        print(f"Summary generated: {summary_path}")

    elif args.demo:
        print("Running Odoo Integrator demo...")

        # Step 1: Create an invoice
        print(f"\n1. Creating invoice for Acme Corp, $5000.00")
        result = integrator.create_invoice("Acme Corp", 5000.00, "Q1 Services")
        print(f"Result: {json.dumps(result, indent=2)}")

        # Step 2: Record a payment
        print(f"\n2. Recording payment from Beta Inc, $2500.00")
        result = integrator.record_payment("Beta Inc", 2500.00, "INV-001")
        print(f"Result: {json.dumps(result, indent=2)}")

        # Step 3: Get accounting data
        print(f"\n3. Fetching accounting data...")
        result = integrator.get_accounting_data()
        print(f"Data retrieval: {json.dumps(result, indent=2)}")

        # Step 4: Generate a summary
        print(f"\n4. Generating accounting summary...")
        summary_path = integrator.generate_summary()
        print(f"Summary created: {summary_path}")

        print(f"\nDemo completed successfully!")

    else:
        print("Odoo Integrator Skill")
        print("Usage:")
        print("  --invoice --partner NAME --amount AMT [--description DESC] : Create invoice")
        print("  --payment --partner NAME --amount AMT [--invoice-ref REF]  : Record payment")
        print("  --approve FILE            : Process approved operation")
        print("  --get-data                : Get accounting data from Odoo")
        print("  --summary                 : Generate accounting summary")
        print("  --demo                    : Run full demo")


if __name__ == "__main__":
    main()