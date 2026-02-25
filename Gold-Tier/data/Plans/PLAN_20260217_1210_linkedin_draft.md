---
type: plan
source_file: SCHEDULED_linkedin_draft_20260217.md
status: in_progress
plan_id: PLAN_20260217_1210_linkedin_draft
skills_needed:
  - skill-linkedin-draft
  - skill-approval-request-creator
  - skill-logger
approval_required: true
created: 2026-02-17T12:10:00Z
completed:
---

## Objective
Generate a daily LinkedIn sales post draft and route through HITL approval.

## Steps
- [x] Step 1: Read Company_Handbook.md for branding/tone → skill-linkedin-draft
- [x] Step 2: Generate LinkedIn draft post → skill-linkedin-draft
- [x] Step 3: Create HITL approval file → skill-approval-request-creator
- [ ] Step 4: Await human approval (HITL) → skill-hitl-watcher
- [ ] Step 5: If approved, post via LinkedIn API → skill-linkedin-draft

## Dependencies
- Step 4 requires human action (move file to data/Approved/)
- Step 5 blocked until Step 4 completes

## Act
- Step 1: Handbook loaded — tone: professional, engaging, sales-oriented
- Step 2: Draft generated → LINKEDIN_DRAFT_20260217.md
- Step 3: Approval request created → APPROVAL_LINKEDIN_20260217.md

## Result
Plan in progress — awaiting HITL approval at Step 4.
