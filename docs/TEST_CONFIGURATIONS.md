# Test Configuration Quick Reference

## Test Type Configurations

### Performance Test
**Purpose**: Establish baseline metrics for normal operations
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: standard
  enable_randomization: true
  dispatch_rate: 1.0 jobs/minute
  duration: 30 minutes

Expected Results:
  - Execution time: 3-5 minutes
  - Sustainable with minimal queuing
  - Baseline for comparison
```

### Load Test
**Purpose**: Validate system under expected production load
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: standard
  enable_randomization: true
  dispatch_rate: 0.8 jobs/minute (sustainable rate)
  duration: 60 minutes

Expected Results:
  - Minimal queue buildup
  - Consistent execution times
  - Stable runner utilization ~80%
```

### Stress Test
**Purpose**: Find system breaking point
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: heavy
  enable_randomization: true
  dispatch_rate: 1.5 jobs/minute
  duration: 30 minutes

Expected Results:
  - Significant queue buildup
  - Extended wait times
  - Runner utilization 100%
```

### Spike Test
**Purpose**: Test response to sudden load increase
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: varies by phase
  enable_randomization: true

  Phase 1 (10 min):
    workload_type: light
    dispatch_rate: 0.5 jobs/minute

  Phase 2 (10 min):
    workload_type: heavy
    dispatch_rate: 2.0 jobs/minute

  Phase 3 (10 min):
    workload_type: light
    dispatch_rate: 0.5 jobs/minute

Expected Results:
  - Quick queue buildup during spike
  - Recovery time measurement
  - System stability validation
```

### Capacity Test
**Purpose**: Maximum concurrent job handling
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: test
  enable_randomization: false
  dispatch_pattern: burst (20 jobs at once)

Expected Results:
  - 4 jobs run immediately (runner count)
  - 16 jobs queue
  - Measures max queue handling
```

### Soak Test
**Purpose**: Long-term stability validation
```yaml
Configuration:
  workflow: build_job.yml
  workload_type: light
  enable_randomization: true
  dispatch_rate: 0.6 jobs/minute
  duration: 120 minutes (2 hours)

Expected Results:
  - No memory leaks
  - Consistent performance over time
  - No runner degradation
```

## Dispatch Rates by Runner Count

### For 4 Runners (Current Configuration)

| Workload Type | Max Sustainable Rate | Queue Threshold | Breaking Point |
|---------------|---------------------|-----------------|----------------|
| test (30-60s) | 4.0 jobs/min | 5.0 jobs/min | 8.0 jobs/min |
| light (2-3min) | 1.6 jobs/min | 2.0 jobs/min | 3.0 jobs/min |
| standard (3-5min) | 1.0 jobs/min | 1.2 jobs/min | 2.0 jobs/min |
| heavy (5-8min) | 0.6 jobs/min | 0.8 jobs/min | 1.2 jobs/min |

### Calculation Formula
```
Max Sustainable Rate = (Runner Count × 60) / Avg Duration
Queue Threshold = Max Sustainable Rate × 1.2
Breaking Point = Max Sustainable Rate × 2.0
```

## Python Test Configuration Examples

### Performance Test
```python
config = {
    "test_type": "performance",
    "environment": "aws-ecs",
    "workflow": ".github/workflows/build_job.yml",
    "duration_minutes": 30,
    "dispatch_config": {
        "rate": 1.0,
        "pattern": "steady"
    },
    "workflow_inputs": {
        "workload_type": "standard",
        "enable_randomization": "true"
    }
}
```

### Load Test
```python
config = {
    "test_type": "load",
    "environment": "aws-ecs",
    "workflow": ".github/workflows/build_job.yml",
    "duration_minutes": 60,
    "dispatch_config": {
        "rate": 0.8,
        "pattern": "steady"
    },
    "workflow_inputs": {
        "workload_type": "standard",
        "enable_randomization": "true"
    }
}
```

### Stress Test
```python
config = {
    "test_type": "stress",
    "environment": "aws-ecs",
    "workflow": ".github/workflows/build_job.yml",
    "duration_minutes": 30,
    "dispatch_config": {
        "rate": 1.5,
        "pattern": "steady"
    },
    "workflow_inputs": {
        "workload_type": "heavy",
        "enable_randomization": "true"
    }
}
```

## Metrics to Track

### Primary Metrics (All Tests)
- **Queue Time**: Time waiting for available runner
- **Execution Time**: Time running on runner
- **Total Time**: Queue + Execution (user experience)

### Secondary Metrics
- **Runner Utilization**: Percentage of runners busy
- **Throughput**: Jobs completed per hour
- **Success Rate**: Percentage of successful jobs
- **Queue Length**: Number of jobs waiting

### Test-Specific Metrics
| Test Type | Key Metric | Success Criteria |
|-----------|------------|------------------|
| Performance | Avg Total Time | <5 minutes |
| Load | Queue Time | <1 minute |
| Stress | Breaking Point | >1.5 jobs/min |
| Spike | Recovery Time | <5 minutes |
| Capacity | Max Concurrent | =Runner Count |
| Soak | Consistency | <10% variance |

## Reporting Template

All tests should report:
```
TEST TYPE: [Performance/Load/Stress/etc]
Date: YYYY-MM-DD
Duration: XX minutes
Environment: [aws-ecs/openshift]
Runners: X

CONFIGURATION:
- Workflow: build_job.yml
- Workload Type: [test/light/standard/heavy]
- Dispatch Rate: X.X jobs/minute
- Total Jobs: XX

RESULTS:
Developer Metrics:
- Avg Total Time: X.X min
- Max Total Time: X.X min

DevOps Metrics:
- Avg Queue Time: X.X min
- Avg Execution Time: X.X min
- Queue Impact: XX% of total
- Runner Utilization: XX%

CONCLUSION:
[Summary of findings]
```

## Next Steps After Each Test

1. **Performance Test** → Run Load Test at sustainable rate
2. **Load Test** → Run Stress Test to find limits
3. **Stress Test** → Run Spike Test for recovery behavior
4. **Spike Test** → Run Capacity Test for max concurrency
5. **Capacity Test** → Run Soak Test for stability
6. **Soak Test** → Adjust production configuration based on findings