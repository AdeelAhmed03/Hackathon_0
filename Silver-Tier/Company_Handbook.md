# Company Handbook

## Overview
This handbook contains all company policies, procedures, and guidelines for employees.

## General Policies
- All employees must maintain professional conduct
- Confidentiality agreements must be respected at all times
- Data security protocols must be followed strictly

## Approval Process
- All requests must go through proper channels
- Multi-level approvals are required for sensitive operations
- Documentation must be maintained for all decisions

## Compliance
- All operations must comply with industry regulations
- Regular audits will be conducted
- Violations will result in disciplinary action

---

## Silver Tier Policies

### Plan Creation Policy
- **Mandatory** for any task requiring 2 or more distinct steps or skills
- Plans must be created in `data/Plans/` with proper YAML frontmatter
- Each plan step must reference exactly one skill
- Plans must identify which steps require HITL approval before execution
- Single-step tasks do NOT require plans — execute directly
- All plans must follow the Think/Plan/Act/Result structure
- Failed plans must be marked as `blocked` with clear explanation in Result section

### LinkedIn Posting Policy
- All LinkedIn posts must be 150-300 words
- Tone must be professional, engaging, and authentic
- Post types: update, announcement, thought_leadership, milestone
- **All LinkedIn posts ALWAYS require HITL approval** — no exceptions
- Posts must not contain confidential company information
- Maximum 3-5 hashtags per post
- `LINKEDIN_DRY_RUN=true` must be used for initial testing
- Draft → Plan → Pending_Approval → (human approves) → Post

### MCP Email Policy
- **All email sends require HITL approval** — no exceptions
- Agent NEVER sends email directly — always through approval workflow
- `MCP_EMAIL_DRY_RUN=true` must be enabled for initial testing and verification
- Email credentials must NEVER be logged or exposed
- Email body content is truncated to 200 chars in audit logs
- Retry up to 3 times with exponential backoff on SMTP failure
- Supported actions: send_email, reply_email, forward_email
- All emails must have clear context explaining why they are being sent

### Scheduling Policy
- Scheduled tasks enter the system via `data/Needs_Action/` queue
- Task files are picked up by the existing `needs_action_watcher.py` pipeline
- **Deduplication is mandatory** — check `scheduler_state.json` before creating tasks
- Each task type can only fire once per day (per dedup rules)
- Scheduler state is persisted in `data/Logs/scheduler_state.json`
- Schedule times are configured via environment variables
- `--force-trigger` flag available for testing, bypasses dedup

### HITL (Human-in-the-Loop) Policy
- **The agent NEVER self-approves** — only humans move files to `data/Approved/`
- Human approval is required for: email sends, LinkedIn posts, external communications, sensitive data access
- To approve: move file from `data/Pending_Approval/` to `data/Approved/`
- To reject: move file from `data/Pending_Approval/` to `data/Rejected/`
- The HITL watcher routes approved files to the correct execution skill by `action` field
- Files that have already been executed (have `execution_result` set) must not be re-executed
- All routing decisions and execution results must be logged

---

## Silver Tier Additions
- Add two+ watchers (e.g. WhatsApp via Playwright, LinkedIn via API/MCP)
- For all tasks: Create Plan.md with checkboxes
- Generate daily LinkedIn sales post drafts (e.g. "Our new product boosted revenue 20% – DM for details")
- Use MCP for email sends (draft first, HITL approve)
- Human approval workflow: Watch /Approved/ → execute
- Basic scheduling: Daily at 8AM refresh dashboard / generate briefs
- Flag payments/social >threshold for approval

Last updated: 2026-02-17
