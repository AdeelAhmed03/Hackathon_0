# AI Employee Vault - Platinum Tier

## Project Overview
This is the Cloud Executive extension for GIAIC Hackathon 0. It runs as a 24/7 cloud-based agent specializing in email triage, draft generation, and social media drafts. The Platinum Tier builds upon Gold Tier's Autonomous Employee with distributed cloud/local operation, Git-synced vault, and specialized work-zone separation.

## Architecture
- **Cloud Agent**: 24/7 Cloud Executive specializing in triage/drafts (email/social/Odoo actions as drafts)
- **Local Agent**: Handles approvals, WhatsApp, banking, and actual sends/posts/payments
- **Synchronized Vault**: Git/Syncthing for .md/state files only (no secrets)
- **Work-Zone Separation**: Cloud triage/drafts, local execution/approvals
- **Claim-by-Move**: Files moved to `/In_Progress/cloud/` for processing
- **Single-Writer Dashboard**: Cloud writes to `/Updates/` for local merge

## Directory Structure
```
data/Inbox/                 - Drop-folder for new files
data/Needs_Action/cloud/    - Cloud-specific items awaiting processing
data/Needs_Action/local/    - Local-specific items awaiting processing
data/Plans/cloud/           - Cloud-generated plans
data/Pending_Approval/local/- Items requiring local human approval
data/Approved/              - Human-approved items
data/Rejected/              - Human-rejected items
data/Done/cloud/            - Cloud-processed tasks
data/Done/local/            - Local-processed tasks
data/In_Progress/cloud/     - Items claimed by cloud agent
data/In_Progress/local/     - Items claimed by local agent
data/Updates/               - Cloud agent updates for local merge
data/Plans/                 - Multi-step execution plans (Silver)
data/Logs/                  - JSON audit logs (enhanced Gold format)
data/Accounting/            - Odoo invoices, transactions, payments (Gold)
data/Briefings/             - Weekly audits and CEO briefings (Gold)
data/Docs/                  - Architecture and lessons learned (Gold)
data/Quarantine/            - Error recovery quarantine folder (Gold)
```

## Key Files
- `agents/agent-cloud-executive.md` - Platinum agent role definition with 20-step loop
- `agents/agent-local-executive.md` - Local agent role definition for approval/execution
- `Company_Handbook.md` - Platinum policies (cloud/local separation, triage rules, Git sync)
- `agents/agent-core.md` - Platinum extended framework with Cloud/Local Executive integration
- `skills/skill-cloud-triage.md` - Cloud triage handler (Platinum skill 19)
- `skills/skill-draft-generator.md` - Draft generation framework (Platinum skill 20)
- `skills/skill-sync-handler.md` - Git sync handler (Platinum skill 21)
- `skills/skill-health-monitor.md` - Health monitoring for cloud agent (Platinum skill 22)
- `skills/skill-a2a-upgrade.md` - A2A Phase 2 optional upgrades (Platinum skill 23)
- `skills/skill-approval-executor.md` - Execute approved actions using local credentials (Platinum skill 24)
- `skills/skill-merge-updater.md` - Merge cloud updates into local Dashboard.md (Platinum skill 25)
- `watcher/cloud_sync_watcher.py` - Git sync watcher for cloud/local coordination
- `watcher/orchestrator_cloud.py` - Cloud orchestrator for 24/7 service
- `watchdog_cloud.py` - Cloud-specific process health monitor

## Conventions
- **Draft-Only Rule**: Cloud agent never executes sends/posts/payments - only drafts
- **Delegation Pattern**: Write to `/Needs_Action/local/`, `/Plans/cloud/`, `/Pending_Approval/local/`
- **Claim-by-Move**: Move files to `/In_Progress/cloud/` to claim ownership
- **Sync Protocol**: Git push/pull for `/data/` (no secrets), use `.env.cloud` for cloud secrets
- **Health Monitoring**: Alert local on cloud issues, graceful degradation
- **Platinum Skills**: 19-23 (cloud triage, draft generation, sync, health, A2A upgrade)
- **Ralph Loop**: 20-step Platinum enhanced loop with cloud-specific steps

## Core Loop (Ralph Wiggum - Platinum enhanced)
1. Read Company_Handbook.md (Platinum updates)
2. Read data/Dashboard.md (via sync)
3. Claim items: Move to /In_Progress/cloud/ if not owned
4. Triage/draft: Email → draft reply in /Plans/cloud/; social → draft post; Odoo → draft invoice
5. Write approval files to /Pending_Approval/local/
6. Update /Updates/cloud_{id}.md for local merge
7. Log, error recovery
8. On done: Move to /Done/cloud/; sync Git
9. If more → <RALPH_CONTINUE>; else TASK_COMPLETE

## Platinum Skills (19-28)

### Cloud Executive Skills (19-23)

#### Skill 19: Cloud Triage (`skill-cloud-triage.md` + `Cloud_Triage.md`)
- Purpose: Triage incoming cloud tasks and route appropriately
- Trigger: New files in data/Needs_Action/cloud/
- Process: Categorize, prioritize, delegate to cloud-specific handlers
- Rules: Follow Platinum work-zone separation policies

#### Skill 20: Draft Generator (`skill-draft-generator.md` + `Draft_Generator.md`)
- Purpose: Generate drafts for email replies, social posts, Odoo actions
- Trigger: Triage results requiring draft creation
- Process: Create draft files in data/Plans/cloud/
- Rules: Draft-only (no execution), proper template adherence

#### Skill 21: Sync Handler (`skill-sync-handler.md` + `Sync_Handler.md`)
- Purpose: Handle Git synchronization between cloud and local
- Trigger: Scheduled sync, file completion, updates
- Process: Git operations for data/ synchronization
- Rules: No secrets sync, conflict resolution

#### Skill 22: Health Monitor (`skill-health-monitor.md` + `Health_Monitor.md`)
- Purpose: Monitor cloud agent health and alert local
- Trigger: Scheduled checks, error detection
- Process: System health checks, alert generation
- Rules: Alert local on degradation, auto-recovery

#### Skill 23: A2A Upgrade (`skill-a2a-upgrade.md` + `A2A_Upgrade.md`)
- Purpose: Handle optional A2A Phase 2 direct messages
- Trigger: A2A Phase 2 enabled configuration
- Process: Direct message handling via MCP
- Rules: Optional feature, logged to vault

### Local Executive Skills (24-28)

#### Skill 24: Approval Executor (`skill-approval-executor.md` + `Approval_Executor.md`)
- Purpose: Process approval requests and execute actions using local MCP and credentials
- Trigger: Files moved to /Approved/ from /Pending_Approval/local/
- Process: Execute approved actions via local MCP servers with local credentials
- Rules: Execute only approved actions, never use cloud credentials

#### Skill 25: Merge Updater (`skill-merge-updater.md` + `Merge_Updater.md`)
- Purpose: Merge cloud updates from /Updates/ into local Dashboard.md
- Trigger: New files in /Updates/ generated by cloud system
- Process: Parse cloud updates and merge metrics into local dashboard
- Rules: Maintain single-writer dashboard principle, preserve local metrics

#### Skill 26: Sync Handler (Local) (`skill-sync-handler.md` + `Sync_Handler.md`)
- Purpose: Handle Git synchronization operations (pull/push) for local system
- Trigger: Local processing completion, dashboard updates, scheduled sync
- Process: Git pull/push operations for data synchronization
- Rules: Pull before push, handle conflicts, exclude secrets

#### Skill 27: Health Monitor (Local) (`skill-health-monitor.md` + `Health_Monitor.md`)
- Purpose: Monitor local system health and performance
- Trigger: Scheduled checks, processing operations
- Process: System health checks, resource monitoring
- Rules: Report health status, detect issues early

#### Skill 28: A2A Upgrade (Local) (`skill-a2a-upgrade.md` + `A2A_Upgrade.md`)
- Purpose: Handle optional A2A Phase 2 direct messages on local system
- Trigger: A2A Phase 2 enabled configuration
- Process: Direct message handling via local MCP
- Rules: Optional feature, logged to vault for compliance

## Work-Zone Separation
- **Cloud Domain**: Email triage, draft generation, social media drafts, Odoo draft actions
- **Local Domain**: Approvals, WhatsApp, banking operations, actual execution/sends/posts/payments
- **Delegation**: Cloud writes to local directories when action requires local execution

## Sync Protocol
- Git-based synchronization between cloud and local vaults
- Only .md files and state data synchronized (no secrets)
- Conflict resolution favors local changes for execution decisions
- Cloud updates Dashboard via /Updates/ files for local merge

## Security
- Cloud `.env` excludes sensitive local operations (banking, approvals)
- Git sync excludes secrets, credentials, and session data
- A2A Phase 2 optional and logged for audit
- Separation of duties: draft vs. execute, cloud vs. local
- Health monitoring with alert escalation
