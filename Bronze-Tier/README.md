# AI Employee Vault - Bronze Tier

> Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0
> **Tier:** Bronze (Foundation)

## What Is This?

A local-first, agent-driven AI Employee that monitors your Gmail, processes incoming tasks, and manages a file-based workflow — all powered by **Claude Code** as the reasoning engine and an **Obsidian-compatible Markdown vault** as the dashboard.

The AI doesn't just wait for commands — it watches for new emails and files, reasons about what to do, creates plans, and requests human approval for sensitive actions.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  EXTERNAL SOURCES                     │
│         Gmail API        │       Local Files          │
└────────────┬─────────────┴──────────────┬─────────────┘
             │                            │
             ▼                            ▼
┌──────────────────────────────────────────────────────┐
│               PERCEPTION LAYER (Watchers)             │
│    gmail_watcher.py      │   needs_action_watcher.py  │
└────────────┬─────────────┴──────────────┬─────────────┘
             │    Creates .md files in     │
             ▼    data/Needs_Action/       ▼
┌──────────────────────────────────────────────────────┐
│              OBSIDIAN VAULT (Local Markdown)           │
│  /Inbox → /Needs_Action → /Pending_Approval → /Done  │
│  Dashboard.md  │  Company_Handbook.md  │  Logs/       │
└──────────────────────────┬───────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────┐
│             REASONING LAYER (Claude Code)             │
│     Ralph Wiggum Loop: Read → Think → Plan → Act     │
│              5 Agent Skills (Markdown)                 │
└──────────────────────────────────────────────────────┘
```

## Features (Bronze Tier)

- **Gmail Watcher** — Polls Gmail every 120s for unread/important emails, creates structured Markdown task files
- **Filesystem Watcher** — Monitors `data/Needs_Action/` and `data/Inbox/` for new `.md` files, triggers Claude Code agent
- **Agent Skills** — 5 Markdown-defined skills: File System Access, Needs Action Processor, Dashboard Updater, Approval Request Creator, Logger
- **File-Based State Machine** — Directories represent workflow states (Inbox → Needs_Action → Pending_Approval → Done)
- **Human-in-the-Loop** — Sensitive actions require approval (move file to Approved/Rejected)
- **Dashboard** — Real-time status overview in `data/Dashboard.md`
- **Audit Logging** — Structured JSON logs in `data/Logs/`

## Project Structure

```
Bronze-Tier/
├── agents/
│   └── agent-core.md              # Core agent framework
├── skills/
│   ├── skill-fs-access.md         # File System Access skill
│   ├── skill-needs-action-processor.md
│   ├── skill-dashboard-updater.md
│   ├── skill-approval-request-creator.md
│   ├── skill-logger.md
│   └── (detailed versions of each)
├── watcher/
│   ├── gmail_watcher.py           # Gmail API polling watcher
│   └── needs_action_watcher.py    # Filesystem watcher + agent trigger
├── data/
│   ├── Inbox/                     # Drop-folder for new files
│   ├── Needs_Action/              # Items awaiting processing
│   ├── Pending_Approval/          # Awaiting human approval
│   ├── Approved/                  # Human-approved items
│   ├── Rejected/                  # Human-rejected items
│   ├── Done/                      # Completed tasks
│   ├── Logs/                      # JSON audit logs
│   └── Dashboard.md               # Live status dashboard
├── Company_Handbook.md            # Rules of engagement
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
cd Bronze-Tier
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the `.env` file and fill in your real credentials:

```bash
# Edit .env with your actual Gmail OAuth2 credentials
# GMAIL_CLIENT_ID=your_client_id
# GMAIL_CLIENT_SECRET=your_client_secret
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
3. Point to the `Bronze-Tier/` directory
4. `data/Dashboard.md` is your main status page

### 6. Start the Watchers

```bash
# Terminal 1: Start Gmail watcher
python watcher/gmail_watcher.py

# Terminal 2: Start filesystem watcher
python watcher/needs_action_watcher.py

# Or with dry-run mode for safe testing:
python watcher/needs_action_watcher.py --dry-run
```

## How It Works

1. **Gmail Watcher** polls for new emails → creates `.md` files in `data/Needs_Action/`
2. **Filesystem Watcher** detects new files → triggers Claude Code (Ralph Wiggum loop)
3. **Claude Code** reads the task, applies Company Handbook rules, and either:
   - Processes it directly → moves to `data/Done/`
   - Creates an approval request → moves to `data/Pending_Approval/`
4. **Human** reviews approval requests and moves to `data/Approved/` or `data/Rejected/`
5. **Dashboard** is updated with current counts and recent activity
6. **Logs** are written as structured JSON for audit trail

## Security

- All credentials stored in `.env` (excluded from git via `.gitignore`)
- `credentials.json` and `token.json` are gitignored
- Human-in-the-loop for all sensitive actions (emails, payments)
- `DRY_RUN=true` mode for safe testing
- Agent restricted to project directory only

## Hackathon Tier Declaration

**Bronze Tier: Foundation (Minimum Viable Deliverable)**

| Requirement | Status |
|-------------|--------|
| Obsidian vault with Dashboard.md and Company_Handbook.md | Done |
| One working Watcher script (Gmail OR filesystem) | Done (both) |
| Claude Code reading from and writing to the vault | Done |
| Basic folder structure: /Inbox, /Needs_Action, /Done | Done |
| All AI functionality as Agent Skills | Done (5 skills) |

## Tech Stack

- **Python 3.13+** — Watcher scripts
- **Claude Code** — AI reasoning engine (Ralph Wiggum loop)
- **Obsidian** — Knowledge base & dashboard (local Markdown)
- **Google Gmail API** — Email ingestion
- **watchdog** — Filesystem event monitoring
- **Markdown + YAML frontmatter** — Data format for all tasks and configs
