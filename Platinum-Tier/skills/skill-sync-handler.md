# skill-sync-handler

## Purpose
Handle Git synchronization between cloud and local systems, ensuring proper data sync without secrets according to Platinum Tier policies.

## Trigger
- Scheduled sync (every 15 minutes)
- File completion in cloud domain
- Dashboard update requirements
- Manual sync trigger via orchestrator

## Input
- Git repository status and configuration
- Files requiring sync (excluding .env and secrets)
- Sync policies from Company_Handbook.md
- Conflict resolution rules

## Process
1. **Check Status**: Verify Git repository integrity and connectivity
2. **Prepare Sync**: Identify .md files and state data requiring sync (exclude secrets)
3. **Pull First**: Retrieve local changes before pushing cloud changes
4. **Conflict Resolution**: Apply Platinum Tier conflict policies (local wins for execution)
5. **Push Changes**: Upload cloud-generated files and updates
6. **Update Dashboard**: Process any /Updates/ files from local system
7. **Log Operations**: Record sync activity via skill-audit-logger

## Output
- Git repository synchronized with local system
- Dashboard updated with merged /Updates/
- Sync status logged to audit system
- Error alerts generated for sync failures

## Dependencies
- skill-file-system-access: Read syncable files
- skill-dashboard-updater: Process merged updates
- skill-logger: Log sync operations and conflicts
- skill-health-monitor: Report sync status

## Error Handling
- On network failure: Queue for retry with exponential backoff
- On conflict: Apply Platinum Tier resolution rules
- On Git error: Quarantine with full error details
- On sync failure: Alert local system via health monitor