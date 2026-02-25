# AI Employee Vault - Gold Tier

> Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0
> **Tier:** Gold (Autonomous Employee)

## What Is This?

A local-first, agent-driven AI Employee that monitors your Gmail, manages Odoo accounting, posts to social media (Facebook, Instagram, Twitter/X), and orchestrates a file-based workflow — all powered by **Claude Code** as the reasoning engine and an **Obsidian-compatible Markdown vault** as the dashboard.

The AI doesn't just wait for commands — it watches for new emails and files, reasons about what to do, creates multi-step plans, generates LinkedIn drafts, manages invoices and payments via Odoo, posts to social media with HITL approval, runs weekly business audits with CEO briefings, and handles errors with graceful degradation. Gold Tier adds full cross-domain integration, 6 MCP servers, 18 agent skills, watchdog process monitoring, claim-by-move pattern, and comprehensive audit logging.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    EXTERNAL SOURCES                           │
│  Gmail API │ Odoo (JSON-RPC) │ Facebook │ Instagram │ X/Twitter│
└────┬───────┴───────┬─────────┴────┬─────┴─────┬─────┴────┬──┘
     │               │              │           │          │
     ▼               ▼              ▼           ▼          ▼
┌──────────────────────────────────────────────────────────────┐
│                PERCEPTION LAYER (Watchers)                     │
│  gmail_watcher.py  │ needs_action_watcher.py                  │
│  hitl_watcher.py   │ scheduler.py                             │
│  facebook_watcher.py │ instagram_watcher.py │ x_watcher.py    │
│  orchestrator.py (Gold — supervises all watchers)             │
│  watchdog.py (Gold — process health monitor)                  │
└────────┬───────────┴──────────┬──────────────────────────────┘
         │  Creates .md files   │
         ▼  in data/ dirs       ▼
┌──────────────────────────────────────────────────────────────┐
│                OBSIDIAN VAULT (Local Markdown)                 │
│  /Inbox → /Needs_Action → /Pending_Approval → /Done          │
│  /Plans │ /Accounting │ /Briefings │ /Quarantine │ /Docs     │
│  /In_Progress/ (claim-by-move)                                │
│  Dashboard.md  │  Company_Handbook.md                         │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                REASONING LAYER (Claude Code)                   │
│     Ralph Wiggum Loop: 16-Step Gold Processing                │
│          18 Agent Skills (5 Bronze + 5 Silver + 8 Gold)       │
│        --completion-promise "TASK_COMPLETE" (max 20 iterations)│
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  ACTION LAYER (MCP Servers)                    │
│  email-mcp (Node.js)  │  odoo-mcp (Python)  │  social-mcp    │
│  draft, send           │  invoices, payments  │  FB, IG, X     │
│  social-mcp-fb (Node.js) │ social-mcp-ig (Node.js) │ social-mcp-x (Node.js) │
└──────────────────────────────────────────────────────────────┘
```

## Features

### Bronze Foundation
- **Gmail Watcher** — Polls Gmail every 120s for unread/important emails, creates structured Markdown task files
- **Filesystem Watcher** — Monitors `data/Needs_Action/` and `data/Inbox/` for new `.md` files, triggers Claude Code agent
- **Agent Skills** — 5 Markdown-defined skills: File System Access, Needs Action Processor, Dashboard Updater, Approval Request Creator, Logger
- **File-Based State Machine** — Directories represent workflow states (Inbox → Needs_Action → Pending_Approval → Done)
- **Human-in-the-Loop** — Sensitive actions require approval (move file to Approved/Rejected)
- **Dashboard** — Real-time status overview in `data/Dashboard.md`
- **Audit Logging** — Structured JSON logs in `data/Logs/`

### Silver Enhancements
- **Plan Creator** — Multi-step task reasoning with PLAN files in `data/Plans/`
- **LinkedIn Draft** — Generates 150-300 word professional posts, always requires HITL approval
- **MCP Email** — Sends email via SMTP with mandatory HITL approval and DRY_RUN mode
- **HITL Watcher** — Routes approved files to the correct execution skill by `action` field
- **Scheduler** — Cron-like scheduled task creation (daily LinkedIn drafts, extensible)
- **13-Step Agent Loop** — Enhanced Ralph Wiggum loop with plan creation, approval processing, and scheduling

### Gold Additions
- **Odoo MCP Server** — Accounting integration via JSON-RPC: invoices, payments, partner search, account summaries
- **Social Media MCP Server** — Facebook, Instagram, Twitter/X posting and engagement summaries
- **Per-Platform MCP Servers** — Individual Node.js servers for Facebook, Instagram, Twitter/X
- **Weekly Audit** — Automated business data audit (tasks, accounting, social media, system health)
- **CEO Briefing** — Executive summary generation with KPIs, issues, and recommendations
- **Error Recovery** — Exponential backoff retries, quarantine for permanent failures, graceful degradation
- **Audit Logger** — Enhanced logging with severity levels, correlation IDs, execution timing, error traces
- **Ralph Advanced** — 16-step autonomous loop with file-move completion detection, max 20 iterations
- **Claim-by-Move Pattern** — Files moved to `/In_Progress/{agent}/` to claim ownership and prevent concurrent processing
- **Watchdog Process Monitor** — Dedicated process health monitoring with auto-restart and escalation
- **Orchestrator** — Central supervisor for all watchers and cron jobs
- **Doc Generator** — Architecture and lessons learned documentation
- **Cross-Domain Integration** — Personal (email, LinkedIn) ↔ Business (Odoo, social) data linking
- **6 MCP Servers** — Email (Node.js), Odoo (Python), Social (Python), Facebook/IG/X (Node.js) — all with DRY_RUN support
- **Social Media Watchers** — Individual watchers for Facebook, Instagram, Twitter/X feeds
- **18 Agent Skills** — All AI functionality implemented as numbered, documented skills

## Project Structure

```
Gold-Tier/
├── agents/
│   ├── agent-core.md                 # Core agent framework (16-step Gold loop)
│   └── agent-autonomous-employee.md  # Gold agent role definition
├── skills/
│   ├── skill-fs-access.md            # (1) File System Access
│   ├── skill-needs-action-processor.md # (2) Needs Action Processor
│   ├── skill-dashboard-updater.md    # (3) Dashboard Updater
│   ├── skill-approval-request-creator.md # (4) Approval Request Creator
│   ├── skill-logger.md               # (5) Logger
│   ├── skill-plan-creator.md         # (6) Plan Creator
│   ├── skill-linkedin-draft.md       # (7) LinkedIn Draft
│   ├── skill-mcp-email.md            # (8) MCP Email
│   ├── skill-hitl-watcher.md         # (9) HITL Watcher
│   ├── skill-scheduler.md            # (10) Scheduler
│   ├── skill-odoo-mcp.md             # (11) Odoo MCP [Gold]
│   ├── skill-social-integrator.md    # (12) Social Integrator [Gold]
│   ├── skill-weekly-audit.md         # (13) Weekly Audit [Gold]
│   ├── skill-ceo-briefing.md         # (14) CEO Briefing [Gold]
│   ├── skill-error-recovery.md       # (15) Error Recovery [Gold]
│   ├── skill-audit-logger.md         # (16) Audit Logger [Gold]
│   ├── skill-ralph-advanced.md       # (17) Ralph Advanced [Gold]
│   ├── skill-doc-generator.md        # (18) Doc Generator [Gold]
│   └── (detailed PascalCase versions of each)
├── watcher/
│   ├── gmail_watcher.py              # Gmail API polling watcher
│   ├── needs_action_watcher.py       # Filesystem watcher + agent trigger with claim-by-move
│   ├── hitl_watcher.py               # Approved/ file watcher
│   ├── scheduler.py                  # Time-based task scheduler
│   ├── facebook_watcher.py           # Facebook feed monitoring with claim-by-move [Gold]
│   ├── instagram_watcher.py          # Instagram feed monitoring with claim-by-move [Gold]
│   └── x_watcher.py                  # X/Twitter feed monitoring with claim-by-move [Gold]
├── mcp-servers/
│   ├── email-mcp/                    # Email MCP (Node.js, nodemailer)
│   │   ├── index.js
│   │   └── package.json
│   ├── odoo-mcp/                     # Odoo MCP (Python, XML-RPC) [Gold]
│   │   ├── odoo_mcp.py
│   │   └── requirements.txt
│   ├── social-mcp/                   # Social MCP (Python, tweepy) [Gold]
│   │   ├── social_mcp.py
│   │   └── requirements.txt
│   ├── social-mcp-fb/                # Facebook MCP (Node.js) [Gold]
│   │   ├── social-mcp-fb.js
│   │   └── package.json
│   ├── social-mcp-ig/                # Instagram MCP (Node.js) [Gold]
│   │   ├── social-mcp-ig.js
│   │   └── package.json
│   └── social-mcp-x/                 # X/Twitter MCP (Node.js) [Gold]
│       ├── social-mcp-x.js
│       └── package.json
├── data/
│   ├── Inbox/                        # Drop-folder for new files
│   ├── Needs_Action/                 # Items awaiting processing
│   ├── Pending_Approval/             # Awaiting human approval
│   ├── Approved/                     # Human-approved items
│   ├── Rejected/                     # Human-rejected items
│   ├── Done/                         # Completed tasks
│   ├── Plans/                        # Multi-step execution plans
│   ├── Logs/                         # JSON audit logs
│   ├── Accounting/                   # Odoo records [Gold]
│   ├── Briefings/                    # Audits & CEO briefs [Gold]
│   ├── Docs/                         # Architecture docs [Gold]
│   ├── Quarantine/                   # Failed tasks [Gold]
│   └── In_Progress/                  # Claimed tasks awaiting processing [Gold - claim-by-move]
├── orchestrator.py                   # Central watcher supervisor [Gold]
├── watchdog.py                       # Process health monitor with auto-restart [Gold]
├── retry_handler.py                  # Error classification and retry logic [Gold]
├── audit_logger.py                   # Centralized structured logging [Gold]
├── Company_Handbook.md               # Rules + policies (Bronze/Silver/Gold)
├── CLAUDE.md                         # Claude Code project context
├── .env                              # Secrets (not committed)
├── .gitignore                        # Excludes secrets & generated files
├── requirements.txt                  # Python dependencies
└── README.md                         # This file
```

## Prerequisites

| Component     | Requirement                                |
|---------------|--------------------------------------------|
| Claude Code   | Active subscription (Pro or Router)        |
| Obsidian      | v1.10.6+ (free)                            |
| Python        | 3.13 or higher                             |
| Node.js       | v24+ LTS                                   |
| Git           | Latest stable                              |
| Odoo Community| 19+ (local, for accounting — optional)     |

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Gold-Tier
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Node.js Dependencies (Email MCP)

```bash
cd mcp-servers/email-mcp && npm install && cd ../..
```

### 4. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# Gmail OAuth2 credentials
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret

# LinkedIn (Silver)
LINKEDIN_ACCESS_TOKEN=your_token

# MCP Email (Silver)
MCP_EMAIL_SERVER=smtp.gmail.com
MCP_EMAIL_PORT=587
MCP_EMAIL_ADDRESS=your_email@gmail.com
MCP_EMAIL_APP_PASSWORD=your_app_password

# Odoo (Gold)
ODOO_URL=http://localhost:8069
ODOO_DB=ai_employee
ODOO_USERNAME=admin
ODOO_PASSWORD=admin
ODOO_DRY_RUN=true

# Facebook/Instagram (Gold)
FB_PAGE_ID=your_page_id
FB_ACCESS_TOKEN=your_fb_access_token
IG_BUSINESS_ACCOUNT_ID=your_ig_account_id
FB_DRY_RUN=true

# Twitter/X (Gold)
X_API_KEY=your_api_key
X_API_SECRET=your_api_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_SECRET=your_access_secret
X_BEARER_TOKEN=your_bearer_token
X_DRY_RUN=true
```

### 5. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to the project root
5. Run the Gmail watcher once to complete OAuth flow and generate `token.json`

### 6. Set Up Odoo Community (Optional)

1. Install Odoo Community Edition 19+
2. Create a database named `ai_employee`
3. Configure accounting modules (Invoicing, Accounting)
4. Set `ODOO_DRY_RUN=false` when ready for live integration

### 7. Open in Obsidian

1. Open Obsidian
2. Select "Open folder as vault"
3. Point to the `Gold-Tier/` directory
4. `data/Dashboard.md` is your main status page

### 8. Start the System

```bash
# Option A: Start the orchestrator (manages all watchers)
python orchestrator.py

# Option B: Start watchers individually
python watcher/gmail_watcher.py          # Terminal 1
python watcher/needs_action_watcher.py   # Terminal 2
python watcher/hitl_watcher.py           # Terminal 3
python watcher/scheduler.py              # Terminal 4

# Test MCP servers in dry-run mode
python mcp-servers/odoo-mcp/odoo_mcp.py --test
python mcp-servers/social-mcp/social_mcp.py --test
```

## How It Works

1. **Gmail Watcher** polls for new emails → creates `.md` files in `data/Needs_Action/`
2. **Filesystem Watcher** detects new files → triggers Claude Code (16-step Ralph Wiggum Gold loop)
3. **Claude Code** reads the task, applies Company Handbook rules (Bronze + Silver + Gold), and either:
   - Processes it directly → moves to `data/Done/`
   - Creates a multi-step plan → `data/Plans/`
   - Creates an approval request → `data/Pending_Approval/`
   - Routes to Odoo MCP for accounting → `data/Accounting/`
   - Routes to Social MCP for posting → requires HITL approval
4. **Human** reviews approval requests and moves to `data/Approved/` or `data/Rejected/`
5. **HITL Watcher** detects approved files → triggers Claude to route by `action` field and execute
6. **Scheduler** creates recurring task files at configured times → feeds into step 2
7. **Weekly Audit** runs on schedule → generates `AUDIT_{date}.md` in `data/Briefings/`
8. **CEO Briefing** summarizes audit data → generates `CEO_BRIEF_{date}.md`
9. **Error Recovery** retries failures, quarantines permanently broken tasks
10. **Dashboard** is updated with current counts, plans, and system health
11. **Logs** are written as enhanced JSON with severity, correlation IDs, and timing

## Security

- All credentials stored in `.env` (excluded from git via `.gitignore`)
- `credentials.json` and `token.json` are gitignored
- Human-in-the-loop for all sensitive actions (emails, social posts, invoices)
- DRY_RUN mode for all external integrations — enabled by default
- PII handling: email bodies truncated in logs, passwords never logged
- Financial data restricted from social media content
