# Cloud_Triage

## Extended Skill Definition

### Overview
Cloud_Triage is the primary intake handler for the Cloud Executive agent. It evaluates incoming tasks in data/Needs_Action/cloud/ and determines appropriate processing based on Platinum Tier policies. This skill serves as the first decision point for all cloud-based operations.

### Detailed Process Flow

#### Step 1: Task Analysis
- Reads YAML frontmatter from incoming task file
- Identifies task type (email, social, accounting, health, sync, etc.)
- Extracts priority indicators and urgency flags
- Determines required compliance checks based on task type

#### Step 2: Compliance Validation
- Verifies task aligns with Platinum Tier work-zone separation
- Ensures task is appropriate for cloud execution (draft-only operations)
- Checks against Company_Handbook.md policies
- Validates that no local-only operations are requested

#### Step 3: Categorization & Prioritization
- Assigns one of three priority levels:
  - **Critical** (response within 1 hour): System health alerts, security issues, critical customer emails
  - **High** (response within 4 hours): Important customer communications, time-sensitive tasks
  - **Normal** (response within 24 hours): Standard operational tasks
- Tags with appropriate processing type for routing

#### Step 4: Resource Assessment
- Checks current system load and processing capacity
- Evaluates any dependencies or prerequisites
- Determines if external services are required (MCP servers)
- Assesses for potential conflicts with ongoing operations

#### Step 5: Routing Decision
- **Email tasks** → skill-draft-generator (email mode)
- **Social media tasks** → skill-draft-generator (social mode)
- **Accounting tasks** → skill-draft-generator (odoo mode)
- **Health tasks** → skill-health-monitor
- **Sync tasks** → skill-sync-handler
- **A2A Phase 2** → skill-a2a-upgrade (if enabled)

### Examples

#### Example Input Task
```yaml
---
type: email_triage
source: customer_support
priority: high
from: important.client@example.com
subject: Urgent issue with latest order
status: pending
created: 2026-02-21T15:30:00Z
---
Customer has reported an issue with their latest order #12345.
They need a response within a few hours as this affects their operations.
```

#### Example Process
1. Task identified as email_triage from important client
2. Priority validated as high (response within 4 hours)
3. Compliance check passed - appropriate for cloud draft generation
4. Assigned to skill-draft-generator with email template
5. Response queued for customer with proper escalation flag

#### Example Output
- Task moved to data/In_Progress/cloud/EMAIL_TRIAGE_20260221_1530.md
- Draft generation task queued with high priority
- Dashboard updated with customer priority status

### Error Handling Scenarios

#### Invalid Task Type
- **Issue**: Task type not recognized or not supported by cloud agent
- **Action**: Move to data/Quarantine/ with error details
- **Log**: Record via skill-audit-logger with error classification

#### Compliance Violation
- **Issue**: Task requests local-only operation or violates work-zone separation
- **Action**: Flag for human review, do not process automatically
- **Log**: Create compliance violation record in audit system

#### Resource Unavailable
- **Issue**: Required MCP server or external service unavailable
- **Action**: Queue with retry logic, mark with appropriate SLA adjustment
- **Log**: Track service availability for health monitoring

### Performance Metrics
- Triage completion time (target: < 30 seconds)
- Compliance check accuracy (target: > 99.9%)
- Routing accuracy (target: > 99.5%)
- Escalation rate (target: < 2% of tasks)

### Integration Points
- **Dashboard**: Updates task status and priority metrics
- **Audit Logger**: Records all triage decisions and compliance checks
- **File System**: Manages file movements between directories
- **Health Monitor**: Reports on triage performance and bottlenecks