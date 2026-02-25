# Merge_Updater

## Extended Skill Definition

### Overview
Merge_Updater handles the critical task of merging cloud-generated updates from the `/Updates/` directory into the local `Dashboard.md` file. This skill maintains the single-writer principle while ensuring both cloud and local system metrics are properly consolidated in the dashboard.

### Detailed Process Flow

#### Step 1: Update File Discovery
- Scan `/Updates/` directory for new update files (typically named `cloud_{id}.md`)
- Filter files by type and validate update file format
- Sort update files by timestamp if multiple updates exist
- Check for any previously unprocessed update files

#### Step 2: Update Content Parsing
- Read each update file and parse YAML frontmatter if present
- Extract update metrics, counts, and activity data
- Validate update structure and data integrity
- Identify the type of data to be merged (cloud metrics, activity logs, etc.)

#### Step 3: Current Dashboard Analysis
- Read current `Dashboard.md` content
- Parse existing metrics and counters
- Identify sections that may be updated by cloud data
- Preserve local-only metrics and data

#### Step 4: Merge Strategy Determination
Based on Platinum Tier policies:
- **Cloud metrics**: Add to existing cloud counters in dashboard
- **Activity logs**: Append cloud activities to existing log
- **System health**: Update cloud system health status
- **Workload metrics**: Merge with local workload metrics
- **Conflict resolution**: Handle any overlapping data according to policy

#### Step 5: Dashboard Update Construction
- Construct updated dashboard content by merging cloud data
- Maintain existing local metrics and preserve local data
- Format new content according to dashboard standards
- Ensure data consistency and formatting integrity

#### Step 6: Single-Writer Update
- Apply single-writer principle: atomic update to `Dashboard.md`
- Use file locking if available to prevent concurrent updates
- Validate dashboard format after update
- Ensure no data loss during merge operation

#### Step 7: Update Completion
- Move processed update files to `/Done/local/` directory
- Log the merge operation in audit logs
- Update internal state to reflect successful merge
- Prepare for next update cycle

### Merge Categories

#### Cloud Task Metrics
- **Source**: Cloud system task completion counts
- **Merge**: Add to existing cloud task counters
- **Example**: Cloud email drafts processed, social drafts created
- **Policy**: Accumulate cloud metrics with local metrics

#### Cloud System Health
- **Source**: Cloud system heartbeat and health reports
- **Merge**: Update cloud system status in dashboard
- **Example**: Cloud service uptime, response times
- **Policy**: Replace cloud health data with latest

#### Cloud Activity Logs
- **Source**: Cloud system activity and processing logs
- **Merge**: Append to existing activity log section
- **Example**: Cloud processing timestamps, actions taken
- **Policy**: Append chronological activities

#### Performance Metrics
- **Source**: Cloud performance and efficiency data
- **Merge**: Combine with local performance data
- **Example**: Cloud processing speed, resource usage
- **Policy**: Aggregate performance data appropriately

### Examples

#### Example Dashboard Update
**Input Update File** (`Updates/cloud_20260221_1645.md`):
```yaml
---
type: dashboard_update
source: cloud_executive
timestamp: 2026-02-21T16:45:00Z
---
## Cloud System Update

**Cloud Tasks Processed**: 12
**Email Drafts Generated**: 5
**Social Drafts Created**: 3
**Odoo Drafts Prepared**: 4
**Cloud System Status**: Operational
**Errors Encountered**: 0
**Sync Operations**: 2
```

**Current Dashboard.md**:
```
# Dashboard - Local System

## Task Counts
- Local Tasks: 25
- Cloud Tasks: 8
- Total Tasks: 33

## System Health
- Local Status: Operational
- Cloud Status: Unknown

## Recent Activity
- Local processing: 2026-02-21 16:30
```

**Processing**:
1. Parse update file and extract cloud metrics
2. Update cloud task count from 8 to 20 (8 + 12)
3. Update cloud system status to Operational
4. Append activity timestamp to activity log

**Output Dashboard.md**:
```
# Dashboard - Local System

## Task Counts
- Local Tasks: 25
- Cloud Tasks: 20  # Updated from 8 to 20
- Total Tasks: 45

## System Health
- Local Status: Operational
- Cloud Status: Operational  # Updated from Unknown

## Recent Activity
- Local processing: 2026-02-21 16:30
- Cloud update: 2026-02-21 16:45  # Added from update
```

### Error Handling Scenarios

#### Dashboard File Lock
- **Issue**: `Dashboard.md` is locked by another process
- **Action**: Wait with timeout, then retry or queue for later
- **Log**: Record blocking process if possible
- **Retry**: Poll every 1 second for up to 10 seconds

#### Update File Corruption
- **Issue**: Update file format is invalid or corrupted
- **Action**: Move to error queue, log error, continue with other updates
- **Log**: Record corruption details for troubleshooting
- **Status**: Continue processing other valid updates

#### Merge Conflict
- **Issue**: Cloud data conflicts with local data in incompatible way
- **Action**: Apply Platinum Tier conflict resolution policy
- **Log**: Record conflict and resolution method
- **Status**: Continue with best-effort merge

#### Update Processing Failure
- **Issue**: Error during dashboard update process
- **Action**: Preserve original dashboard, mark update as failed
- **Log**: Record full error details for debugging
- **Retry**: Queue for retry with exponential backoff

### Integration Points
- **Dashboard**: Single-writer update to main dashboard file
- **Audit Logger**: Log all merge operations and metrics
- **File System**: Manage update files in `/Updates/` and `/Done/local/`
- **Cloud Executive**: Receive updates from cloud system for merging
- **Sync Handler**: Coordinate with Git synchronization for consistency

### Performance Considerations
- **Efficiency**: Minimize dashboard read/write operations
- **Atomicity**: Ensure dashboard updates are atomic to prevent corruption
- **Concurrency**: Handle multiple updates in proper order
- **Validation**: Verify dashboard integrity after each update