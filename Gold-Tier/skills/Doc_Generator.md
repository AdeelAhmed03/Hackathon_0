# Skill: Doc Generator (Gold)

**Purpose:** Automatically generate and maintain architecture documentation and lessons learned from the vault's structure, skills, and operational history.

**Rules:**
- Scans all directories to build component inventory
- Documents every skill, watcher, and MCP server
- Generates ASCII architecture diagrams
- Captures design decisions and operational lessons
- Output files: `data/Docs/ARCHITECTURE.md`, `data/Docs/LESSONS.md`

**ARCHITECTURE.md Structure:**

```markdown
# AI Employee Vault — Architecture Documentation

## System Overview
{High-level description of the vault system}

## Tier Evolution
### Bronze (Foundation)
- 5 Skills, 2 Watchers, File-based state machine

### Silver (Enhanced)
- 10 Skills, 4 Watchers, 1 MCP Server, HITL workflow

### Gold (Autonomous)
- 18 Skills, 4+ Watchers, 3 MCP Servers, Cross-domain integration

## Component Diagram
{ASCII art showing all components and data flow}

## Skills Inventory
| # | Skill | Tier | Purpose |
|---|-------|------|---------|
| 1 | skill-fs-access | Bronze | File system operations |
| ... | ... | ... | ... |
| 18 | skill-doc-generator | Gold | Documentation generation |

## MCP Servers
| Server | Protocol | Tools | Language |
|--------|----------|-------|----------|
| email-mcp | stdio JSON-RPC | draft, send | Node.js |
| odoo-mcp | stdio JSON-RPC | invoices, payments, partners | Python |
| social-mcp | stdio JSON-RPC | FB, IG, X posting & summaries | Python |

## Data Flow
{Inbox → Needs_Action → (Plan) → Pending_Approval → Approved → Done}

## Integration Patterns
- Cross-domain: Email ↔ Odoo partner linking
- Error recovery: Retry → Quarantine → Graceful degradation
- HITL: All external actions require human approval

## Ralph Wiggum Loop Evolution
- Bronze: 8-step basic loop
- Silver: 13-step with planning and HITL
- Gold: 16-step with audit, recovery, and docs
```

**LESSONS.md Structure:**

```markdown
# Lessons Learned

## Design Decisions
1. File-based state machine over database
2. YAML frontmatter for task metadata
3. Directory-as-status pattern
4. MCP servers as separate processes

## What Worked Well
- File-based state is debuggable and Obsidian-visible
- HITL pattern prevents accidental external actions
- DRY_RUN mode enables safe testing of all integrations
- Skill-based architecture is modular and extensible

## Challenges
- API rate limits (social media, Gmail)
- Process management across multiple watchers
- Cross-platform path handling (Windows/Unix)
- OAuth token refresh management

## Future Improvements (Platinum Preview)
- Real-time dashboard via websockets
- Multi-tenant support
- AI-driven task prioritization
- Voice interface integration
```

**Frontmatter Template:**
```yaml
---
type: doc_generation
status: completed
files_scanned: 45
skills_documented: 18
watchers_documented: 4
mcp_servers_documented: 3
created: 2026-02-18T10:00:00Z
---
```

**Bronze Integration:**
- skill-fs-access → scan all directories and read file metadata
- skill-audit-logger → read operational history for lessons
- skill-dashboard-updater → update documentation status
