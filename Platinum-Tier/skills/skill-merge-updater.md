# skill-merge-updater

## Purpose
Merge cloud-generated updates from `/Updates/` directory into the local `Dashboard.md` file, maintaining the single-writer principle for dashboard updates while incorporating cloud system metrics.

## Trigger
When cloud system generates update files in `/Updates/` directory

## Input
- Update files from `/Updates/` (typically named `cloud_{id}.md`)
- Current local `Dashboard.md` content
- Update data (metrics, counts, activity logs)

## Process
1. Scan `/Updates/` directory for new update files
2. Parse update content and extract metrics/data
3. Merge cloud metrics with local dashboard data
4. Apply Platinum Tier conflict resolution rules
5. Update single-writer Dashboard.md with merged data
6. Preserve local-only metrics while adding cloud data

## Output
- Updated `Dashboard.md` with merged cloud/local data
- Processed update files moved to `/Done/local/`
- Updated dashboard metrics reflecting both cloud and local activity
- Audit log of dashboard update operations

## Dependencies
- File system access to read `/Updates/` and write `Dashboard.md`
- Dashboard parsing and updating capability
- Audit logging system
- File move operations for completed updates