# AI Employee Vault - Gold Tier

## Project Overview
This is a Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0. It uses Claude Code as the reasoning engine and an Obsidian-compatible Markdown vault as the dashboard and memory system. Gold Tier adds full cross-domain integration, Odoo accounting, social media management (FB/IG/X), weekly CEO briefings, error recovery, comprehensive audit logging, watchdog process monitoring, and architecture documentation.

## Architecture
- **Brain**: Claude Code (Ralph Wiggum 16-step Gold loop for autonomous task completion)
- **Memory/GUI**: Obsidian vault (local Markdown files in `data/`)
- **Senses**: Python watcher scripts in `watcher/`
- **Skills**: 18 Agent skill definitions in `skills/`
- **Actions**: 4 MCP servers in `mcp-servers/` (email, odoo, social, per-platform social)
- **Supervision**: Orchestrator and watchdog for process health

## Directory Structure
```
data/Inbox/           - Drop-folder for new files
data/Needs_Action/    - Items awaiting agent processing
data/Pending_Approval/- Items requiring human approval
data/Approved/        - Human-approved items
data/Rejected/        - Human-rejected items
data/Done/            - Completed tasks
data/Plans/           - Multi-step execution plans (Silver)
data/Logs/            - JSON audit logs (enhanced Gold format)
data/Accounting/      - Odoo invoices, transactions, payments (Gold)
data/Briefings/       - Weekly audits and CEO briefings (Gold)
data/Docs/            - Architecture and lessons learned (Gold)
data/Quarantine/      - Error recovery quarantine folder (Gold)
data/In_Progress/     - Claimed tasks awaiting processing (Gold - claim-by-move)
```

## Key Files
- `data/Dashboard.md` - Real-time status overview (updated by agent)
- `Company_Handbook.md` - Rules of engagement and policies (Bronze + Silver + Gold)
- `agents/agent-core.md` - Core agent framework definition (16-step Gold loop)
- `agents/agent-autonomous-employee.md` - Gold agent role definition
- `watcher/gmail_watcher.py` - Polls Gmail for unread/important emails
- `watcher/needs_action_watcher.py` - Filesystem watcher that triggers Claude agent with claim-by-move
- `watcher/hitl_watcher.py` - Watches data/Approved/ for human-approved files (Silver)
- `watcher/scheduler.py` - Time-based scheduler for recurring tasks (Silver)
- `watcher/facebook_watcher.py` - Facebook feed monitoring with claim-by-move (Gold)
- `watcher/instagram_watcher.py` - Instagram feed monitoring with claim-by-move (Gold)
- `watcher/x_watcher.py` - X/Twitter feed monitoring with claim-by-move (Gold)
- `orchestrator.py` - Central supervisor for all watchers and cron jobs (Gold)
- `watchdog.py` - Process health monitor with auto-restart and escalation (Gold)
- `retry_handler.py` - Error classification and retry logic with quarantine (Gold)
- `audit_logger.py` - Centralized structured JSON logging (Gold)
- `mcp-servers/email-mcp/index.js` - Email MCP server (Node.js, nodemailer)
- `mcp-servers/odoo-mcp/odoo_mcp.py` - Odoo accounting MCP server (Gold)
- `mcp-servers/social-mcp/social_mcp.py` - Social media MCP server (Gold)
- `mcp-servers/social-mcp-fb/social-mcp-fb.js` - Facebook MCP server (Node.js) (Gold)
- `mcp-servers/social-mcp-ig/social-mcp-ig.js` - Instagram MCP server (Node.js) (Gold)
- `mcp-servers/social-mcp-x/social-mcp-x.js` - X/Twitter MCP server (Node.js) (Gold)

## Conventions
- All task files use YAML frontmatter with `type`, `status`, `priority` fields
- Files move between directories to indicate status changes
- Never delete files — always move to `data/Done/` (or `data/Quarantine/` on permanent failure)
- Sensitive actions require approval (file moved to `data/Pending_Approval/`)
- Plans use `PLAN_{YYYYMMDD_HHMM}_{description}.md` naming convention
- Scheduled tasks use `SCHEDULED_{task_type}_{YYYYMMDD}.md` naming convention
- Accounting records use `INV_{ref}_{YYYYMMDD}.md` or `PAY_{ref}_{YYYYMMDD}.md`
- Audit reports use `AUDIT_{YYYYMMDD}.md` in data/Briefings/
- CEO briefings use `CEO_BRIEF_{YYYYMMDD}.md` in data/Briefings/
- Quarantine files use `QUARANTINE_{original_name}_{YYYYMMDD}.md`
- Claim-by-move: Move files to `data/In_Progress/{agent}/` to claim ownership (Gold)
- HITL: Only humans move files to Approved/ — agent never self-approves
- Logs are enhanced JSON format in `data/Logs/YYYY-MM-DD.json` with severity, correlation_id, duration_ms
- All social media posts require HITL approval on all platforms
- Invoice creation always requires HITL approval
- DRY_RUN mode available for all external integrations (email, Odoo, social)
- Ralph loop maximum 20 iterations with completion promise: `--completion-promise "TASK_COMPLETE"`

## Agent Skills

### Bronze Skills (1-5)
1. **File System Access** - Read/write/list/move files within project
2. **Needs Action Processor** - Parse and route new task files
3. **Dashboard Updater** - Update counts and activity in Dashboard.md
4. **Approval Request Creator** - Generate approval files for sensitive actions
5. **Logger** - Append structured JSON log entries

### Silver Skills (6-10)
6. **Plan Creator** - Create multi-step execution plans in data/Plans/
7. **LinkedIn Draft** - Generate professional LinkedIn post drafts (150-300 words)
8. **MCP Email** - Send email via SMTP (only from Approved/, always HITL)
9. **HITL Watcher** - Route approved files to correct execution skill by action field
10. **Scheduler** - Create scheduled task files via time-based triggers

### Gold Skills (11-18)
11. **Odoo MCP** - Interface with Odoo Community accounting via JSON-RPC MCP
12. **Social Integrator** - Post to FB/IG/X and generate engagement summaries
13. **Weekly Audit** - Audit business data (tasks, accounting, social, health)
14. **CEO Briefing** - Generate executive summary from audit data
15. **Error Recovery** - Retry logic, quarantine, graceful degradation
16. **Audit Logger** - Enhanced logging (severity, correlation IDs, duration, traces)
17. **Ralph Advanced** - 16-step Ralph Wiggum loop with file-move completion detection, claim-by-move, max 20 iterations
18. **Doc Generator** - Generate ARCHITECTURE.md and LESSONS.md

## MCP Servers

| Server | Language | Protocol | Tools | DRY_RUN |
|--------|----------|----------|-------|---------|
| email-mcp | Node.js | stdio JSON-RPC | draft, send | MCP_EMAIL_DRY_RUN |
| odoo-mcp | Python | stdio JSON-RPC | create_invoice, get_invoices, create_payment, get_payments, get_account_summary, search_partners | ODOO_DRY_RUN |
| social-mcp | Python | stdio JSON-RPC | post_to_facebook, get_fb_feed_summary, post_to_instagram, get_ig_media_summary, post_tweet, get_x_timeline_summary | FB_DRY_RUN, X_DRY_RUN |
| social-mcp-fb | Node.js | stdio JSON-RPC | post_message, get_summary | FB_DRY_RUN |
| social-mcp-ig | Node.js | stdio JSON-RPC | post_media, get_summary | IG_DRY_RUN |
| social-mcp-x | Node.js | stdio JSON-RPC | post_tweet, get_summary | X_DRY_RUN |

## Error Recovery & Monitoring

### Error Classification (Gold)
- **Transient** (retry with backoff): Network timeouts, rate limits, 5xx errors - auto-retry
- **Auth** (no retry): 401/403, expired tokens - alert human
- **Logic** (no retry): Bad input, parse errors, 4xx - review queue

### Recovery Mechanisms (Gold)
- **Retry Handler**: Automatic retries with exponential backoff (2s, 4s, 8s) for transient errors
- **Quarantine**: Failed tasks moved to `data/Quarantine/` with metadata
- **Error Alerts**: `ERROR_{id}.md` files in Needs_Action for human attention
- **Watchdog**: Process monitoring with restart on crashes and escalation after max attempts
- **Graceful Degradation**: Queue tasks when services are unavailable

### Process Supervision (Gold)
- **Orchestrator**: Central supervisor managing all watchers and cron jobs
- **Watchdog**: Dedicated process monitor watching individual components
- **Claim-by-Move Pattern**: Files moved to `/In_Progress/{agent}/` to prevent concurrent processing

## Security
- Credentials stored in `.env` (never committed)
- `.gitignore` excludes all secrets, tokens, and session data
- Human-in-the-loop for all sensitive/external actions
- DRY_RUN mode available for safe testing of all integrations
- PII handling: email bodies truncated in logs, passwords never logged
- Financial data restricted from social media content
- No sensitive actions auto-approved by AI (HITL required)
