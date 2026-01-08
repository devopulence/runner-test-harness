# ECS Fargate Runner Testing Strategy with Sleep Workflows

## Architecture Overview

```
ECS Fargate Service
├── Min: 4 tasks
├── Max: 4 tasks (hard limit as requested)
├── Desired: 4 tasks
└── Each task = 1 GitHub Runner
```

## The Sleep-Based Testing Approach

### Core Concept
Use simple workflows that sleep for X seconds to simulate different workload patterns. This gives you precise control over:
- **Job duration**: How long each runner is busy
- **Concurrency**: How many jobs run in parallel
- **Queue formation**: When jobs exceed runner capacity

## Test Workflow: `runner_test.yml`

### Parameters:
- **sleep_duration**: How long each job runs (default: 60s)
- **job_count**: Number of parallel jobs (1-10)
- **job_type**: parallel or sequential

### Usage Examples:

#### Test 1: Baseline (4 jobs, 60s each)
```bash
gh workflow run runner_test.yml \
  -f test_id="baseline_4x60" \
  -f sleep_duration=60 \
  -f job_count=4
```
**Expected**: All 4 jobs run simultaneously, no queuing

#### Test 2: Over-capacity (8 jobs, 60s each)
```bash
gh workflow run runner_test.yml \
  -f test_id="overcapacity_8x60" \
  -f sleep_duration=60 \
  -f job_count=8
```
**Expected**: First 4 run, next 4 queue for ~60s

#### Test 3: Quick Jobs (4 jobs, 10s each)
```bash
gh workflow run runner_test.yml \
  -f test_id="quick_4x10" \
  -f sleep_duration=10 \
  -f job_count=4
```
**Expected**: High throughput, 24 jobs/minute possible

## How Sleep Duration Affects Each Test Type

### 1. Performance Testing
```python
# Test with different sleep durations
sleep_durations = [10, 30, 60, 120, 300]  # seconds

for duration in sleep_durations:
    # Dispatch 4 workflows
    # Measure: queue time, total time
    # Calculate: throughput = 4 runners / duration
```

**Throughput Calculation**:
- 10s jobs: 4 runners × 6 cycles/min = **24 jobs/min**
- 30s jobs: 4 runners × 2 cycles/min = **8 jobs/min**
- 60s jobs: 4 runners × 1 cycle/min = **4 jobs/min**
- 120s jobs: 4 runners × 0.5 cycle/min = **2 jobs/min**

### 2. Load Testing
```python
# Sustained load at runner capacity
def load_test(duration_minutes=30, sleep_duration=60):
    jobs_per_minute = 4  # Match runner count

    for minute in range(duration_minutes):
        dispatch_workflows(
            count=4,
            sleep_duration=sleep_duration
        )
        wait(60)
```

**Key Metrics**:
- Queue depth (should stay at 0 if balanced)
- Runner utilization (should be ~100%)
- Consistent throughput

### 3. Spike Testing
```python
# Sudden load increase
def spike_test():
    # Normal load
    dispatch_workflows(count=2, sleep_duration=60)
    wait(30)

    # SPIKE!
    dispatch_workflows(count=10, sleep_duration=60)

    # Measure recovery time
```

**What to Measure**:
- Queue depth spike (peaks at 6)
- Recovery time (how long to clear queue)
- Impact on subsequent workflows

### 4. Stress Testing
```python
# Find breaking point
def stress_test():
    for job_count in [4, 6, 8, 10, 12, 16, 20]:
        dispatch_workflows(
            count=job_count,
            sleep_duration=60
        )
        # Measure queue growth
        # Find point where queue doesn't clear
```

**Breaking Points**:
- 4 jobs: No queue
- 8 jobs: Queue clears after 1 cycle
- 12 jobs: Queue clears after 2 cycles
- 20 jobs: Queue grows continuously

### 5. Capacity Testing
```python
# Test different parallelism levels
def capacity_test():
    test_patterns = [
        (1, 240),  # 1 job, 4 minutes
        (2, 120),  # 2 jobs, 2 minutes each
        (4, 60),   # 4 jobs, 1 minute each
        (8, 30),   # 8 jobs, 30 seconds each
    ]

    for job_count, sleep_duration in test_patterns:
        # All patterns take same total time
        # But different queue behavior
```

## Terraform Configuration for ECS Fargate

```hcl
# ecs-runners.tf
resource "aws_ecs_service" "github_runners" {
  name            = "github-runners"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.runner.arn

  # Hard limit of 4 runners
  desired_count = 4

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 100  # Prevents scaling beyond 4

  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# Auto-scaling (disabled to maintain exactly 4)
resource "aws_appautoscaling_target" "runners" {
  service_namespace  = "ecs"
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.github_runners.name}"
  scalable_dimension = "ecs:service:DesiredCount"

  min_capacity = 4
  max_capacity = 4  # Hard limit
}
```

## Test Execution Script

```bash
#!/bin/bash
# run_ecs_tests.sh

echo "ECS Fargate Runner Tests (4 runners)"

# Test 1: Perfect fit
echo "Test 1: 4 parallel jobs (60s)"
gh workflow run runner_test.yml \
  -f test_id="perfect_fit" \
  -f sleep_duration=60 \
  -f job_count=4

sleep 90  # Wait for completion

# Test 2: Over capacity
echo "Test 2: 8 parallel jobs (60s)"
gh workflow run runner_test.yml \
  -f test_id="over_capacity" \
  -f sleep_duration=60 \
  -f job_count=8

sleep 150  # Wait for completion

# Test 3: Quick jobs
echo "Test 3: 10 quick jobs (10s)"
gh workflow run runner_test.yml \
  -f test_id="quick_jobs" \
  -f sleep_duration=10 \
  -f job_count=10

sleep 60  # Wait for completion

# Test 4: Long running
echo "Test 4: 4 long jobs (300s)"
gh workflow run runner_test.yml \
  -f test_id="long_running" \
  -f sleep_duration=300 \
  -f job_count=4
```

## Python Test Harness Updates

```python
# test_ecs_runners.py
import asyncio
from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest

async def test_ecs_with_sleep(sleep_duration, job_count, test_name):
    """Test ECS runners with configurable sleep workflows"""

    dispatcher = GitHubWorkflowDispatcher(token, max_concurrent=100)  # No artificial limit

    request = WorkflowDispatchRequest(
        owner="Devopulence",
        repo="test-workflows",
        workflow_id="runner_test.yml",
        inputs={
            "test_id": test_name,
            "sleep_duration": str(sleep_duration),
            "job_count": str(job_count),
            "job_type": "parallel"
        }
    )

    # Dispatch and monitor
    run_id = await dispatcher.dispatch_workflow(request)
    metrics = await dispatcher.monitor_run(owner, repo, run_id)

    # Calculate theoretical vs actual
    theoretical_time = sleep_duration if job_count <= 4 else (sleep_duration * (job_count / 4))
    actual_time = metrics.total_time

    print(f"Test: {test_name}")
    print(f"  Jobs: {job_count}, Sleep: {sleep_duration}s")
    print(f"  Theoretical time: {theoretical_time}s")
    print(f"  Actual time: {actual_time}s")
    print(f"  Queue time: {metrics.queue_time}s")

    return metrics

# Test suite
async def run_ecs_test_suite():
    tests = [
        (60, 4, "baseline"),      # Perfect fit
        (60, 8, "double"),        # 2x capacity
        (30, 4, "quick"),         # Quick jobs
        (120, 4, "slow"),         # Slow jobs
        (60, 1, "single"),        # Under-utilized
        (10, 20, "burst"),        # Many quick jobs
    ]

    for sleep, jobs, name in tests:
        await test_ecs_with_sleep(sleep, jobs, name)
        await asyncio.sleep(sleep + 30)  # Wait for completion
```

## Key Metrics to Track

### Runner Metrics
1. **Utilization**: % time runners are busy
2. **Queue Time**: Time jobs wait for runner
3. **Queue Depth**: Number of jobs waiting

### Performance Metrics
```
Throughput = (4 runners × 60 seconds) / job_duration
Efficiency = Actual throughput / Theoretical throughput
Queue Factor = (Total time - Job duration) / Job duration
```

### Expected Results with 4 ECS Runners

| Test Case | Sleep | Jobs | Total Time | Queue Time |
|-----------|-------|------|------------|------------|
| Baseline | 60s | 4 | 60s | 0s |
| Over 2x | 60s | 8 | 120s | 60s |
| Over 3x | 60s | 12 | 180s | 120s |
| Quick | 10s | 4 | 10s | 0s |
| Quick Burst | 10s | 20 | 50s | varies |
| Long | 300s | 4 | 300s | 0s |

## Implementation Steps

### 1. Deploy ECS with Terraform
```bash
terraform init
terraform plan -var="runner_count=4"
terraform apply
```

### 2. Register Runners
```bash
# SSH into each ECS task and run:
./config.sh \
  --url https://github.com/Devopulence/test-workflows \
  --token $RUNNER_TOKEN \
  --name "ecs-runner-${TASK_ID}" \
  --labels "self-hosted,ecs-fargate"
```

### 3. Run Tests
```bash
# Simple test
make test-ecs

# Or specific test
python test_ecs_runners.py
```

### 4. Analyze Results
- Compare theoretical vs actual times
- Identify queue bottlenecks
- Optimize job durations

## Recommendations

1. **Start with 60s sleep duration** - Easy math, realistic job time
2. **Test job_count in multiples of 4** - 4, 8, 12, 16
3. **Monitor ECS metrics** - CPU, memory, network
4. **Track costs** - $0.20/hour for 4 runners
5. **Document queue behavior** - Critical for capacity planning

The sleep-based approach gives you perfect control over timing and makes it easy to predict and verify runner behavior!