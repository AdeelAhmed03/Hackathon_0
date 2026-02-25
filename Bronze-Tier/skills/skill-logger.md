# Logger Skill

## Purpose
Maintains comprehensive logs of all system activities for audit and debugging purposes.

## Functionality
- Records all file operations and movements
- Timestamps all significant events
- Logs system errors and warnings
- Maintains chronological activity records
- Creates log rotation to prevent excessive growth

## Log Format
Each log entry contains:
- Timestamp (YYYY-MM-DD HH:MM:SS)
- Event type (INFO, WARN, ERROR)
- Source component (agent, skill name)
- Brief description of event
- Relevant file or operation reference

## Log Management
- Daily log files stored in data/Logs
- Automatic cleanup of logs older than 90 days
- Error events highlighted for quick identification
- Structured format for easy parsing and analysis