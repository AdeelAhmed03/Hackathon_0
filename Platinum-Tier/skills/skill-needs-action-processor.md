# Needs Action Processor Skill

## Purpose
Processes files in the data/Needs_Action directory according to company policies.

## Functionality
- Scans data/Needs_Action directory for new files
- Reads each file to understand the request
- Applies rules from Company_Handbook.md to determine outcome
- Moves processed files to appropriate status directory
- Generates log entries for all actions taken

## Processing Rules
1. Parse request content and metadata
2. Validate request against Company_Handbook policies
3. Determine if request needs additional approval
4. Move to Pending_Approval, Approved, or Rejected based on validation
5. Update dashboard counters

## Error Handling
- Invalid requests moved to Rejected with reason
- Malformed files logged and skipped
- System errors trigger alert notifications