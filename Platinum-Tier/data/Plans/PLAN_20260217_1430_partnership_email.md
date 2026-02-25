---
type: plan
source_file: EMAIL_ae7f29b3c4d1.md
status: in_progress
plan_id: PLAN_20260217_1430_partnership_email
skills_needed:
  - skill-mcp-email
  - skill-linkedin-draft
  - skill-approval-request-creator
  - skill-logger
approval_required: true
created: 2026-02-17T14:30:00Z
completed:
---

## Objective
Process inbound partnership email: draft reply, generate LinkedIn post about the opportunity, route both through HITL.

## Steps
- [x] Step 1: Parse email and identify actions → skill-needs-action-processor
- [x] Step 2: Draft email reply via MCP → skill-mcp-email
- [x] Step 3: Create HITL approval for email reply → skill-approval-request-creator
- [x] Step 4: Generate LinkedIn post about partnership news → skill-linkedin-draft
- [x] Step 5: Create HITL approval for LinkedIn post → skill-approval-request-creator
- [x] Step 6: Await human approval for email (HITL) → skill-hitl-watcher
- [ ] Step 7: Await human approval for LinkedIn (HITL) → skill-hitl-watcher
- [x] Step 8: If email approved → MCP send via skill-mcp-email
- [ ] Step 9: If LinkedIn approved → post via skill-linkedin-draft

## Dependencies
- Steps 6-7 require human action (move files to data/Approved/)
- Step 8 blocked until Step 6 completes ✓
- Step 9 blocked until Step 7 completes

## Act
- Step 1: Email parsed — from Sarah Chen, partnership proposal, high priority
- Step 2: Reply drafted via MCP draft tool → EMAIL_REPLY_ae7f29b3c4d1.md
- Step 3: Approval created → APPROVAL_EMAIL_REPLY_20260217.md
- Step 4: LinkedIn draft generated → LINKEDIN_DRAFT_PARTNERSHIP_20260217.md
- Step 5: Approval created → APPROVAL_LINKEDIN_PARTNERSHIP_20260217.md
- Step 6: Human approved email reply → moved to data/Approved/
- Step 8: HITL watcher routed to skill-mcp-email → DRY_RUN send → moved to data/Done/

## Result
Plan in progress — Steps 1-6, 8 complete. Step 7 (LinkedIn approval) awaiting human. Step 9 blocked.
