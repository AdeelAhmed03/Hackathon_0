# skill-health-monitor

## Purpose
Monitor cloud agent health and alert local system on issues, ensuring 24/7 cloud operation according to Platinum Tier policies.

## Trigger
- Scheduled health checks (every 5 minutes)
- Service startup/shutdown events
- Error detection in other skills
- Performance threshold violations

## Input
- System metrics (CPU, memory, disk usage)
- Service status (MCP servers, orchestrator, watchdog)
- Error logs and retry counts
- Performance metrics (response times, throughput)

## Process
1. **System Check**: Monitor CPU, memory, disk, network connectivity
2. **Service Check**: Verify all MCP servers and cloud services are responsive
3. **Performance Check**: Measure response times and throughput metrics
4. **Error Analysis**: Analyze error logs and retry patterns
5. **Threshold Validation**: Compare metrics against Platinum Tier SLA requirements
6. **Alert Generation**: Create alerts for local system when thresholds exceeded
7. **Auto-Recovery**: Attempt recovery up to 3 times before escalating

## Output
- Health status logged to audit system
- Alerts generated in data/Needs_Action/ for local system
- Performance metrics updated in dashboard
- Recovery attempts logged via skill-audit-logger

## Dependencies
- skill-dashboard-updater: Update health status
- skill-logger: Log health metrics and alerts
- skill-error-recovery: Handle service recovery attempts
- skill-file-system-access: Create alert files

## Error Handling
- On monitoring failure: Escalate to local immediately
- On service failure: Attempt auto-recovery with exponential backoff
- On alert system failure: Queue alerts for retry
- On persistent issues: Generate emergency notifications