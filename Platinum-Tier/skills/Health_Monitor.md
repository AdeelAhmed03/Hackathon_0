# Health_Monitor

## Extended Skill Definition

### Overview
Health_Monitor continuously assesses the health and performance of the Cloud Executive agent and its supporting services. This skill ensures 24/7 operation by detecting issues early and alerting the local system when cloud services degrade, maintaining Platinum Tier uptime requirements (99.9%).

### Detailed Process Flow

#### Step 1: System Metrics Collection
- Monitor CPU usage, memory consumption, disk space, and network connectivity
- Check system load averages and process counts
- Verify system clock synchronization and time drift
- Assess overall system responsiveness

#### Step 2: Service Availability Checks
- Ping all MCP servers (email, odoo, social, browser)
- Test database connections if applicable
- Validate API endpoints and external service connectivity
- Check file system permissions and disk I/O performance

#### Step 3: Performance Monitoring
- Measure response times for all services
- Track throughput metrics (requests per minute, operations per second)
- Monitor queue lengths and processing delays
- Assess error rates and retry patterns

#### Step 4: Error Pattern Analysis
- Analyze recent error logs and exception rates
- Identify recurring error patterns that may indicate systemic issues
- Cross-reference error types with retry behavior
- Assess the impact of errors on overall system health

#### Step 5: SLA Compliance Check
- Compare measured metrics against Platinum Tier SLA requirements
- Verify 99.9% uptime commitment
- Check performance thresholds (response times, throughput)
- Validate that error rates remain within acceptable limits

#### Step 6: Auto-Recovery Attempt
- If service issues detected, attempt recovery procedures:
  - Restart unresponsive MCP servers
  - Clear stuck queues
  - Reconnect failed external services
- Limit recovery attempts to 3 per service to prevent thrashing
- Log all recovery actions taken

#### Step 7: Alert Generation
- Generate appropriate alerts for local system based on issue severity:
  - **Critical**: Service down, data loss, security breach
  - **High**: Performance degradation, repeated failures
  - **Medium**: Resource constraints, configuration issues
  - **Low**: Warnings, information for optimization
- Create alert files in data/Needs_Action/ for local attention

### Health Check Categories

#### Infrastructure Health
- **System Resources**: CPU, memory, disk, network (thresholds: <80% usage)
- **Process Health**: Running processes, zombie processes, memory leaks
- **File System**: Disk space, I/O performance, permission access
- **Network**: Connectivity, bandwidth, latency to external services

#### Service Health
- **MCP Servers**: Email-mcp, odoo-mcp, social-mcp, browser-mcp availability
- **API Endpoints**: Response time, error rate, authentication
- **Database**: Connection health, query performance, storage
- **File Watchers**: Inotify, polling mechanisms, file access

#### Application Health
- **Core Functions**: Triage, draft generation, sync operations
- **Error Rates**: Exception frequency, retry patterns, failure modes
- **Performance**: Response times, throughput, resource utilization
- **Business Logic**: Compliance with Platinum Tier policies

### Examples

#### Example Health Check Report
**Timestamp**: 2026-02-21T16:30:00Z
**Status**: HEALTHY

**System Metrics**:
- CPU: 15% (OK, <80%)
- Memory: 2.1GB/8GB (26%, OK, <80%)
- Disk: 120GB/500GB (24%, OK, >20% free)
- Network: 12ms average latency (OK)

**Service Status**:
- email-mcp: Responding in 23ms (OK)
- odoo-mcp: Responding in 45ms (OK)
- social-mcp: Responding in 31ms (OK)
- cloud_sync: Last sync 12 minutes ago (OK)

**Performance**:
- Average response time: 38ms
- Operations per minute: 24
- Error rate: 0.02% (OK, <0.1%)
- Queue depth: 0 (OK)

**SLA Compliance**: 99.97% uptime this month (OK, >99.9%)

#### Example Alert Generation
**Issue**: odoo-mcp service unresponsive
**Severity**: HIGH
**Action**: Auto-recovery attempted - restarted service
**Result**: Service restored in 12 seconds

**Auto-Generated Alert File** (`data/Needs_Action/ALERT_odoo-mcp_20260221_1635.md`):
```yaml
---
type: health_alert
severity: high
service: odoo-mcp
status: resolved
created: 2026-02-21T16:35:00Z
resolved: 2026-02-21T16:35:12Z
---
## Service Health Alert

**Service**: odoo-mcp
**Severity**: HIGH
**Time**: 2026-02-21T16:35:00Z

### Issue
odoo-mcp service became unresponsive, not responding to health checks.

### Resolution
Auto-recovery system restarted the service. Service restored after 12 seconds.

### Impact
- 12 seconds of service unavailability
- 3 pending requests timed out
- All services now healthy

### Recommendation
Monitor service stability over the next hour for recurring issues.
```

### Alert Thresholds

#### Critical Alerts (Immediate Attention)
- Service completely unresponsive (>30s timeout)
- System resource exhaustion (CPU > 95%, memory > 95%)
- Data corruption or integrity failures
- Security breach detected

#### High Alerts (Within 1 hour)
- Service performance degradation (>3x normal response time)
- Repeated service failures (>5 failures in 10 minutes)
- Resource constraints (CPU > 85%, memory > 85% for >5 min)
- External API errors >50%

#### Medium Alerts (Within 4 hours)
- Moderate performance degradation (1.5x normal response time)
- Service restart events
- Resource usage >80% for >10 minutes
- Queue backlog >50 items

#### Low Alerts (Within 24 hours)
- Minor performance variations
- Configuration warnings
- Resource usage >70%
- Informational notices

### Auto-Recovery Procedures

#### Service Restart
- Identify unresponsive or high-error services
- Safely stop service with proper cleanup
- Clear any stuck state or cache
- Restart with fresh configuration

#### Queue Management
- Check for stuck processing queues
- Reset queue position if necessary
- Verify queue integrity
- Resume processing with appropriate backoff

#### Resource Management
- Clear memory-intensive caches
- Close unused connections
- Optimize resource allocation
- Reset performance-tuning parameters

### Integration Points
- **Dashboard**: Updates with real-time health metrics
- **Audit Logger**: Records all health checks and incidents
- **Cloud Executive**: Adjusts behavior based on health status
- **Sync Handler**: May be paused during critical health issues
- **All Services**: Provides health status for decision making

### Performance Metrics
- **Health Check Frequency**: Every 5 minutes during normal operation
- **Response Time**: Target < 100ms for health check execution
- **Uptime**: Target 99.9% as per Platinum Tier commitment
- **Alert Response**: Target < 30 seconds from issue detection
- **Auto-Recovery Success**: Target > 90% success rate