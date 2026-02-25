# Sync_Handler

## Extended Skill Definition

### Overview
Sync_Handler manages Git-based synchronization between cloud and local systems, ensuring data consistency while maintaining security through Platinum Tier sync policies. This skill handles the critical task of keeping distributed vaults in sync without compromising security.

### Detailed Process Flow

#### Step 1: Sync Readiness Check
- Verify Git repository is accessible and not locked by another process
- Check network connectivity to remote repository
- Validate repository integrity using Git status commands
- Confirm configuration settings and sync policies

#### Step 2: File Inventory
- Scan data/ directory for .md files and state data requiring sync
- Apply Platinum Tier sync filters:
  - Include: .md files, state files, logs (structured), updates
  - Exclude: .env files, credentials, session data, secrets
- Generate file manifest with timestamps and checksums
- Identify any files pending sync from previous cycles

#### Step 3: Conflict Detection
- Pull latest changes from remote repository
- Compare local and remote versions of each file
- Identify potential conflicts based on Platinum Tier rules:
  - Local updates take precedence for execution decisions
  - Cloud updates take precedence for cloud-specific data
  - Timestamp-based resolution for concurrent edits
- Prepare conflict resolution plan

#### Step 4: Sync Execution
- Apply conflict resolution decisions
- Push cloud-generated updates to remote repository
- Handle any merge conflicts according to Platinum Tier policies
- Verify successful sync completion

#### Step 5: Dashboard Update
- Process any incoming /Updates/ files from local system
- Update Dashboard.md with merged information
- Log sync activity and any issues encountered
- Reset sync status indicators

### Sync Policies

#### Security-First Approach
- **Never sync secrets**: .env, token files, credentials
- **Validate file types**: Only .md and state-related files
- **Audit trail**: Log all sync activity for security review
- **Access controls**: Verify repository permissions before sync

#### Platinum Tier Conflict Resolution
- **Execution decisions**: Local system takes precedence
- **Cloud-specific data**: Cloud updates take precedence
- **Concurrent edits**: Timestamp-based resolution with notification
- **Policy compliance**: Follow Platinum Tier work-zone separation

#### Data Integrity
- **Checksum validation**: Verify file integrity during sync
- **Backup**: Maintain previous versions of sync'd files
- **Rollback capability**: Revert to previous state if sync fails
- **Consistency checks**: Validate data structure post-sync

### Examples

#### Example Sync Cycle
**Time**: 2026-02-21T16:15:00Z
**Action**: Scheduled sync execution

**Step 1**: Readiness check passes - Git repo accessible
**Step 2**: File inventory identifies:
- 5 cloud-generated task files in data/Plans/cloud/
- 3 cloud updates in data/Updates/
- 2 local updates in remote repository pending merge
**Step 3**: Conflict detection finds no conflicts
**Step 4**: Sync executes successfully
**Step 5**: Dashboard updated with merged local updates

**Log Entry**:
```
{
  "timestamp": "2026-02-21T16:15:30Z",
  "action": "git_sync",
  "actor": "sync_handler",
  "files_synced": 10,
  "conflicts": 0,
  "result": "success",
  "duration_ms": 2450,
  "correlation_id": "sync_20260221_161530"
}
```

### Error Handling Scenarios

#### Network Failure
- **Issue**: Cannot connect to remote repository
- **Action**: Queue sync for retry with exponential backoff (2s, 4s, 8s)
- **Log**: Track connection failures for network monitoring

#### Git Repository Error
- **Issue**: Repository corruption or lock detected
- **Action**: Attempt repository recovery, alert health monitor
- **Log**: Record repository state for troubleshooting

#### Conflict Resolution Failure
- **Issue**: Unable to resolve file conflicts automatically
- **Action**: Flag for manual resolution, pause sync until resolved
- **Log**: Document conflict details and proposed resolution

#### Sync Policy Violation
- **Issue**: File marked for sync violates Platinum Tier policies
- **Action**: Exclude file from sync, log security alert
- **Log**: Record policy violation for security review

### Performance Metrics
- **Sync frequency**: Target every 15 minutes or on demand
- **Sync completion time**: Target < 5 seconds for normal operations
- **Conflict rate**: Target < 1% of sync operations
- **Data integrity**: Target > 99.9% successful sync rate
- **Security compliance**: Target 100% policy adherence

### Integration Points
- **Dashboard**: Updates with merged information from local system
- **Health Monitor**: Reports sync status and any failures
- **Audit Logger**: Records all sync operations and conflicts
- **File System**: Manages file selection and validation for sync
- **Cloud Executive**: Provides sync completion notifications

### Automation & Scheduling
- **Automatic sync**: Every 15 minutes during normal operation
- **Event-driven sync**: On task completion in cloud domain
- **Manual sync**: Available via orchestrator commands
- **Conditional sync**: Skip if no changes detected to optimize performance