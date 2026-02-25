# Logger Skill

## Purpose
Maintains comprehensive logs of all system activities for audit and debugging purposes.

## Functionality
- Records all file operations and movements
- Timestamps all significant events
- Logs system errors and warnings
- Maintains chronological activity records
- Daily log rotation by filename (YYYY-MM-DD.json)

## Log Format
Each log entry contains:
- Timestamp (YYYY-MM-DD HH:MM:SS)
- Event type (INFO, WARN, ERROR)
- Source component (agent, skill name)
- Brief description of event
- Relevant file or operation reference

## Log Management
- Daily log files stored in data/Logs (one file per day: YYYY-MM-DD.json)
- Old log files are preserved for audit trail — no automatic deletion
- Error events highlighted for quick identification
- Structured format for easy parsing and analysis