# Dashboard Updater Skill

## Purpose
Maintains accurate statistics in data/Dashboard.md by counting files in each status directory.

## Functionality
- Counts files in each data status directory
- Updates dashboard counters with current numbers
- Records timestamp of last update
- Preserves other dashboard content

## Update Process
1. Count files in data/Done
2. Count files in data/Pending_Approval
3. Count files in data/Approved
4. Count files in data/Rejected
5. Count files in data/Needs_Action
6. Update data/Dashboard.md with new counts

## Schedule
- Updates after each request processing cycle
- Available for manual updates when needed
- Includes system health indicators