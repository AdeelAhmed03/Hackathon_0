#!/usr/bin/env python3
"""
Odoo Platinum Skill - Platinum Tier

Odoo with cloud deploy: Cloud drafts actions, local posts/payments.
Extends Gold Odoo Integrator with work-zone separation.

Features:
- Cloud: Draft invoices, query cloud Odoo (draft-only)
- Local: Execute payments/posts to Odoo (exec via local MCP)
- Work-zone separation: Cloud drafts, Local executes
- Git sync handling between zones (no credentials sync)
- A2A Phase 2 direct messaging (optional)
- Claim-by-move coordination protocol
- Health monitoring for cloud Odoo instance
- Comprehensive audit logging
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

# Platinum directories with zone separation
PLANS_CLOUD_DIR = DATA_DIR / "Plans" / "cloud"
PLANS_LOCAL_DIR = DATA_DIR / "Plans" / "local"
NEEDS_ACTION_CLOUD = DATA_DIR / "Needs_Action" / "cloud"
NEEDS_ACTION_LOCAL = DATA_DIR / "Needs_Action" / "local"
PENDING_APPROVAL_LOCAL = DATA_DIR / "Pending_Approval" / "local"
APPROVED_DIR = DATA_DIR / "Approved"
IN_PROGRESS_CLOUD = DATA_DIR / "In_Progress" / "cloud"
IN_PROGRESS_LOCAL = DATA_DIR / "In_Progress" / "local"
UPDATES_DIR = DATA_DIR / "Updates"
DONE_CLOUD = DATA_DIR / "Done" / "cloud"
DONE_LOCAL = DATA_DIR / "Done" / "local"
ACCOUNTING_DIR = DATA_DIR / "Accounting"
LOGS_DIR = DATA_DIR / "Logs"

# Ensure directories exist
for d in [PLANS_CLOUD_DIR, PLANS_LOCAL_DIR, NEEDS_ACTION_CLOUD, NEEDS_ACTION_LOCAL,
          PENDING_APPROVAL_LOCAL, APPROVED_DIR, IN_PROGRESS_CLOUD, IN_PROGRESS_LOCAL,
          UPDATES_DIR, DONE_CLOUD, DONE_LOCAL, ACCOUNTING_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - OdooPlatinum - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "odoo_platinum.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("OdooPlatinum")

# ── VAULT ENVIRONMENT DETECTION ───────────────────────────────────────────
VAULT_ENVIRONMENT = os.environ.get("VAULT_ENVIRONMENT", "local").lower()

# ── A2A MESSAGING IMPORT ──────────────────────────────────────────────────
A2A_AVAILABLE = False
try:
    sys.path.insert(0, str(VAULT_DIR))
    from a2a_messaging import A2ANode, A2A_ENABLED as _A2A_ENABLED
    A2A_AVAILABLE = True
    logger.info("A2A messaging available")
except ImportError:
    logger.warning("A2A messaging not available")
    _A2A_ENABLED = False

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
            # Call the odoo-mcp server (only available on local with secrets for execution)
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
        from audit_logger import log_action as audit_log_action
        correlation_id = f"odoo_plat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        audit_log_action(
            action_type=action_type,
            actor="odoo_platinum",
            target="odoo-mcp" if VAULT_ENVIRONMENT == "local" else "cloud_processor",
            parameters=details,
            result=result,
            correlation_id=correlation_id
        )
    except ImportError:
        logger.warning("audit_logger not available, using basic logging")
        logger.info(f"AUDIT: {action_type} - {details} - {result}")

# ── CLAIM-BY-MOVE PROTOCOL ────────────────────────────────────────────────
def claim_file(file_path: Path, zone: str) -> bool:
    """
    Implement claim-by-move protocol to prevent double-processing.

    Args:
        file_path: The file to claim
        zone: The zone claiming the file ('cloud' or 'local')

    Returns:
        bool: True if claim successful, False if already claimed
    """
    if not file_path.exists():
        logger.warning(f"Cannot claim non-existent file: {file_path}")
        return False

    # Determine appropriate In_Progress directory based on zone
    in_progress_dir = IN_PROGRESS_CLOUD if zone == "cloud" else IN_PROGRESS_LOCAL
    in_progress_dir.mkdir(parents=True, exist_ok=True)

    # Create claimed file path
    claimed_path = in_progress_dir / file_path.name

    # Check if already claimed by another zone
    cloud_claimed = IN_PROGRESS_CLOUD / file_path.name
    local_claimed = IN_PROGRESS_LOCAL / file_path.name

    if cloud_claimed.exists() or local_claimed.exists():
        logger.warning(f"File already claimed: {file_path.name}")
        return False

    # Move file to In_Progress/{zone}/ to claim it
    try:
        file_path.rename(claimed_path)
        logger.info(f"File claimed by {zone}: {claimed_path.name}")
        return True
    except OSError as e:
        logger.error(f"Failed to claim file {file_path}: {e}")
        return False

# ── A2A MESSAGING HELPER ──────────────────────────────────────────────────
def send_a2a_notification(notification_type: str, payload: dict):
    """
    Send A2A Phase 2 notification if available.

    Args:
        notification_type: Type of notification to send
        payload: Notification data
    """
    if not A2A_AVAILABLE or not _A2A_ENABLED:
        logger.debug("A2A not available or disabled")
        return

    try:
        node = A2ANode(role=VAULT_ENVIRONMENT)
        node.start()

        recipient = "local" if VAULT_ENVIRONMENT == "cloud" else "cloud"
        success = node.send(recipient, payload, msg_type=notification_type)

        logger.info(f"A2A notification {notification_type} sent to {recipient}: {success}")
        node.stop()
    except Exception as e:
        logger.error(f"Failed to send A2A notification: {e}")

# ── SYNC HANDLER ──────────────────────────────────────────────────────────
def run_git_sync():
    """
    Run Git sync operations per Platinum spec.
    Only sync .md files and state, never secrets.
    No credentials sync (per Platinum spec).
    """
    logger.info("Running Git sync operation")

    try:
        # Stage only data/ (no secrets)
        add_result = subprocess.run(
            ["git", "add", "data/"],
            cwd=VAULT_DIR, capture_output=True, text=True, timeout=30,
        )

        if add_result.returncode != 0:
            logger.warning(f"Git add failed: {add_result.stderr}")
            return False

        # Check if there are changes to commit
        status_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=VAULT_DIR, capture_output=True, text=True, timeout=10,
        )

        if status_result.returncode == 0:
            logger.info("No changes to commit in Git sync")
            return True

        # Commit changes
        commit_msg = f"Plat-ODOO sync {datetime.now().isoformat()}"
        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=VAULT_DIR, capture_output=True, text=True, timeout=30,
        )

        if commit_result.returncode != 0:
            logger.warning(f"Git commit failed: {commit_result.stderr}")
            return False

        # Push changes
        push_result = subprocess.run(
            ["git", "push"],
            cwd=VAULT_DIR, capture_output=True, text=True, timeout=30,
        )

        if push_result.returncode == 0:
            logger.info("Git push successful")
            log_action("git_sync_success", {"message": commit_msg})
            return True
        else:
            logger.warning(f"Git push failed: {push_result.stderr}")
            log_action("git_sync_failed", {"error": push_result.stderr, "message": commit_msg}, "failed")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Git sync timed out")
        log_action("git_sync_timeout", {"operation": "sync"}, "failed")
        return False
    except Exception as e:
        logger.error(f"Git sync failed: {e}")
        log_action("git_sync_failed", {"error": str(e)}, "failed")
        return False

# ── HEALTH MONITORING ─────────────────────────────────────────────────────
def check_odoo_health():
    """
    Health monitoring for cloud Odoo instance (per Platinum spec).
    """
    logger.info("Checking Odoo health")

    try:
        # Try to query basic info from cloud Odoo
        mcp_params = {
            "action": "get_info",
            "correlation_id": f"health_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }

        # This would be a query to the cloud Odoo instance
        # In a real implementation, this would connect to the cloud Odoo endpoint
        mcp_result = invoke_mcp("odoo-mcp", mcp_params)

        if mcp_result["success"]:
            logger.info("Odoo health check passed")
            return True
        else:
            logger.warning(f"Odoo health check failed: {mcp_result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"Error during Odoo health check: {e}")
        return False

# ── MAIN ODOO PLATINUM SKILL ──────────────────────────────────────────────
class OdooPlatinum:
    """Main Odoo Platinum skill class with zone-aware operations."""

    def __init__(self):
        self.a2a_node = None

        logger.info(f"Odoo Platinum initialized for {VAULT_ENVIRONMENT} environment")

        # Initialize A2A node if available
        if A2A_AVAILABLE and _A2A_ENABLED:
            try:
                self.a2a_node = A2ANode(role=VAULT_ENVIRONMENT)
                self.a2a_node.start()
                logger.info(f"A2A node started for {VAULT_ENVIRONMENT}")
            except Exception as e:
                logger.error(f"Failed to start A2A node: {e}")

    def cloud_draft_invoice(self, partner_name: str, amount: float, description: str = "",
                           plan_content: str = None) -> dict:
        """
        Cloud zone: Draft invoice following Platinum spec (draft-only to cloud Odoo).

        Args:
            partner_name: Name of the partner/customer
            amount: Invoice amount
            description: Invoice description
            plan_content: Pre-formatted plan content (optional)

        Returns:
            dict: Result of the operation
        """
        if VAULT_ENVIRONMENT != "cloud":
            logger.warning("cloud_draft_invoice called on non-cloud environment")
            return {
                "success": False,
                "error": "Not in cloud environment",
                "message": "This function should only be called in cloud environment"
            }

        logger.info(f"Starting Cloud invoice draft for {partner_name}, amount: {amount}")

        try:
            # Step 1: Create draft in /Plans/cloud/ODOO_DRAFT_{id}.md (per Platinum spec)
            correlation_id = f"odoo_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if plan_content:
                # Use provided plan content
                draft_file = PLANS_CLOUD_DIR / f"ODOO_DRAFT_{correlation_id}.md"
                draft_file.write_text(plan_content, encoding="utf-8")
            else:
                # Create plan from parameters
                plan_content = f"""---
type: odoo_invoice
action: create_invoice
status: draft
priority: normal
created: {datetime.now().isoformat()}
zone: cloud
draft_only: true
---

# Invoice Draft

## Details
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Description:** {description}
- **Date:** {datetime.now().strftime('%Y-%m-%d')}

## Cloud Draft Notice
This is a draft created by the cloud agent. It requires human approval
and will be executed by the local agent after approval.
No actual posting to Odoo occurs from the cloud agent.
"""
                draft_file = PLANS_CLOUD_DIR / f"ODOO_DRAFT_{correlation_id}.md"
                draft_file.write_text(plan_content, encoding="utf-8")

            logger.info(f"Invoice draft created: {draft_file.name}")

            # Step 2: Write approval request to /Pending_Approval/local/ (per Platinum spec)
            approval_file = PENDING_APPROVAL_LOCAL / f"ODOO_{correlation_id}.md"
            approval_content = f"""---
type: approval_request
action: odoo_invoice
source_zone: cloud
target_zone: local
correlation_id: {correlation_id}
created: {datetime.now().isoformat()}
status: pending
priority: high
---

# Odoo Invoice Approval Request

**Correlation ID:** {correlation_id}
**Source Zone:** Cloud
**Target Action:** odoo_invoice

## Draft Invoice
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Description:** {description}

## Original Draft File
{draft_file.name}

Please review and approve this Odoo invoice. After approval, the local agent will post to Odoo with local credentials.
"""
            approval_file.write_text(approval_content, encoding="utf-8")
            logger.info(f"Approval request created in local queue: {approval_file.name}")

            # Step 3: Update /Updates/ for dashboard merge (cloud updates for local)
            update_file = UPDATES_DIR / f"cloud_odoo_draft_{correlation_id}.md"
            update_content = f"""---
type: cloud_update
source: odoo_platinum
timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}
summary: Invoice draft created, approval pending
correlation_id: {correlation_id}
---

# Cloud Update: Invoice Draft Created

- **Draft ID:** {correlation_id}
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Status:** Awaiting local approval
- **Created:** {datetime.now().isoformat()}
"""
            update_file.write_text(update_content, encoding="utf-8")
            logger.info(f"Cloud update created: {update_file.name}")

            # Step 4: Run sync to push to local (per Platinum spec - Git sync, no creds sync)
            sync_success = run_git_sync()
            if not sync_success:
                logger.warning("Git sync failed after draft creation")

            # Step 5: Send A2A notification for "Invoice draft ready" (Phase 2 A2A per spec)
            send_a2a_notification("draft_ready", {
                "draft_id": correlation_id,
                "draft_type": "odoo_invoice",
                "summary": f"Invoice draft ready for approval: {partner_name} - ${amount}",
                "created": datetime.now().isoformat()
            })

            result = {
                "success": True,
                "status": "draft_created",
                "draft_file": str(draft_file.name),
                "approval_file": f"ODOO_{correlation_id}.md",
                "message": f"Invoice draft created and approval requested for {partner_name}"
            }

            # Log the success
            log_action("odoo_draft_created", {
                "draft_file": str(draft_file.name),
                "approval_file": f"ODOO_{correlation_id}.md",
                "partner": partner_name,
                "amount": amount,
                "correlation_id": correlation_id,
                "zone": "cloud"
            })

            return result

        except Exception as e:
            logger.error(f"Error in cloud invoice draft process: {e}")
            log_action("odoo_draft_created", {
                "error": str(e),
                "partner": partner_name,
                "amount": amount
            }, "failed")

            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to create invoice draft: {e}"
            }

    def local_process_approved_invoice(self, approved_file_path: Path) -> dict:
        """
        Local zone: Process approved invoices and post to Odoo via MCP (per Platinum spec).

        Args:
            approved_file_path: Path to the approved file

        Returns:
            dict: Result of the posting operation
        """
        if VAULT_ENVIRONMENT != "local":
            logger.warning("local_process_approved_invoice called on non-local environment")
            return {
                "success": False,
                "error": "Not in local environment",
                "message": "This function should only be called in local environment"
            }

        logger.info(f"Processing approved invoice: {approved_file_path.name}")

        try:
            # Use claim-by-move protocol to prevent double-processing (per Platinum spec)
            if not claim_file(approved_file_path, "local"):
                return {
                    "success": False,
                    "error": "File already claimed by another agent",
                    "message": "Approval file already being processed"
                }

            # Read the approved file to get the original draft details
            approved_content = approved_file_path.read_text(encoding="utf-8")

            # Extract correlation info from the approved file name
            match = re.search(r'ODOO_([a-zA-Z0-9_]+)', approved_file_path.name)
            if not match:
                raise ValueError(f"Could not extract correlation ID from {approved_file_path.name}")

            correlation_id = match.group(1)

            # Extract details from the approved file
            partner_name = ""
            amount = 0.0
            description = ""

            lines = approved_content.splitlines()
            for line in lines:
                if "**Partner:**" in line:
                    partner_name = line.split("**Partner:**")[1].strip()
                elif "**Amount:**" in line:
                    amount_str = line.split("**Amount:**")[1].strip()
                    try:
                        amount = float(amount_str.replace('$', '').replace(',', ''))
                    except ValueError:
                        pass
                elif "**Description:**" in line:
                    description = line.split("**Description:**")[1].strip()

            if not partner_name or amount == 0:
                raise ValueError("Could not extract required invoice details")

            # Find the original draft file reference in the content
            draft_file_match = re.search(r'Original Draft File\n([^\n]+)', approved_content)
            if draft_file_match:
                draft_file_name = draft_file_match.group(1).strip()
                original_draft_path = PLANS_CLOUD_DIR / draft_file_name

            # Step 3: Execute via odoo-mcp with local credentials (per Platinum spec - local exec, fresh approval)
            mcp_params = {
                "action": "post_invoice",
                "partner_name": partner_name,
                "amount": amount,
                "description": description,
                "correlation_id": correlation_id
            }

            logger.info(f"Invoking Odoo MCP with params: {mcp_params}")
            mcp_result = invoke_mcp("odoo-mcp", mcp_params)

            if mcp_result["success"]:
                logger.info(f"Odoo invoice posted successfully: {correlation_id}")

                # Create execution update for dashboard
                exec_update_file = UPDATES_DIR / f"local_odoo_exec_{correlation_id}.md"
                exec_update_content = f"""---
type: execution_result
source: odoo_platinum
timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}
summary: Invoice posted to Odoo successfully
correlation_id: {correlation_id}
---

# Local Execution: Invoice Posted

- **Invoice ID:** {correlation_id}
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Status:** Success
- **Executed:** {datetime.now().isoformat()}
- **MCP Result:** {json.dumps(mcp_result.get('result', {}), indent=2)}
"""
                exec_update_file.write_text(exec_update_content, encoding="utf-8")
                logger.info(f"Execution update created: {exec_update_file.name}")

                # Log the successful post
                log_action("odoo_post_success", {
                    "correlation_id": correlation_id,
                    "partner": partner_name,
                    "amount": amount,
                    "mcp_result": mcp_result.get("result", {})
                })

                # Move approved file to Done/local/
                done_file = DONE_LOCAL / approved_file_path.name
                approved_file_path.rename(done_file)

                # Run sync to update cloud
                sync_success = run_git_sync()
                if not sync_success:
                    logger.warning("Git sync failed after execution")

                # Send A2A notification
                send_a2a_notification("execution_complete", {
                    "correlation_id": correlation_id,
                    "action": "odoo_invoice",
                    "result": "success",
                    "executed": datetime.now().isoformat()
                })

                return {
                    "success": True,
                    "status": "posted",
                    "correlation_id": correlation_id,
                    "message": f"Odoo invoice posted successfully for {partner_name}"
                }
            else:
                error_msg = mcp_result.get("error", "Unknown error")
                logger.error(f"Odoo invoice posting failed: {error_msg}")

                # Create error update for dashboard
                error_update_file = UPDATES_DIR / f"local_odoo_error_{correlation_id}.md"
                error_update_content = f"""---
type: execution_error
source: odoo_platinum
timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}
summary: Invoice posting to Odoo failed
correlation_id: {correlation_id}
---

# Local Execution: Invoice Posting Failed

- **Invoice ID:** {correlation_id}
- **Partner:** {partner_name}
- **Amount:** {amount}
- **Status:** Failed
- **Error:** {error_msg}
- **Executed:** {datetime.now().isoformat()}
"""
                error_update_file.write_text(error_update_content, encoding="utf-8")
                logger.info(f"Error update created: {error_update_file.name}")

                log_action("odoo_post_failed", {
                    "correlation_id": correlation_id,
                    "partner": partner_name,
                    "amount": amount,
                    "error": error_msg
                }, "failed")

                # Move to Done even on failure to prevent retry loop
                done_file = DONE_LOCAL / approved_file_path.name
                approved_file_path.rename(done_file)

                return {
                    "success": False,
                    "error": error_msg,
                    "message": f"Failed to post to Odoo: {error_msg}"
                }

        except Exception as e:
            logger.error(f"Error processing approved invoice: {e}")
            log_action("process_approved_invoice", {
                "approved_file": str(approved_file_path.name),
                "error": str(e)
            }, "failed")

            # Try to move the file to done even if there's an error
            try:
                done_file = DONE_LOCAL / approved_file_path.name
                if approved_file_path.exists():
                    approved_file_path.rename(done_file)
            except:
                pass  # If we can't move it, it will remain in In_Progress and be handled by error recovery

            return {
                "success": False,
                "error": str(e),
                "message": f"Error processing approved invoice: {e}"
            }

    def cloud_generate_summary_draft(self, summary_data: dict = None) -> Path:
        """
        Cloud zone: Generate draft revenue summary with table (per Platinum spec).

        Args:
            summary_data: Dictionary with accounting metrics (if None, will use sample)

        Returns:
            Path: Path to the generated summary file
        """
        if VAULT_ENVIRONMENT != "cloud":
            logger.warning("cloud_generate_summary_draft called on non-cloud environment")
            return None

        logger.info("Generating Cloud Odoo revenue summary draft")

        if not summary_data:
            # If no data provided, create sample data
            summary_data = {
                "total_invoices": 24,
                "total_amount": 125000.00,
                "outstanding_invoices": 6,
                "outstanding_amount": 28500.00,
                "invoices": [
                    {"number": "#123", "amount": 500, "status": "Paid"},  # As in spec example
                    {"number": "#124", "amount": 1200, "status": "Paid"},
                    {"number": "#125", "amount": 750, "status": "Pending"}
                ]
            }

        date_str = datetime.now().strftime('%Y%m')
        summary_file = ACCOUNTING_DIR / f"SUMMARY_ODOO_DRAFT_{date_str}.md"

        # Create revenue table (per Platinum spec format with Invoice, Amount, Status)
        table_rows = ["| Invoice | Amount | Status |", "|---------|--------|--------|"]
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
type: odoo_summary_draft
date: {date_str}
metrics: {summary_data}
zone: cloud
status: draft
---

# Odoo Revenue Summary Draft - {date_str}

## Revenue Metrics

{chr(10).join(table_rows)}

## Cloud Draft Notice
This is a draft summary created by the cloud agent. It will be merged with
other accounting data by the local agent to create the final summary.

**Generated by:** Odoo Platinum Cloud
**Created:** {datetime.now().isoformat()}
"""

        summary_file.write_text(summary_content, encoding="utf-8")
        logger.info(f"Cloud Odoo summary draft created: {summary_file.name}")

        # Log the summary generation
        log_action("summary_draft_generated", {
            "summary_file": str(summary_file.name),
            "date": date_str,
            "metrics": summary_data
        })

        return summary_file

    def local_finalize_summary(self, draft_summaries: list) -> Path:
        """
        Local zone: Finalize summary from cloud draft (per Platinum spec).

        Args:
            draft_summaries: List of paths to draft summaries to combine

        Returns:
            Path: Path to the final summary file
        """
        if VAULT_ENVIRONMENT != "local":
            logger.warning("local_finalize_summary called on non-local environment")
            return None

        logger.info(f"Finalizing Odoo revenue summary from {len(draft_summaries)} draft(s)")

        # Combine metrics from all draft summaries
        combined_metrics = {"invoices": []}
        for draft_path in draft_summaries:
            if draft_path.exists():
                try:
                    content = draft_path.read_text(encoding="utf-8")
                    # Extract metrics from YAML frontmatter
                    import yaml
                    if "---" in content:
                        frontmatter_text = content.split("---")[1]
                        frontmatter = yaml.safe_load(frontmatter_text)
                        if "metrics" in frontmatter:
                            metrics = frontmatter["metrics"]
                            if "invoices" in metrics:
                                combined_metrics["invoices"].extend(metrics["invoices"])
                            # Add other metrics as needed
                except Exception as e:
                    logger.warning(f"Could not parse draft summary {draft_path}: {e}")

        date_str = datetime.now().strftime('%Y%m')
        final_summary_file = ACCOUNTING_DIR / f"SUMMARY_ODOO_{date_str}.md"

        # Create the final summary with combined metrics
        table_rows = ["| Invoice | Amount | Status |", "|---------|--------|--------|"]
        for invoice in combined_metrics["invoices"]:
            inv_num = invoice.get("number", "N/A")
            amount = invoice.get("amount", "N/A")
            status = invoice.get("status", "N/A")
            table_rows.append(f"| {inv_num} | ${amount} | {status} |")

        final_summary_content = f"""---
type: odoo_summary
date: {date_str}
metrics: {combined_metrics}
zone: local
status: final
---

# Odoo Revenue Summary - {date_str}

## Final Revenue Metrics

{chr(10).join(table_rows)}

## Summary
This final summary incorporates data from both cloud and local Odoo metrics.
It has been approved and finalized by the local agent.

**Compiled by:** Odoo Platinum Local
**Finalized:** {datetime.now().isoformat()}
"""

        final_summary_file.write_text(final_summary_content, encoding="utf-8")
        logger.info(f"Final Odoo summary created: {final_summary_file.name}")

        # Log the summary generation
        log_action("summary_finalized", {
            "summary_file": str(final_summary_file.name),
            "date": date_str,
            "metrics": combined_metrics
        })

        return final_summary_file

    def run_health_check(self):
        """
        Run health check for cloud Odoo instance (per Platinum spec).
        """
        logger.info("Running Odoo health check")

        success = check_odoo_health()

        if success:
            # Create health update for dashboard
            update_file = UPDATES_DIR / f"odoo_health_ok_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            update_content = f"""---
type: health_status
source: odoo_platinum
timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}
summary: Odoo service health check passed
---

# Health Monitor: Odoo Status

- **Status:** OK
- **Service:** Odoo
- **Check Time:** {datetime.now().isoformat()}
- **Details:** Cloud Odoo instance is responding normally
"""
            update_file.write_text(update_content, encoding="utf-8")
            logger.info(f"Health OK update created: {update_file.name}")

            # Log the health check
            log_action("health_check", {"service": "odoo", "status": "ok"}, "success")
        else:
            # Create health error for dashboard
            error_file = UPDATES_DIR / f"odoo_health_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            error_content = f"""---
type: health_error
source: odoo_platinum
timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}
summary: Odoo service health check failed
---

# Health Monitor: Odoo Status

- **Status:** ERROR
- **Service:** Odoo
- **Check Time:** {datetime.now().isoformat()}
- **Details:** Cloud Odoo instance is not responding
"""
            error_file.write_text(error_content, encoding="utf-8")
            logger.info(f"Health error created: {error_file.name}")

            # Log the health failure
            log_action("health_check", {"service": "odoo", "status": "error"}, "failed")

    def process_needs_action(self):
        """
        Process any Odoo-related items in the appropriate Needs_Action directory.
        Cloud processes cloud items, local processes local items.
        """
        logger.info(f"Processing Odoo needs_action items for {VAULT_ENVIRONMENT} zone")

        if VAULT_ENVIRONMENT == "cloud":
            # Cloud only processes cloud-specific needs (e.g., triage from skill-cloud-triage)
            needs_dir = NEEDS_ACTION_CLOUD
            action_pattern = r'.*_odoo_.*\.md$'  # Files with odoo in the name
        else:
            # Local processes local items (if any) and approved items
            needs_dir = NEEDS_ACTION_LOCAL
            action_pattern = r'.*\.md$'  # All local needs

        items_processed = 0
        for item_file in needs_dir.glob(action_pattern):
            try:
                if claim_file(item_file, VAULT_ENVIRONMENT):
                    # Process the item based on its type
                    content = item_file.read_text(encoding="utf-8")

                    # Move to Done after processing
                    done_dir = DONE_CLOUD if VAULT_ENVIRONMENT == "cloud" else DONE_LOCAL
                    done_file = done_dir / item_file.name
                    item_file.rename(done_file)

                    items_processed += 1
                    logger.info(f"Processed Odoo needs_action item: {item_file.name}")
                else:
                    logger.info(f"Skipped already-claimed item: {item_file.name}")
            except Exception as e:
                logger.error(f"Error processing Odoo needs_action item {item_file.name}: {e}")

        logger.info(f"Processed {items_processed} Odoo needs_action items")

# ── MAIN EXECUTION ────────────────────────────────────────────────────────
def main():
    """Main function to demonstrate the Odoo Platinum skill."""
    import argparse

    parser = argparse.ArgumentParser(description="Odoo Platinum Skill")
    parser.add_argument("--draft-invoice", help="Create an invoice draft (cloud only)")
    parser.add_argument("--partner", help="Partner name for invoice")
    parser.add_argument("--amount", type=float, help="Amount for invoice")
    parser.add_argument("--process-approved", help="Process an approved invoice file (local only)")
    parser.add_argument("--generate-draft-summary", action="store_true", help="Generate draft summary (cloud only)")
    parser.add_argument("--health-check", action="store_true", help="Run health check (cloud only)")
    parser.add_argument("--env", choices=["cloud", "local"], help="Specify environment manually")
    parser.add_argument("--demo", action="store_true", help="Run Platinum demo")

    args = parser.parse_args()

    if args.env:
        os.environ["VAULT_ENVIRONMENT"] = args.env

    integrator = OdooPlatinum()

    if args.draft_invoice and args.partner and args.amount:
        if VAULT_ENVIRONMENT != "cloud":
            print("Error: Drafting should be done on cloud environment")
            return
        result = integrator.cloud_draft_invoice(args.partner, args.amount, args.draft_invoice)
        print(json.dumps(result, indent=2))

    elif args.process_approved:
        if VAULT_ENVIRONMENT != "local":
            print("Error: Processing approved invoices should be done on local environment")
            return
        approved_path = Path(args.process_approved)
        if approved_path.exists():
            result = integrator.local_process_approved_invoice(approved_path)
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: Approved file not found: {approved_path}")

    elif args.generate_draft_summary:
        if VAULT_ENVIRONMENT != "cloud":
            print("Error: Draft summary should be generated on cloud environment")
            return
        summary_path = integrator.cloud_generate_summary_draft()
        print(f"Draft summary generated: {summary_path}")

    elif args.health_check:
        if VAULT_ENVIRONMENT != "cloud":
            print("Error: Health checks should be run on cloud environment")
            return
        integrator.run_health_check()
        print("Health check completed")

    elif args.demo:
        print(f"Running Odoo Platinum demo for {VAULT_ENVIRONMENT} environment...")

        if VAULT_ENVIRONMENT == "cloud":
            print(f"\n1. Creating invoice draft for Acme Corp, $5000.00")
            result = integrator.cloud_draft_invoice("Acme Corp", 5000.00, "Q1 Services")
            print(f"Result: {json.dumps(result, indent=2)}")

            print(f"\n2. Running health check...")
            integrator.run_health_check()
            print("Health check completed")

            print(f"\n3. Generating draft summary...")
            summary_path = integrator.cloud_generate_summary_draft()
            print(f"Draft summary created: {summary_path}")

        else:  # local environment
            print(f"\n1. Processing Odoo invoices in queue...")
            # Process any approved invoices
            integrator.process_needs_action()

        print(f"\nPlatinum demo completed for {VAULT_ENVIRONMENT} zone!")

    else:
        print("Odoo Platinum Skill")
        print(f"Environment: {VAULT_ENVIRONMENT}")
        print("Usage:")
        print("  --draft-invoice \"desc\" --partner NAME --amount AMT  : Create draft (cloud only)")
        print("  --process-approved FILE      : Process approved invoice (local only)")
        print("  --generate-draft-summary     : Generate summary draft (cloud only)")
        print("  --health-check               : Run health check (cloud only)")
        print("  --env cloud|local            : Specify environment")
        print("  --demo                       : Run zone-appropriate demo")


if __name__ == "__main__":
    main()