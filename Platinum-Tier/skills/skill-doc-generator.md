# Skill: Doc Generator (Gold)

## Purpose
Document architecture + lessons.

## Trigger
- On-demand via manual task file
- End-of-session documentation update
- After significant vault changes (new skills, watchers, MCP servers)

## Rules
- Scan vault structure: agents/, skills/, watcher/, mcp-servers/, data/
- Document all skills (1-18) with their dependencies and triggers
- Document all watchers with their watch directories and actions
- Document all MCP servers with their tools and protocols
- Generate data flow diagram (ASCII art)
- Capture lessons learned from operational data and error patterns

## Output
- `/Docs/ARCHITECTURE.md`: ASCII diagram + stack summary (per spec)
- `/Docs/LESSONS.md`: Key learnings, issues fixed

## Gold Spec
- Comprehensive docs + demo video stub (describe)
- Documents all 3 tiers (Bronze → Silver → Gold) evolution
- Includes cross-domain integration patterns
- Captures error recovery patterns and degradation strategies
- Preview of Platinum tier direction

## Prior Integration
- Run at end of setup
- Uses skill-fs-access to scan directory structure
- Uses skill-audit-logger to read operational history
- Dashboard updated with documentation status
