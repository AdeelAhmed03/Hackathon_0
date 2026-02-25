# AI Employee Vault - Platinum Tier

> Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0
> **Tier:** Platinum (Cloud Executive)

## What Is This?

A distributed, agent-driven AI Employee with **cloud/local separation** — the Cloud Executive runs 24/7 on a VM handling email triage, draft generation, and social media drafts, while the Local Executive handles approvals, WhatsApp, banking, and actual execution. Powered by **Claude Code** as the reasoning engine and an **Obsidian-compatible Markdown vault** as the dashboard, synchronized via Git.

Platinum Tier builds on Gold's autonomous employee with: distributed cloud/local operation, Git-synced vault, work-zone separation (cloud drafts vs local execution), 10 additional skills (28 total), cloud health monitoring, A2A Phase 2 messaging, and a 20-step Ralph Wiggum loop.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUD VM (24/7)                                  │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │              CLOUD EXECUTIVE AGENT                              │     │
│  │  orchestrator_cloud.py │ cloud_health_monitor.py               │     │
│  │  cloud_sync_watcher.py │ gmail_watcher.py                      │     │
│  │  Skills 19-23: Triage, Draft, Sync, Health, A2A                │     │
│  │  Draft-Only Rule: NEVER executes sends/posts/payments          │     │
│  └──────────────────────────┬─────────────────────────────────────┘     │
│                              │ Git sync (.md only, no secrets)           │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │   Git / Syncthing Sync Layer     │
              │  data/ only │ no .env │ no tokens│
              └────────────────┼────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────────┐
│                         LOCAL MACHINE                                    │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │              LOCAL EXECUTIVE AGENT                               │     │
│  │  orchestrator_local.py │ local_health_monitor.py                │     │
│  │  local_sync_watcher.py │ hitl_watcher.py │ scheduler.py        │     │
│  │  whatsapp_watcher.py │ linkedin_watcher.py                      │     │
│  │  Skills 24-28: Executor, Merge, Sync, Health, A2A              │     │
│  │  Owns: Credentials, approvals, execution                       │     │
│  └──────────────────────────┬─────────────────────────────────────┘     │
│                              │                                           │
│  ┌──────────────────────────┴─────────────────────────────────────┐     │
│  │                OBSIDIAN VAULT (Synced Markdown)                  │     │
│  │  /Inbox → /Needs_Action/cloud|local → /Pending_Approval/local   │     │
│  │  → /Approved → /Done/cloud|local                                │     │
│  │  /Plans/cloud|local │ /Updates/ │ /In_Progress/cloud|local      │     │
│  │  /Accounting │ /Briefings │ /Quarantine │ /Docs                 │     │
│  │  Dashboard.md (single-writer: local merges cloud /Updates/)     │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                REASONING LAYER (Claude Code)                      │    │
│  │     Ralph Wiggum Loop: 20-Step Platinum Processing               │    │
│  │          28 Agent Skills (5 Bronze + 5 Silver + 8 Gold + 10 Pt) │    │
│  │        --completion-promise "TASK_COMPLETE" (max 20 iterations)   │    │
│  └──────────────────────────┬──────────────────────────────────────┘    │
│                              │                                           │
│  ┌──────────────────────────┴──────────────────────────────────────┐    │
│  │                  ACTION LAYER (MCP Servers)                       │    │
│  │  email-mcp (Node.js)  │  odoo-mcp (Python)  │  social-mcp       │    │
│  │  draft, send           │  invoices, payments  │  FB, IG, X        │    │
│  │  social-mcp-fb │ social-mcp-ig │ social-mcp-x (Node.js)         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
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
- **Social Media MCP Servers** — Facebook, Instagram, Twitter/X posting and engagement summaries (per-platform Node.js servers)
- **Weekly Audit** — Automated business data audit (tasks, accounting, social media, system health)
- **CEO Briefing** — Executive summary generation with KPIs, issues, and recommendations
- **Error Recovery** — Exponential backoff retries, quarantine for permanent failures, graceful degradation
- **Audit Logger** — Enhanced logging with severity levels, correlation IDs, execution timing, error traces
- **Ralph Advanced** — 16-step autonomous loop with file-move completion detection, max 20 iterations
- **Claim-by-Move Pattern** — Files moved to `/In_Progress/{agent}/` to claim ownership
- **Watchdog & Orchestrator** — Central supervisor and process health monitoring with auto-restart
- **6 MCP Servers** — Email, Odoo, Social (Python), Facebook, Instagram, X (Node.js) — all with DRY_RUN support

### Platinum Additions
- **Cloud/Local Separation** — Cloud Executive (24/7 VM) handles triage and drafts; Local Executive handles approvals and execution
- **Draft-Only Policy** — Cloud agent never sends/posts/pays — only creates drafts for local approval
- **Cloud Executive Agent** — Triage engine with priority levels (Critical/High/Normal), routes to draft handlers
- **Local Executive Agent** — Processes approved actions, merges cloud updates, executes via local MCP with local credentials
- **Git Sync Mechanism** — Automatic synchronization of `.md`/state files between cloud and local (no secrets)
- **Syncthing Alternative** — Pre-configured Syncthing XML for non-Git sync setups
- **Cloud Health Monitoring** — psutil-based CPU/memory/disk/network monitoring, service checks, alert generation
- **Local Health Monitoring** — Local system health checks, resource monitoring, dashboard updates
- **Cloud Orchestrator** — 24/7 service supervisor with auto-restart, scheduled health/sync/status
- **Local Orchestrator** — Local service management with heartbeat and scheduled tasks
- **Cloud Sync Watcher** — Git pull/push cycle with 15-minute interval, approved file processing
- **Local Sync Watcher** — Cloud update pulling, processing, local change pushing (10-minute interval)
- **Work-Zone Directories** — `Needs_Action/cloud|local`, `Plans/cloud|local`, `Done/cloud|local`, `In_Progress/cloud|local`, `Updates/`
- **Single-Writer Dashboard** — Cloud writes to `/Updates/`, local merges into `Dashboard.md`
- **A2A Phase 2** — Optional direct agent-to-agent messaging with audit trail (opt-in)
- **Cloud VM Deployment** — Setup scripts for Oracle OCI and AWS (systemd services, PM2 config)
- **Odoo Cloud Deployment** — Docker Compose with PostgreSQL 15, Odoo 19, Nginx HTTPS reverse proxy, backup cron
- **WhatsApp Watcher** — WhatsApp Web monitoring via Playwright (local-only)
- **LinkedIn Watcher** — LinkedIn feed monitoring with OAuth authentication
- **Cloud/Local Watchdogs** — Separate process health monitors for cloud and local systems
- **20-Step Ralph Wiggum Loop** — Platinum-enhanced autonomous processing with cloud/local steps
- **28 Agent Skills** — 5 Bronze + 5 Silver + 8 Gold + 10 Platinum (cloud skills 19-23 + local skills 24-28)

## Project Structure

```
Platinum-Tier/
├── agents/
│   ├── agent-core.md                    # Core agent framework (20-step Platinum loop)
│   ├── agent-cloud-executive.md         # Cloud Executive role definition [Platinum]
│   ├── agent-local-executive.md         # Local Executive role definition [Platinum]
│   ├── agent-local-executive.py         # Local Executive Python implementation [Platinum]
│   ├── agent-autonomous-employee.md     # Gold autonomous employee agent
│   └── agent-functional-assistant.md    # Silver functional assistant agent
├── skills/
│   ├── skill-fs-access.md               # (1) File System Access
│   ├── skill-needs-action-processor.md  # (2) Needs Action Processor
│   ├── skill-dashboard-updater.md       # (3) Dashboard Updater
│   ├── skill-approval-request-creator.md # (4) Approval Request Creator
│   ├── skill-logger.md                  # (5) Logger
│   ├── skill-plan-creator.md            # (6) Plan Creator
│   ├── skill-linkedin-draft.md          # (7) LinkedIn Draft
│   ├── skill-mcp-email.md              # (8) MCP Email
│   ├── skill-hitl-watcher.md            # (9) HITL Watcher
│   ├── skill-scheduler.md               # (10) Scheduler
│   ├── skill-odoo-mcp.md               # (11) Odoo MCP [Gold]
│   ├── skill-social-integrator.md       # (12) Social Integrator [Gold]
│   ├── skill-weekly-audit.md            # (13) Weekly Audit [Gold]
│   ├── skill-ceo-briefing.md            # (14) CEO Briefing [Gold]
│   ├── skill-error-recovery.md          # (15) Error Recovery [Gold]
│   ├── skill-audit-logger.md            # (16) Audit Logger [Gold]
│   ├── skill-ralph-advanced.md          # (17) Ralph Advanced [Gold]
│   ├── skill-doc-generator.md           # (18) Doc Generator [Gold]
│   ├── skill-cloud-triage.md            # (19) Cloud Triage [Platinum]
│   ├── skill-draft-generator.md         # (20) Draft Generator [Platinum]
│   ├── skill-sync-handler.md            # (21) Sync Handler [Platinum]
│   ├── skill-health-monitor.md          # (22) Health Monitor [Platinum]
│   ├── skill-a2a-upgrade.md             # (23) A2A Upgrade [Platinum]
│   ├── skill-approval-executor.md       # (24) Approval Executor [Platinum]
│   ├── skill-merge-updater.md           # (25) Merge Updater [Platinum]
│   └── (detailed PascalCase versions of each + skills 26-28 share 21-23)
├── watcher/
│   ├── gmail_watcher.py                 # Gmail API polling watcher
│   ├── needs_action_watcher.py          # Filesystem watcher + agent trigger
│   ├── hitl_watcher.py                  # Approved/ file watcher
│   ├── scheduler.py                     # Time-based task scheduler
│   ├── facebook_watcher.py              # Facebook feed monitoring [Gold]
│   ├── instagram_watcher.py             # Instagram feed monitoring [Gold]
│   ├── x_watcher.py                     # X/Twitter feed monitoring [Gold]
│   ├── whatsapp_watcher.py              # WhatsApp monitoring via Playwright [Platinum]
│   ├── linkedin_watcher.py              # LinkedIn feed monitoring [Platinum]
│   ├── linkedin_auth.py                 # LinkedIn OAuth authentication [Platinum]
│   ├── cloud_sync_watcher.py            # Git sync for cloud agent [Platinum]
│   ├── local_sync_watcher.py            # Git sync for local agent [Platinum]
│   ├── cloud_health_monitor.py          # Cloud health monitoring [Platinum]
│   ├── local_health_monitor.py          # Local health monitoring [Platinum]
│   ├── orchestrator_cloud.py            # Cloud 24/7 orchestrator [Platinum]
│   └── orchestrator_local.py            # Local orchestrator [Platinum]
├── mcp-servers/
│   ├── email-mcp/                       # Email MCP (Node.js, nodemailer)
│   ├── odoo-mcp/                        # Odoo MCP (Python, JSON-RPC) [Gold]
│   ├── social-mcp/                      # Social MCP (Python, multi-platform) [Gold]
│   ├── social-mcp-fb/                   # Facebook MCP (Node.js) [Gold]
│   ├── social-mcp-ig/                   # Instagram MCP (Node.js) [Gold]
│   └── social-mcp-x/                    # X/Twitter MCP (Node.js) [Gold]
├── data/
│   ├── Inbox/                           # Drop-folder for new files
│   ├── Needs_Action/cloud/              # Cloud-specific items [Platinum]
│   ├── Needs_Action/local/              # Local-specific items [Platinum]
│   ├── Pending_Approval/local/          # Items requiring local human approval [Platinum]
│   ├── Approved/                        # Human-approved items
│   ├── Rejected/                        # Human-rejected items
│   ├── Done/cloud/                      # Cloud-completed tasks [Platinum]
│   ├── Done/local/                      # Local-completed tasks [Platinum]
│   ├── Plans/cloud/                     # Cloud-generated plans [Platinum]
│   ├── Plans/local/                     # Local-generated plans [Platinum]
│   ├── In_Progress/cloud/               # Cloud agent claimed tasks [Platinum]
│   ├── In_Progress/local/               # Local agent claimed tasks [Platinum]
│   ├── Updates/                         # Cloud → local dashboard updates [Platinum]
│   ├── Logs/                            # JSON audit logs
│   ├── Accounting/                      # Odoo records [Gold]
│   ├── Briefings/                       # Audits & CEO briefs [Gold]
│   ├── Docs/                            # Architecture docs [Gold]
│   ├── Quarantine/                      # Failed tasks [Gold]
│   └── Signals/                         # Inter-agent signals [Platinum]
├── orchestrator.py                      # Central watcher supervisor [Gold]
├── watchdog.py                          # Process health monitor [Gold]
├── watchdog_local.py                    # Local watchdog [Platinum]
├── retry_handler.py                     # Error classification and retry [Gold]
├── audit_logger.py                      # Centralized structured logging [Gold]
├── audit_logic.py                       # Audit analysis logic [Platinum]
├── git_sync.py                          # Git synchronization handler [Platinum]
├── test_audit.py                        # Audit tests [Platinum]
├── docker-compose.yml                   # Odoo cloud deployment (Docker) [Platinum]
├── ecosystem.config.js                  # PM2 process manager config [Platinum]
├── syncthing-config.xml                 # Syncthing sync alternative config [Platinum]
├── setup-cloud-vm.sh                    # Cloud VM provisioning script [Platinum]
├── odoo_cloud_deploy.sh                 # Odoo cloud deployment script [Platinum]
├── SETUP-CLOUD-VM.md                    # Cloud VM setup instructions [Platinum]
├── SYNC-RUN-INSTRUCTIONS.md             # Sync setup guide [Platinum]
├── Business_Goals.md                    # KPIs and quarterly targets [Gold]
├── Company_Handbook.md                  # All policies (Bronze → Platinum)
├── CLAUDE.md                            # Claude Code project context
├── .mcp.json                            # Claude Code MCP server config (all 6 servers)
├── mcp.json                             # MCP server template config
├── .env                                 # Secrets (not committed)
├── .gitignore                           # Excludes secrets & generated files
├── requirements.txt                     # Python dependencies
└── README.md                            # This file
```

## Prerequisites

| Component     | Requirement                                |
|---------------|--------------------------------------------|
| Claude Code   | Active subscription (Pro or Router)        |
| Obsidian      | v1.10.6+ (free)                            |
| Python        | 3.13 or higher                             |
| Node.js       | v24+ LTS                                   |
| Git           | Latest stable                              |
| Odoo Community| 19+ (for accounting — optional)            |
| Cloud VM      | Oracle OCI / AWS (for cloud agent)         |
| Docker        | For Odoo cloud deployment (optional)       |

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd Platinum-Tier
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Node.js Dependencies

```bash
cd mcp-servers/email-mcp && npm install && cd ../..
cd mcp-servers/social-mcp-fb && npm install && cd ../..
cd mcp-servers/social-mcp-ig && npm install && cd ../..
cd mcp-servers/social-mcp-x && npm install && cd ../..
```

### 4. Configure Environment Variables

Edit `.env` with your credentials (see `.env` for all available options).

### 5. Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app)
4. Download `credentials.json` to the project root
5. Run the Gmail watcher once to complete OAuth flow and generate `token.json`

### 6. Open in Obsidian

1. Open Obsidian
2. Select "Open folder as vault"
3. Point to the `Platinum-Tier/` directory
4. `data/Dashboard.md` is your main status page

### 7. Start the System (Local)

```bash
# Option A: Start the local orchestrator (manages all local watchers)
python watcher/orchestrator_local.py

# Option B: Start watchers individually
python watcher/gmail_watcher.py          # Terminal 1
python watcher/needs_action_watcher.py   # Terminal 2
python watcher/hitl_watcher.py           # Terminal 3
python watcher/scheduler.py              # Terminal 4

# Start the Local Executive agent
python agents/agent-local-executive.py
```

### 8. Deploy Cloud Agent (Optional)

```bash
# Set up cloud VM (Oracle OCI or AWS)
bash setup-cloud-vm.sh

# Deploy Odoo on cloud (Docker)
bash odoo_cloud_deploy.sh

# See detailed instructions
cat SETUP-CLOUD-VM.md
cat SYNC-RUN-INSTRUCTIONS.md
```

## How It Works

### Cloud Executive (24/7 VM)
1. **Gmail Watcher** polls for new emails → creates `.md` files in `data/Needs_Action/cloud/`
2. **Cloud Triage** categorizes by priority (Critical/High/Normal) and routes to draft handlers
3. **Draft Generator** creates drafts in `data/Plans/cloud/` — email replies, social posts, Odoo actions
4. **Approval files** written to `data/Pending_Approval/local/` for human review
5. **Dashboard updates** written to `data/Updates/` for local merge
6. **Git Sync** pushes changes to remote at completion and every 15 minutes
7. **Health Monitor** tracks cloud health, alerts local on degradation

### Local Executive (Your Machine)
1. **Git Sync** pulls cloud changes to local vault
2. **Local Sync Watcher** processes cloud updates from `data/Updates/`
3. **Human** reviews approval requests, moves to `data/Approved/` or `data/Rejected/`
4. **HITL Watcher** detects approved files → routes by `action` field
5. **Approval Executor** executes actions via local MCP servers with local credentials
6. **Merge Updater** merges cloud updates into `Dashboard.md` (single-writer principle)
7. **Completed tasks** moved to `data/Done/local/`, synced back via Git

### Inherited Workflows (Bronze/Silver/Gold)
- **Scheduler** creates recurring task files at configured times
- **Weekly Audit** runs on schedule → `AUDIT_{date}.md` in `data/Briefings/`
- **CEO Briefing** summarizes audit data → `CEO_BRIEF_{date}.md`
- **Error Recovery** retries failures, quarantines permanently broken tasks
- **Odoo** handles invoices, payments, partner management via JSON-RPC
- **Social Media** posts to FB/IG/X with per-platform MCP servers

## Security

- **No secrets sync** — `.env`, credentials, tokens never leave local machine
- **Cloud .env separated** — Cloud uses `.env.cloud` with limited scope
- **Git sync excludes** — 94-rule `.gitignore` covers all sensitive files
- **Draft-only cloud** — Cloud agent cannot execute sends, posts, or payments
- **Local credential isolation** — Local credentials never accessible to cloud system
- **Human-in-the-loop** — All external actions require human approval
- **DRY_RUN mode** — Enabled by default for all external integrations
- **PII handling** — Email bodies truncated in logs, passwords never logged
- **A2A Phase 2** — Optional and logged for audit compliance
