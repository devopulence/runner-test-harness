# 🎯 How to Run 4-Runner Simulation Tests

## Quick Answer: YES, We Can Simulate 4 Runners!

Even though you're using public GitHub runners (20+ available), we can simulate having only 4 runners by **artificially limiting our test harness** to dispatch only 4 workflows at a time.

## Three Ways to Test with 4-Runner Limit

### 1️⃣ Easiest: Use the Simulation Environment
```bash
python test_harness.py --environment simulate-4-runners --test performance
python test_harness.py --environment simulate-4-runners --test load
python test_harness.py --environment simulate-4-runners --test capacity
```

### 2️⃣ Dedicated 4-Runner Test Suite
```bash
make test-4-runners
# or
python test_4_runners.py
```

This runs specific tests designed for 4-runner scenarios:
- Exact capacity test (4 workflows)
- Over capacity test (8 workflows - see queuing)
- Sustained load test (4 workflows/minute)
- Queue stress test (progressive overload)

### 3️⃣ See It In Action: Interactive Demo
```bash
make demo-4-runners
# or
python demonstrate_4_runner_limit.py
```

Choose option 3 to see BOTH scenarios and compare!

## How the Simulation Works

### The Magic Setting:
```python
# This limits our dispatcher to 4 concurrent operations
GitHubWorkflowDispatcher(token, max_concurrent=4)
```

### What Happens:
- **Workflows 1-4**: Dispatch immediately ✅
- **Workflows 5+**: Wait in our Python queue ⏳
- **As each finishes**: Next one starts 🔄

### Visual Example:
```
With Public Runners (no limit):
[W1][W2][W3][W4][W5][W6][W7][W8] → All run at once

With 4-Runner Simulation:
[W1][W2][W3][W4] → Running
[W5][W6][W7][W8] → Waiting in queue
```

## Quick Test Commands

### See the Difference:
```bash
# Without limit (uses public runner capacity)
python test_harness.py --environment development --test capacity

# With 4-runner limit
python test_harness.py --environment simulate-4-runners --test capacity
```

### Test Queue Formation:
```bash
# This will dispatch 8 workflows but only 4 can run at once
python test_4_runners.py
```

Watch the output - you'll see:
- First 4 dispatch quickly
- Next 4 have to wait
- Queue times increase

## What to Look For

### In Console Output:
```
✅ Dispatched workflow 1
✅ Dispatched workflow 2
✅ Dispatched workflow 3
✅ Dispatched workflow 4
[PAUSE - waiting for slot]
✅ Dispatched workflow 5  (only after one finishes)
```

### In GitHub Actions UI:
- You'll see maximum 4 workflows running at once
- Even though GitHub has 20+ runners available
- New workflows only start as others complete

### In Metrics:
```
Without Simulation:
  Queue time: 2-5 seconds
  All workflows run in parallel

With 4-Runner Simulation:
  Queue time: 30-120 seconds for workflows 5+
  Maximum 4 running at any time
```

## Why This Matters

When you move to OpenShift with 4 runners:
- **This is exactly what will happen**
- Workflows 5+ will queue
- Queue times will increase under load
- Throughput caps at 4 concurrent workflows

By testing with this simulation NOW, you'll know:
- How long queues get
- What load your system can handle
- Where bottlenecks form
- How to optimize workflow duration

## Start Testing Now!

```bash
# 1. Set token
export GITHUB_TOKEN='your_token'

# 2. Upload workflows (if not done)
make setup

# 3. Run 4-runner simulation
make test-4-runners

# 4. See the demonstration
make demo-4-runners
```

This simulation gives you **real data** about how your system will perform with only 4 runners, even while testing on public GitHub!