# How 4-Runner Simulation Works on Public GitHub Runners

## The Challenge
- **Public GitHub Runners**: 20+ runners available
- **Your OpenShift**: Only 4 runners
- **Need**: Test with 4-runner constraints before moving to OpenShift

## The Solution: Artificial Concurrency Limiting

### How We Simulate 4 Runners

```yaml
# In config.yaml
github:
  max_concurrent: 4  # This is the KEY setting
```

This setting does **NOT** limit GitHub's runners. Instead, it limits **our test harness** to only dispatch/monitor 4 workflows at a time.

### What Actually Happens:

```python
# In dispatcher.py
class GitHubWorkflowDispatcher:
    def __init__(self, token, max_concurrent=4):  # <-- Limited to 4
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def dispatch_workflow(self, request):
        async with self.semaphore:  # <-- Only 4 can run this code at once
            # Dispatch workflow
```

### Visual Example:

**Without Simulation (Public Runners)**:
```
Dispatch 10 workflows → All 10 run immediately on 10 different runners
Time 0: [W1][W2][W3][W4][W5][W6][W7][W8][W9][W10] ← All running
```

**With 4-Runner Simulation**:
```
Dispatch 10 workflows → Only 4 dispatched at a time
Time 0: [W1][W2][W3][W4] ← Running
        [W5][W6][W7][W8][W9][W10] ← Waiting in our local queue

Time 30s: W1 finishes
         [W2][W3][W4][W5] ← Running
         [W6][W7][W8][W9][W10] ← Still waiting
```

## Three Ways to Run 4-Runner Simulation

### Method 1: Use the Simulation Environment
```bash
# This automatically sets max_concurrent=4
python test_harness.py --environment simulate-4-runners
```

### Method 2: Use the Dedicated 4-Runner Test
```bash
# Purpose-built for 4-runner testing
python test_4_runners.py
# or
make test-4-runners
```

### Method 3: Update Default Config
```yaml
# In config.yaml, change default:
github:
  max_concurrent: 4  # Changed from 20 to 4
```

## What the Simulation Shows You

### 1. **Dispatch Throttling**
Even though GitHub has 20+ runners available, we only dispatch 4 workflows at a time.

### 2. **Local Queue Formation**
Workflows 5+ wait in our Python code, not on GitHub. This simulates the queue that would form on OpenShift.

### 3. **Realistic Timing**
The queue times you see will be similar to what you'll experience with real 4-runner limits.

### 4. **Throughput Limitations**
You'll see that throughput caps at 4 concurrent workflows, regardless of load.

## Validation: How to Confirm It's Working

### Check 1: Watch the Console Output
```
Dispatching batch of 10 workflows
✅ Dispatched workflow 1
✅ Dispatched workflow 2
✅ Dispatched workflow 3
✅ Dispatched workflow 4
[Pause here - waiting for a slot]
✅ Dispatched workflow 5 (only after #1 finishes)
```

### Check 2: Look at GitHub Actions UI
- With simulation OFF: You'd see 10 workflows running simultaneously
- With simulation ON: You'll see max 4 workflows running at once

### Check 3: Check the Metrics
```python
# Queue times should show delays for workflows 5+
Average queue time: 45.2s  # Higher because of artificial limit
Max queue time: 120.5s     # Some workflows waited 2 minutes
```

## Important Notes

### What This Simulates ✅
- Maximum 4 concurrent workflows
- Queue formation and delays
- Throughput limitations
- Resource contention behavior

### What This Doesn't Simulate ❌
- Actual OpenShift infrastructure issues
- Network latency to self-hosted runners
- OpenShift-specific resource constraints
- Runner startup time differences

## Quick Test to See the Difference

### Test WITHOUT 4-Runner Limit:
```bash
# Edit config.yaml: max_concurrent: 20
python test_harness.py --test capacity
# Result: 20 workflows run simultaneously
```

### Test WITH 4-Runner Limit:
```bash
# Edit config.yaml: max_concurrent: 4
python test_harness.py --test capacity
# Result: Only 4 run at a time, others queue
```

## Recommendation

Always test with BOTH configurations:
1. **Full capacity** (max_concurrent: 20) - Understand workflow behavior
2. **4-runner limit** (max_concurrent: 4) - Understand OpenShift constraints

This gives you complete picture before migrating to OpenShift.