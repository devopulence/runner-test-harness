# Runner Capacity Limits and Testing Strategy

## Current vs Future Runner Capacity

### Public GitHub Runners (Current Testing)
- **Capacity**: ~20+ runners available
- **Repository**: Devopulence/test-workflows
- **Constraints**: GitHub API rate limits (primary bottleneck)
- **Max Useful Concurrency**: 20-50 workflows

### Self-Hosted OpenShift Runners (Future)
- **Capacity**: **4 runners ONLY** (HARD LIMIT)
- **Repository**: Internal repository (TBD)
- **Constraints**: Physical runner limit
- **Max Useful Concurrency**: 4 workflows

## Understanding the 4-Runner Constraint

With only 4 runners on OpenShift:

1. **Maximum Parallel Execution**: 4 workflows simultaneously
2. **Queue Behavior**: Workflow #5 and beyond must wait
3. **Throughput Ceiling**: ~4 workflows at any given time
4. **Critical Metrics**:
   - Queue depth (how many waiting)
   - Queue time (how long they wait)
   - Runner utilization (% time busy)

## Testing Strategies for 4-Runner Environment

### 1. Capacity Testing (Most Important for 4-Runner Limit)

```yaml
# Optimal test for 4-runner environment
capacity:
  concurrency_levels: [1, 2, 3, 4, 5, 6, 8, 10]
```

**What This Tests:**
- 1-3: Under-capacity (runners available)
- 4: At capacity (all runners busy)
- 5-10: Over-capacity (queue building)

**Key Questions:**
- How long do workflows wait when all 4 runners are busy?
- Does the queue clear efficiently?
- What's the optimal batch size?

### 2. Load Testing Adjusted for 4 Runners

```yaml
load:
  steady_state:
    workflows_per_minute: 4  # Match runner capacity
```

**Why 4 workflows/minute?**
- If each workflow takes ~1 minute, 4 runners can handle 4 workflows/minute
- Higher rates will create queues
- Lower rates will underutilize runners

### 3. Stress Testing for 4-Runner Breaking Point

```yaml
stress:
  initial_workflows_per_minute: 2
  increment: 2
  max_workflows_per_minute: 20
```

**Expected Breaking Points:**
- 4-6 wpm: Queues start forming
- 8-10 wpm: Significant queue delays
- 12+ wpm: Queue grows unbounded

## Test Scenarios to Run Now (Simulating 4-Runner Limit)

### Scenario 1: Baseline 4-Runner Capacity
```bash
# Dispatch exactly 4 parallel workflows
python test_harness.py --test capacity
# Watch for: All 4 should run simultaneously
```

### Scenario 2: Queue Formation Test
```bash
# Dispatch 8 workflows at once (2x capacity)
# This simulates what happens with 4 runners
python test_harness.py --test capacity
# Watch for: First 4 run, next 4 queue
```

### Scenario 3: Sustained Load at Capacity
```bash
# Run at exactly 4 workflows/minute for 30 minutes
python test_harness.py --test load
# Watch for: Can it sustain without queue growth?
```

## Metrics to Track for 4-Runner Environment

### Critical Metrics
1. **Queue Time** - How long workflows wait for a runner
2. **Queue Depth** - How many workflows are waiting
3. **Runner Utilization** - % of time runners are busy
4. **Throughput** - Actual workflows completed/minute

### Warning Thresholds for 4 Runners
```yaml
alerts:
  thresholds:
    queue_depth_warning: 4      # Equal to runner count
    queue_depth_critical: 8     # 2x runner count
    queue_time_warning: 60      # 1 minute wait
    queue_time_critical: 300    # 5 minute wait
    runner_utilization_low: 50  # Under-utilized
    runner_utilization_high: 95 # Over-saturated
```

## Configuration for Testing 4-Runner Scenarios

### Quick Test for 4-Runner Simulation
```python
# In test_harness.py or custom script
async def test_four_runner_capacity():
    """Test specifically for 4-runner capacity"""

    # Test 1: Exactly 4 workflows
    dispatch_batch(4)  # Should all run in parallel

    # Test 2: 6 workflows (4 run, 2 queue)
    dispatch_batch(6)  # First 4 run, 2 wait

    # Test 3: Sustained 4 wpm for 10 minutes
    for minute in range(10):
        dispatch_batch(4)
        sleep(60)
```

## Recommendations for Your Testing

### Phase 1: Current Testing (Public Runners)
1. **Test at high concurrency** (20-50) to understand workflow behavior
2. **But also test at exactly 4** to simulate OpenShift
3. **Monitor queue formation** when limiting to 4 concurrent

### Phase 2: Preparation for OpenShift
1. **Run all tests with max concurrency of 4**
2. **Focus on queue management** strategies
3. **Optimize workflow duration** to maximize throughput

### Phase 3: OpenShift Deployment
1. **Start conservative**: 2-3 workflows/minute
2. **Monitor queue depth** constantly
3. **Implement queue limits** to prevent overload

## Key Insights for 4-Runner Environment

### Math for 4 Runners:
- If workflow duration = 60 seconds
- Max throughput = 4 workflows/minute
- If workflow duration = 30 seconds
- Max throughput = 8 workflows/minute

### Queue Management:
- Queue depth > 4 = workflows waiting
- Queue depth > 8 = significant delays
- Queue depth > 20 = system overwhelmed

### Optimization Strategies:
1. **Shorter workflows** = higher throughput
2. **Batch similar workflows** = predictable timing
3. **Priority queue** = critical workflows first
4. **Time-based scheduling** = spread load evenly

## Testing Commands for 4-Runner Scenarios

```bash
# Test exactly at capacity
CONCURRENCY=4 python test_harness.py --test capacity

# Test queue formation
CONCURRENCY=8 python test_harness.py --test capacity

# Test sustained load at 4 wpm
WORKFLOWS_PER_MINUTE=4 python test_harness.py --test load

# Find breaking point for 4 runners
MAX_WPM=20 python test_harness.py --test stress
```

## Summary

**Remember**: You have a hard limit of 4 runners in your OpenShift environment.

- **Current testing** on public runners helps understand workflow behavior
- **But always keep the 4-runner limit in mind**
- **Design your tests** to specifically evaluate 4-runner scenarios
- **Queue management** becomes critical with only 4 runners
- **Throughput ceiling** is 4 concurrent workflows maximum

The key is not just testing performance, but understanding how your system behaves when constrained to exactly 4 runners.