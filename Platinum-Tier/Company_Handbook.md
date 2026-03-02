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

## Gold Tier Policies

### Odoo Accounting Policy
- All accounting operations routed through the odoo-mcp server (JSON-RPC)
- `ODOO_DRY_RUN=true` must be enabled for initial testing — returns mock data
- **Invoice creation always requires HITL approval** — no exceptions
- **Payments above $5,000 require HITL approval**
- Accounting records saved to `data/Accounting/` as structured .md files
- Partner linking: email contacts cross-referenced with Odoo partners
- Exponential backoff (3 retries) on Odoo connection failures
- All Odoo operations logged with correlation IDs via skill-audit-logger
- Financial data must never be exposed in social media posts

### Social Media Policy
- **All social media posts require HITL approval** — no exceptions, all platforms
- Supported platforms: Facebook (Graph API v19.0), Instagram (Graph API), Twitter/X (API v2)
- Platform-specific formatting rules:
  - **Facebook:** No character limit, supports long-form content
  - **Instagram:** Max 2200 characters, requires image_url for actual posts
  - **Twitter/X:** Max 280 characters strict limit
- Content guidelines:
  - Professional, brand-aligned tone across all platforms
  - No confidential business data (revenue figures, client names without consent)
  - Maximum 3-5 hashtags per post
  - Cross-post content must be adapted per platform (not copy-paste)
- `FB_DRY_RUN=true` and `X_DRY_RUN=true` for initial testing
- Workflow: Draft → Approval → Post via social-mcp → Log result
- Engagement summaries generated for weekly audit and CEO briefing

### Weekly Audit Policy
- Runs weekly on `CEO_BRIEF_DAY` (default: Sunday) at `CEO_BRIEF_HOUR` (default: 9)
- Covers the previous 7-day period
- Audit scope: completed tasks, accounting records, social metrics, system health
- Output: `data/Briefings/AUDIT_{YYYYMMDD}.md`
- Audit is read-only — never modifies source data
- Anomaly flags: overdue invoices >30 days, error rate >5%, engagement drop >20%

### CEO Briefing Policy
- Generated after weekly audit completes — dependency on audit data
- Maximum 500 words — concise, scannable, actionable
- Must include: KPI table, key highlights, issues requiring attention, recommendations
- Status indicators: Green (on target), Yellow (concern), Red (immediate attention)
- Output: `data/Briefings/CEO_BRIEF_{YYYYMMDD}.md`
- Professional executive tone — no jargon, no technical details
- Can be generated on-demand via manual task file

### Error Recovery Policy
- **Never silently drop errors** — every failure must be logged and tracked
- Retry strategy: exponential backoff — 3 attempts (2s, 4s, 8s delays)
- Maximum retries: configurable via `MAX_RETRY_ATTEMPTS` (default: 3)
- On permanent failure: quarantine task to `data/Quarantine/` with error metadata
- Graceful degradation: if one component fails, others continue independently
- Quarantine files include: original task data, error reason, retry count, stack trace
- Recoverable items can be manually moved back to `data/Needs_Action/` for retry
- Error patterns tracked and reported in weekly audit

### Cross-Domain Integration Policy
- Personal (email, LinkedIn) ↔ Business (Odoo, social media) data linked where relevant
- Email contacts automatically matched to Odoo partners
- LinkedIn connections can be cross-referenced with business contacts
- Social engagement metrics contextualize CEO Briefing business data
- Cross-domain linking is informational only — never auto-creates Odoo records from email
- PII handling: email addresses logged, passwords never logged, financial data restricted

### Audit Logging Policy
- All agent actions logged to `data/Logs/YYYY-MM-DD.json`
- Gold-tier enhanced logging adds: severity, correlation_id, duration_ms, error_trace
- Severity levels: DEBUG, INFO, WARN, ERROR, CRITICAL
- Correlation IDs link all log entries for a single task lifecycle
- PII handling: email bodies truncated to 200 chars, passwords never logged
- Retention: configurable via `AUDIT_RETENTION_DAYS` (default: 90 days)
- Log files are gitignored — only .gitkeep committed

---

## Silver Tier Additions
- Add two+ watchers (e.g. WhatsApp via Playwright, LinkedIn via API/MCP)
- For all tasks: Create Plan.md with checkboxes
- Generate daily LinkedIn sales post drafts (e.g. "Our new product boosted revenue 20% – DM for details")
- Use MCP for email sends (draft first, HITL approve)
- Human approval workflow: Watch /Approved/ → execute
- Basic scheduling: Daily at 8AM refresh dashboard / generate briefs
- Flag payments/social >threshold for approval

## Gold Tier Additions
- Full integration: Personal (Gmail/WhatsApp/bank) + Business (Odoo/social)
- Odoo: Self-hosted local, MCP JSON-RPC for accounting (invoices, payments)
- Social: FB/IG/X – post approved messages, generate engagement summaries
- Multiple MCPs: odoo-mcp, social-mcp, browser-mcp (for payments)
- Weekly audit: Read /Accounting/, Odoo → flag bottlenecks, generate CEO Briefing
- Error recovery: Retries, degradation, quarantine
- Logging: JSON in /Logs/ with spec fields (timestamp, action_type, actor, etc.)
- Ralph: Multi-step until /Done/ move
- Docs: Generate architecture + lessons

### Platinum Tier Policies

#### Cloud/Local Work-Zone Separation Policy
- **Cloud Agent (Cloud Executive)**: Handles email triage, draft generation, social media drafts, Odoo draft actions
- **Local Agent**: Handles approvals, WhatsApp, banking operations, actual execution/sends/posts/payments
- **No crossover**: Cloud agent never performs local-only operations, vice versa
- **Delegation**: Cloud writes to local directories when action requires local execution
- **Sync Protocol**: Git-based synchronization between cloud and local vaults
- **Only .md files and state data are synchronized** — no secrets, credentials, or session data
- **Conflict Resolution**: Local changes take precedence for execution decisions

#### Draft-Only Policy
- **Cloud Agent Rule**: Cloud Executive never executes sends/posts/payments — only creates drafts
- **Draft Locations**: Email replies → `data/Plans/cloud/`, Social posts → `data/Plans/cloud/`, Odoo actions → draft invoices
- **Approval Workflow**: All drafts requiring execution must go through `/Pending_Approval/local/`
- **No Direct Execution**: Cloud agent cannot directly send emails, post to social media, or execute payments
- **Verification**: Drafts must include clear intent and context for local human approval

#### Cloud Executive Triage Policy
- **Priority Levels**: Critical (response within 1 hour), High (response within 4 hours), Normal (response within 24 hours)
- **Triage Criteria**: Based on sender, urgency flags, business impact, customer status
- **Routing**: Categorize by type (email, social, accounting) and route to appropriate draft handler
- **Escalation**: Issues requiring immediate human attention marked as `priority: critical`
- **Documentation**: All triage decisions logged with reasoning for audit

#### Git Sync Protocol Policy
- **Sync Frequency**: Automatic sync on task completion and every 15 minutes
- **Conflict Handling**: Local changes take precedence for execution decisions
- **No Secrets**: .env files, tokens, and credentials never synced
- **Dashboard Updates**: Cloud writes to `/Updates/` folder for local merge
- **Rollback Capability**: Git-based recovery for sync conflicts or errors
- **Health Monitoring**: Monitor sync status and alert local on failures

#### Cloud Health Monitoring Policy
- **24/7 Operation**: Cloud Executive must maintain 99.9% uptime on cloud VM
- **Alerting**: Alert local agent on cloud service degradation or failures
- **Auto-Recovery**: Attempt auto-recovery up to 3 times before alerting
- **Graceful Degradation**: Queue tasks when MCP services unavailable
- **Performance Monitoring**: Track response times, error rates, and throughput
- **Status Reporting**: Regular health reports via `/Updates/health_status.md`

#### A2A Phase 2 Policy (Optional)
- **Opt-in Feature**: A2A Phase 2 optional and must be explicitly enabled
- **Logging**: All direct messages through A2A Phase 2 logged to vault
- **Security**: Additional authorization layer required for sensitive operations
- **Audit Trail**: Direct messages create full audit trail like other operations
- **Scope Limitation**: A2A Phase 2 restricted to pre-defined safe operations

#### Local Executive Approval Policy
- **HITL Requirement**: All external actions (email sends, social posts, payments) require human approval
- **Approval Process**: Human moves files from `/Pending_Approval/local/` to `/Approved/`
- **Local Execution Only**: Local agent executes approved actions using local credentials
- **No Cloud Execution**: Cloud agent drafts only, never executes
- **Credential Isolation**: Local credentials never accessible to cloud system

#### Local Executive Dashboard Policy
- **Single-Writer Principle**: Cloud writes to `/Updates/`, local merges to Dashboard.md
- **Merge Protocol**: Process cloud updates from `/Updates/` and merge with local metrics
- **Conflict Resolution**: Preserve local metrics while incorporating cloud data
- **Sync Coordination**: Dashboard updates coordinated through Git sync mechanism
- **State Consistency**: Maintain consistent dashboard state across cloud/local systems

#### Local Executive Security Policy
- **Secrets Isolation**: All sensitive credentials stored on local system only
- **Execution Boundary**: Local agent uses local credentials for all executions
- **Sync Exclusion**: Secrets never synchronized to cloud via Git
- **Access Control**: Local operations require local authentication
- **Audit Compliance**: All local operations fully logged with local context

#### Social Media Authentication Policy
- **Browser-based Authentication**: Use `social_auth.py` to authenticate social media accounts via browser
- **Platform Support**: Facebook, Instagram, and X/Twitter authentication via Playwright automation
- **Authentication Storage**: Session cookies saved to `data/Logs/{platform}_cookies.json`
- **Security**: No passwords stored, only secure session cookies for automation
- **Usage**: Run `python social_auth.py <platform>` to authenticate (e.g., `python social_auth.py facebook`)
- **Approval Required**: All social media posts require HITL approval regardless of authentication method

---

## Platinum Tier Additions
- Cloud 24/7: VM (Oracle/AWS), always-on watchers/orchestrator/health
- Work-Zones: Cloud (drafts/triage), Local (approvals/exec/secrets)
- Delegation: Synced /data/ subfolders (/Needs_Action/<domain>/ etc.); claim-by-move; cloud /Updates/ → local Dashboard merge
- Sync: Git (recommended) or Syncthing (Phase 1); markdown/state only, no secrets
- Odoo: Deploy on cloud VM w/ HTTPS, backups, monitoring; cloud drafts, local posts
- A2A Phase 2: Optional direct agent msgs (replace some files), vault audit
- Security: No secrets sync; local owns sensitive
- Demo: Offline local → cloud draft → online approve → local send
- Local Executive: Handles approvals, WhatsApp, banking, final sends/posts

Last updated: 2026-02-21
