# Test Run Tracking System

## Overview

The Test Run Tracking System solves a critical problem in performance testing: **distinguishing workflows from different test runs**. When you run the same test multiple times (e.g., `python run_tests.py -e aws_ecs -t performance`), all workflows look identical in GitHub Actions, making it impossible to analyze specific test runs accurately.

## The Problem

### Without Tracking
```
8:00 AM - Run performance test → 34 workflows dispatched
8:30 AM - Run performance test → 34 workflows dispatched
9:00 AM - Analyze results → Which 34 workflows belong to which test?
```

**Result**: Cannot distinguish workflows, metrics get mixed, analysis is unreliable.

## The Solution

### With Test Run Tracking
Each test run gets a **unique identifier** that tags all its workflows:

```
Test Run ID: performance_20260104_093000_abc123
             ^^^^^^^^^^^  ^^^^^^^^  ^^^^^^  ^^^^^^
             test_type    date      time    uuid
```

## How It Works

### 1. Test Initialization
When you start a test, the system automatically:
- Generates a unique test run ID
- Creates a TestRunTracker instance
- Logs the ID for reference

```python
# This happens automatically in ScenarioRunner
self.test_run_tracker = TestRunTracker(
    test_type="performance",
    environment="aws-ecs"
)
```

### 2. Workflow Tagging
Every workflow dispatched includes the test run ID in its `job_name` input:

```json
{
    "workload_type": "standard",
    "job_name": "performance_20260104_093000_abc123"
}
```

This appears in the workflow output:
```
🚀 Starting build simulation
Workflow: Realistic Build Job
Run ID: 123456789
Job: performance_20260104_093000_abc123  ← Test run identifier
Workload Type: standard
```

### 3. Tracking Data Storage
When the test completes, tracking data is saved:

**Location**: `test_results/{environment}/tracking/{test_run_id}.json`

**Contents**:
```json
{
    "test_run_id": "performance_20260104_093000_abc123",
    "test_type": "performance",
    "environment": "aws-ecs",
    "start_time": "2026-01-04T09:30:00",
    "end_time": "2026-01-04T10:00:00",
    "duration_minutes": 30,
    "workflow_count": 34,
    "workflow_ids": [20693001, 20693002, ...],
    "workflow_names": ["build_job", "build_job", ...],
    "metadata": {
        "job_name_tag": "performance_20260104_093000_abc123",
        "query_hint": "Search for workflows with job_name=performance_20260104_093000_abc123"
    }
}
```

### 4. Analysis
Analyze specific test runs using the tracking data:

```bash
# List all test runs
python analyze_specific_test.py --list

# Analyze the latest test run
python analyze_specific_test.py

# Analyze a specific test run
python analyze_specific_test.py --test-run-id performance_20260104_093000_abc123
```

## Usage

### Running Tests (Automatic Tracking)
```bash
# Tracking happens automatically when you run tests
python run_tests.py -e aws_ecs -t performance
```

Output shows the test run ID:
```
Loading environment: aws_ecs
Starting test profile: performance
Test Run ID: performance_20260104_093000_abc123  ← Your unique identifier
```

### Finding Your Test Run
```bash
# List all test runs for an environment
python analyze_specific_test.py --list

Available test runs:
------------------------------------------------------------
ID: performance_20260104_093000_abc123
  Type: performance
  Time: 2026-01-04T09:30:00
  Duration: 30.0 minutes
  Workflows: 34

ID: performance_20260104_083000_def456
  Type: performance
  Time: 2026-01-04T08:30:00
  Duration: 30.0 minutes
  Workflows: 34
```

### Analyzing a Specific Test Run
```bash
python analyze_specific_test.py --test-run-id performance_20260104_093000_abc123
```

Output:
```
Analyzing test run: performance_20260104_093000_abc123
Test type: performance
Start time: 2026-01-04T09:30:00
Duration: 30.0 minutes
Expected workflows: 34
------------------------------------------------------------
Looking for workflows tagged with job_name: performance_20260104_093000_abc123
Found 34 workflows from this test run

📊 METRICS SUMMARY
----------------------------------------
Workflows completed: 34/34
Average Queue Time:     0.3 minutes
Average Execution Time: 3.5 minutes
Average Total Time:     3.8 minutes
Queue Impact:           8% of total
```

## Benefits

1. **Multiple Concurrent Tests**: Run different test types simultaneously without confusion
2. **Historical Analysis**: Analyze any past test run precisely
3. **Accurate Comparisons**: Compare metrics between specific test runs
4. **No Data Mixing**: Each test run's metrics are completely isolated
5. **Reproducible Results**: Re-run exact same test and compare results

## API Reference

### TestRunTracker Class

```python
from src.orchestrator.test_run_tracker import TestRunTracker

# Create tracker
tracker = TestRunTracker(
    test_type="performance",    # Test profile name
    environment="aws-ecs"        # Environment name
)

# Get the unique ID to tag workflows
job_name = tracker.get_job_name()  # Returns: performance_20260104_093000_abc123

# Record a dispatched workflow
tracker.add_workflow(
    workflow_id=123456789,
    workflow_name="build_job"
)

# Save tracking data at test end
tracker.save_tracking_data()
```

### Loading Test Run Data

```python
from src.orchestrator.test_run_tracker import load_test_run, list_test_runs

# List all test runs
runs = list_test_runs("aws-ecs")
for run in runs:
    print(f"{run['test_run_id']}: {run['workflow_count']} workflows")

# Load specific test run
data = load_test_run("performance_20260104_093000_abc123", "aws-ecs")

# Load latest test run
data = load_test_run(None, "aws-ecs")  # None = latest
```

## Integration Points

### 1. ScenarioRunner (Automatic)
- Creates TestRunTracker when test starts
- Adds job_name to all workflow inputs
- Saves tracking data when test ends

### 2. Build Workflow
The `build_job.yml` workflow accepts the `job_name` input:
```yaml
inputs:
  job_name:
    description: 'Custom job identifier'
    required: false
    type: string
    default: 'build'
```

### 3. Analysis Tools
- `analyze_specific_test.py` - Analyze specific test runs
- `generate_report.py` - Generate reports for tracked test runs

## Troubleshooting

### Q: My workflows aren't being tagged
**A**: Check that:
1. You're using the latest version of `run_tests.py`
2. The workflow accepts `job_name` input
3. The TestRunTracker is being initialized (check logs for "Test Run ID:")

### Q: Can't find my test run
**A**:
1. Check the tracking directory: `test_results/{environment}/tracking/`
2. Use `--list` to see all available test runs
3. Check that the test completed (tracking saves in finally block)

### Q: Workflows show wrong job_name
**A**: The job_name should be the test_run_id. If it shows "build" or another value:
1. The tracking integration may not be active
2. Check ScenarioRunner initialization logs

## Future Enhancements

1. **Direct Workflow ID Tracking**: Update tracker with actual workflow IDs from GitHub API
2. **Input Verification**: Query workflow inputs via API to verify job_name tags
3. **Real-time Updates**: Update tracking file during test, not just at end
4. **Web UI**: Create dashboard to browse and compare test runs
5. **Metrics Correlation**: Automatically correlate infrastructure metrics with test runs