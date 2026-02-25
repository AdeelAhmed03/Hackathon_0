# Skill: Logger

**Purpose:** Maintain comprehensive logs of all system activities for audit and debugging purposes.

**Process:**
Append JSON object to data/Logs/YYYY-MM-DD.json (create file if missing):

```json
{
  "timestamp": "2026-02-13T10:30:00Z",
  "agent": "Agent_Core",
  "action": "processed_file",
  "file": "data/Needs_Action/xxx.md",
  "result": "moved_to_done",
  "approval_needed": false,
  "details": "Optional additional information about the action"
}
```

**Log Entry Fields:**
- timestamp: ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
- agent: Name of the agent performing the action (typically "Agent_Core")
- action: Type of action performed (processed_file, moved_file, created_approval, etc.)
- file: Path of the file being operated on
- result: Outcome of the action (moved_to_done, moved_to_pending_approval, etc.)
- approval_needed: Boolean indicating if approval was required
- details: Optional field for additional context

**File Naming Convention:**
- Log files are named by date: YYYY-MM-DD.json (e.g., 2026-02-13.json)
- Stored in data/Logs/ directory
- Created if missing when first log entry is added

**Log Rotation:**
- Each day's logs are stored in a separate file
- Old log files are preserved for audit trail
- No automatic deletion (managed separately if needed)

**Error Logging:**
- All errors and exceptions should be logged
- Include error message and stack trace (if appropriate)
- Mark with "error" in the action field

**Security Logging:**
- All access attempts to sensitive data
- All approval requests and decisions
- Any unusual or potentially unauthorized actions