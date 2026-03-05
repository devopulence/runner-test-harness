# GitHub Actions Monitoring Plan

## From GitHub API (Workflow Runs + Jobs)

### Pipeline Health
- Success/failure rate per workflow, per repo, per branch
- Most frequently failing workflows (your flaky pipeline detector)
- Failure patterns — time of day, specific runners, specific steps
- Mean time to recovery (failed run → next successful run)

### Developer Wait Time
- Queue time: how long jobs wait for a runner (the #1 complaint devs will have)
- Queue time by hour of day — find your peak congestion windows
- Total pipeline time: commit push → all jobs complete
- Step-level breakdown — which steps are slowest (build? scan? deploy?)

### Throughput
- Runs per hour/day, by repo
- Jobs per hour/day
- Trend over weeks — is CI/CD demand growing?
- Peak vs off-peak load patterns

### Job Details
- Execution time distribution per workflow (p50, p95, p99)
- Runner assignment — which runner handled which job
- Retries and re-runs — how often are people re-running?
- Cancelled runs — are devs giving up waiting?

## From ARC API (Kubernetes/OpenShift level)

### Runner Pool
- Total runners vs idle vs busy (right now, real-time)
- Runner scale-up/scale-down events — is autoscaling keeping up?
- Time to provision a new runner pod
- Runner pod failures/restarts

### Capacity Saturation
- Queue depth — jobs waiting with no available runner
- Time spent at max capacity (all runners busy)
- Pending pods — are runners stuck in Pending state (resource constraints)?

### Resource Usage
- CPU/memory per runner pod
- Node utilization across your 4 servers
- Which jobs are resource-heavy vs lightweight

## Combined View (the real value)

This is where it gets powerful — correlating both sources:

| Combined Metric | GitHub API | ARC API |
|---|---|---|
| **Why is queue time high?** | Job waited 5 min | All 4 runners busy, 0 idle |
| **Do we need more runners?** | 30 jobs/hr demand | Runners at 90% utilization |
| **Right-size runners?** | Job X takes 8 min | But only uses 20% CPU |
| **Autoscaling lag** | Job queued at 9:01 | Pod provisioned at 9:03 |
| **Capacity planning** | Demand growing 10%/week | Currently 4 runners, headroom shrinking |
