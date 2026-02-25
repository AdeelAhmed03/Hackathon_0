# Agent Core Framework

## Purpose
The core agent system manages all employee vault operations through a file-based memory system.

## Architecture
- Monitors data/Needs_Action for new requests
- Processes requests according to Company_Handbook policies
- Updates status in appropriate folders (Pending_Approval, Approved, Rejected)
- Maintains logs in data/Logs
- Updates dashboard in data/Dashboard.md

## File-Based Memory System
The agent uses the file system as its memory:
- Each request is a file in a specific directory
- Directory location indicates request status
- File content contains request details and metadata
- Agent reads/writes files to process requests and update state

## Processing Flow
1. Check data/Needs_Action for new files
2. Apply Company_Handbook rules to determine next action
3. Move file to appropriate status directory
4. Update data/Dashboard.md with new statistics
5. Log action in data/Logs