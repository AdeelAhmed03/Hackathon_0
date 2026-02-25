# AI Employee Vault - Silver Tier

> Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0
> **Tier:** Silver (Enhanced)

## What Is This?

A local-first, agent-driven AI Employee that monitors your Gmail, processes incoming tasks, and manages a file-based workflow — all powered by **Claude Code** as the reasoning engine and an **Obsidian-compatible Markdown vault** as the dashboard.

The AI doesn't just wait for commands — it watches for new emails and files, reasons about what to do, creates multi-step plans, generates LinkedIn drafts, sends emails via SMTP, and requests human approval for sensitive actions. Silver Tier adds scheduled automation, HITL approval routing, and structured planning.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  EXTERNAL SOURCES                     │
│    Gmail API    │   Local Files   │   LinkedIn API    │
└───────┬─────────┴────────┬────────┴────────┬─────────┘
        │                  │                 │
        ▼                  ▼                 ▼
┌──────────────────────────────────────────────────────┐
│              PERCEPTION LAYER (Watchers)              │
│  gmail_watcher.py │ needs_action_watcher.py          │
│  hitl_watcher.py  │ scheduler.py                     │
└───────┬───────────┴──────────┬───────────────────────┘
        │  Creates .md files   │
        ▼  in data/ dirs       ▼
┌──────────────────────────────────────────────────────┐
│              OBSIDIAN VAULT (Local Markdown)          │
│  /Inbox → /Needs_Action → /Pending_Approval → /Done │
│  /Plans  │  Dashboard.md  │  Company_Handbook.md     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│             REASONING LAYER (Claude Code)             │
│   Ralph Wiggum Loop: 13-Step Silver Processing       │
│        10 Agent Skills (5 Bronze + 5 Silver)         │
└──────────────────────────────────────────────────────┘
```

## Features (Silver Tier)

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

## Project Structure

```
Silver-Tier/
├── agents/
│   └── agent-core.md              # Core agent framework (13-step Silver loop)
├── skills/
│   ├── skill-fs-access.md         # File System Access skill
│   ├── skill-needs-action-processor.md
│   ├── skill-dashboard-updater.md
│   ├── skill-approval-request-creator.md
│   ├── skill-logger.md
│   ├── skill-plan-creator.md      # (Silver) Plan Creator
│   ├── skill-linkedin-draft.md    # (Silver) LinkedIn Draft
│   ├── skill-mcp-email.md         # (Silver) MCP Email
│   ├── skill-hitl-watcher.md      # (Silver) HITL Watcher
│   ├── skill-scheduler.md         # (Silver) Scheduler
│   └── (detailed PascalCase versions of each)
├── watcher/
│   ├── gmail_watcher.py           # Gmail API polling watcher
│   ├── needs_action_watcher.py    # Filesystem watcher + agent trigger
│   ├── hitl_watcher.py            # (Silver) Approved/ file watcher
│   └── scheduler.py               # (Silver) Time-based task scheduler
├── data/
│   ├── Inbox/                     # Drop-folder for new files
│   ├── Needs_Action/              # Items awaiting processing
│   ├── Pending_Approval/          # Awaiting human approval
│   ├── Approved/                  # Human-approved items
│   ├── Rejected/                  # Human-rejected items
│   ├── Done/                      # Completed tasks
│   ├── Plans/                     # (Silver) Multi-step execution plans
│   ├── Logs/                      # JSON audit logs
│   └── Dashboard.md               # Live status dashboard
├── Company_Handbook.md            # Rules of engagement + Silver policies
├── CLAUDE.md                      # Claude Code project context
├── .env                           # Secrets (not committed)
├── .gitignore                     # Excludes secrets & generated files
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Prerequisites

| Component     | Requirement                         |
|---------------|-------------------------------------|
| Claude Code   | Active subscription (Pro or Router) |
| Obsidian      | v1.10.6+ (free)                     |
| Python        | 3.13 or higher                      |
| Node.js       | v24+ LTS                            |
| Git           | Latest stable                       |

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Silver-Tier
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Edit `.env` with your credentials:

```bash
# Gmail OAuth2 credentials
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret

# LinkedIn (Silver)
LINKEDIN_ACCESS_TOKEN=your_token
LINKEDIN_PERSON_URN=urn:li:person:your_id

# MCP Email (Silver)
MCP_EMAIL_SERVER=smtp.gmail.com
MCP_EMAIL_PORT=587
MCP_EMAIL_ADDRESS=your_email@gmail.com
MCP_EMAIL_APP_PASSWORD=your_app_password
```

### 4. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to the project root
5. Run the Gmail watcher once to complete OAuth flow and generate `token.json`

### 5. Open in Obsidian

1. Open Obsidian
2. Select "Open folder as vault"
3. Point to the `Silver-Tier/` directory
4. `data/Dashboard.md` is your main status page

### 6. Start the Watchers

```bash
# Terminal 1: Start Gmail watcher
python watcher/gmail_watcher.py

# Terminal 2: Start filesystem watcher
python watcher/needs_action_watcher.py

# Terminal 3: Start HITL watcher (Silver)
python watcher/hitl_watcher.py

# Terminal 4: Start scheduler (Silver)
python watcher/scheduler.py

# Or with dry-run mode for safe testing:
python watcher/hitl_watcher.py --dry-run
python watcher/scheduler.py --dry-run
python watcher/scheduler.py --dry-run --force-trigger linkedin_draft
```

## How It Works

1. **Gmail Watcher** polls for new emails → creates `.md` files in `data/Needs_Action/`
2. **Filesystem Watcher** detects new files → triggers Claude Code (Ralph Wiggum loop)
3. **Claude Code** reads the task, applies Company Handbook rules, creates plans for multi-step tasks, and either:
   - Processes it directly → moves to `data/Done/`
   - Creates an approval request → moves to `data/Pending_Approval/`
4. **Human** reviews approval requests and moves to `data/Approved/` or `data/Rejected/`
5. **HITL Watcher** detects approved files → triggers Claude to route by `action` field and execute
6. **Scheduler** creates recurring task files at configured times → feeds into step 2
7. **Dashboard** is updated with current counts, plans, and scheduled task status
8. **Logs** are written as structured JSON for audit trail

## Security

- All credentials stored in `.env` (excluded from git via `.gitignore`)
- `credentials.json` and `token.json` are gitignored
- Human-in-the-loop for all sensitive actions (emails, LinkedIn posts)
- Agent NEVER self-approves — only humans move files to `data/Approved/`
- `DRY_RUN=true` mode for safe testing across all watchers
- `LINKEDIN_DRY_RUN` and `MCP_EMAIL_DRY_RUN` for individual feature testing
- Agent restricted to project directory only

## Hackathon Tier Declaration

**Silver Tier: Enhanced**

| Requirement | Status |
|-------------|--------|
| All Bronze requirements | Done |
| Multi-step Plans (data/Plans/) | Done |
| LinkedIn Draft skill with HITL | Done |
| MCP Email skill with HITL | Done |
| HITL Watcher for approval routing | Done |
| Scheduler for recurring tasks | Done |
| 10 Agent Skills (5 Bronze + 5 Silver) | Done |
| Enhanced 13-step agent loop | Done |

## Tech Stack

- **Python 3.13+** — Watcher scripts
- **Claude Code** — AI reasoning engine (Ralph Wiggum loop)
- **Obsidian** — Knowledge base & dashboard (local Markdown)
- **Google Gmail API** — Email ingestion
- **watchdog** — Filesystem event monitoring
- **schedule** — Time-based task scheduling
- **python-dotenv** — Environment variable management
- **SMTP (smtplib)** — Email sending via MCP Email skill
- **Markdown + YAML frontmatter** — Data format for all tasks and configs
