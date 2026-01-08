# GitHub Runner Job Execution Constraints

## Core Constraint: 1 Runner = 1 Job at a Time

**CRITICAL**: A single GitHub Actions runner can only execute ONE job at a time, regardless of hosting platform (OpenShift, ECS, Kubernetes, etc.).

## Understanding Workflows vs Jobs vs Steps

```yaml
workflow:                    # Can have multiple jobs
  job1:                     # Needs 1 runner
    steps: [...]            # All run on same runner
  job2:                     # Needs another runner (or waits)
    steps: [...]
  job3:                     # Needs another runner (or waits)
    needs: [job1, job2]     # Sequential dependency
```

## Capacity Scenarios with 4 Runners

### Scenario 1: Simple Workflows (1 job each)
```
4 workflows (1 job each) = 4 runners needed
✅ All run simultaneously
```

### Scenario 2: Complex Workflow (4 parallel jobs)
```
1 workflow (4 parallel jobs) = 4 runners needed
✅ Uses all capacity for single workflow
```

### Scenario 3: Overload (Matrix Strategy)
```yaml
strategy:
  matrix:
    test: [1,2,3,4,5,6,7,8]  # 8 jobs!
```
```
With 4 runners:
Time 0: Jobs 1-4 run ✅
Time X: Jobs 5-8 wait ⏳
Time X+duration: Jobs 5-8 run ✅
```

### Scenario 4: Mixed Workload
```
Workflow A: 2 parallel jobs
Workflow B: 1 job
Workflow C: 3 parallel jobs
Total: 6 jobs need runners

With 4 runners:
- First 4 jobs run
- 2 jobs queue
- Workflow C partially blocked
```

## Real-World Impact on Your Testing

### Test Case 1: Maximum Throughput
```bash
# With 4 runners, dispatch 4 single-job workflows
Expected: All 4 run simultaneously
Actual throughput: 4 jobs at once
```

### Test Case 2: Workflow Bottleneck
```bash
# Dispatch 1 workflow with 8 parallel jobs
Expected: Only 4 jobs run, 4 wait
Total time: 2x single job duration
```

### Test Case 3: Queue Formation
```bash
# Dispatch 8 single-job workflows
Expected: First 4 run, next 4 queue
Queue depth: 4
```

## Runner Utilization Patterns

### Pattern A: Perfect Fit
```
4 workflows × 1 job = 4 jobs total
Runner utilization: 100%
Queue depth: 0
```

### Pattern B: Underutilized
```
2 workflows × 1 job = 2 jobs total
Runner utilization: 50%
Idle runners: 2
```

### Pattern C: Oversubscribed
```
3 workflows × 3 jobs = 9 jobs total
Runner utilization: 100%
Queue depth: 5
Wait time: Significant
```

## Optimizing for 4-Runner Constraint

### 1. **Minimize Parallel Jobs**
```yaml
# Instead of:
strategy:
  matrix:
    test: [1,2,3,4,5,6,7,8]

# Consider:
strategy:
  matrix:
    test: [1,2,3,4]  # Match runner count
```

### 2. **Batch Sequential Steps**
```yaml
# Combine multiple steps into single job
# Instead of 3 jobs, use 1 job with 3 steps
job:
  steps:
    - name: Test
    - name: Build
    - name: Deploy
```

### 3. **Time-Based Scheduling**
```yaml
# Spread workflows across time
on:
  schedule:
    - cron: '0 * * * *'  # Hourly, not all at once
```

## Testing Commands for Job Constraints

### Test Single Job per Workflow
```bash
# Dispatch 4 workflows with 1 job each
for i in {1..4}; do
  gh workflow run simple_test.yml
done
# Result: All 4 run simultaneously
```

### Test Multi-Job Workflow
```bash
# Dispatch 1 workflow with parallel jobs
gh workflow run parallel_jobs.yml --field job_count=8
# Result: Only 4 jobs run at once
```

### Test Queue Buildup
```bash
# Dispatch 10 workflows rapidly
for i in {1..10}; do
  gh workflow run simple_test.yml &
done
# Result: First 4 run, 6 queue
```

## Key Metrics to Monitor

1. **Jobs per Workflow**: Average parallel jobs
2. **Runner Utilization**: % time busy
3. **Queue Depth**: Jobs waiting for runner
4. **Wait Time**: Time from dispatch to execution
5. **Job Duration**: How long each job runs

## OpenShift vs ECS Comparison

| Aspect | OpenShift (4 runners) | ECS Fargate (4 tasks) |
|--------|----------------------|---------------------|
| **Max Concurrent Jobs** | 4 | 4 |
| **Single Job Limit** | 1 per runner | 1 per task |
| **Scaling** | Fixed | Can auto-scale |
| **Queue Location** | GitHub | GitHub |
| **Job Assignment** | GitHub assigns | GitHub assigns |

## Recommendations

1. **Design workflows** to use ≤4 parallel jobs
2. **Monitor job queue** depth continuously
3. **Optimize job duration** to increase throughput
4. **Consider job dependencies** to reduce parallelism
5. **Test with realistic** workflow patterns

## The Math That Matters

```
4 Runners × 60 minutes = 240 runner-minutes per hour

If average job = 5 minutes:
  Max jobs per hour = 48

If average job = 10 minutes:
  Max jobs per hour = 24

If average job = 1 minute:
  Max jobs per hour = 240
```

**Bottom Line**: With 4 runners, you can run exactly 4 jobs simultaneously, no more. Plan your workflows accordingly!