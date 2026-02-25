# skill-cloud-triage

## Purpose
Triage incoming cloud tasks and route appropriately based on priority, type, and required action. Categorizes tasks for the Cloud Executive agent according to Platinum work-zone policies.

## Trigger
- New files in data/Needs_Action/cloud/
- Scheduled re-processing of unclaimed cloud tasks
- Manual trigger via cloud orchestrator

## Input
- Task file with YAML frontmatter containing: type, priority, source, content
- Current system state (Dashboard.md, other claimed tasks)
- Platinum Tier Company Handbook policies

## Process
1. **Read Task**: Parse YAML frontmatter and content
2. **Categorize**: Classify by task type (email, social, accounting, health, sync)
3. **Prioritize**: Apply Platinum Tier priority rules (critical/4h/24h)
4. **Route**: Determine appropriate handler based on type and complexity
5. **Claim**: Move to In_Progress/cloud/ if not already claimed
6. **Queue**: Add to processing queue for appropriate skill

## Output
- Claimed task moved to data/In_Progress/cloud/
- Processing queue updated with categorized task
- Dashboard updated with task status
- Logs updated via skill-audit-logger

## Dependencies
- skill-file-system-access: Read/write/move files
- skill-dashboard-updater: Update processing status
- skill-logger: Log triage decisions
- Company_Handbook.md: Platinum Tier policies

## Error Handling
- On unparseable task: Move to Quarantine with error details
- On conflicting claims: Verify ownership before proceeding
- On policy violation: Flag for human review