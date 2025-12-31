# GitHub Runner Performance Testing Harness - Architecture Design

## Executive Summary

This document outlines the architecture and design for a comprehensive GitHub Runner Performance Testing Harness. The system is designed to test various performance characteristics of GitHub workflow runners, initially targeting publicly hosted runners with future adaptation for self-hosted runners on OpenShift.

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Orchestrator                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐        │
│  │ Test Manager │  │ Load Generator│  │ Metrics Collector│      │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────┘        │
└─────────┼──────────────────┼──────────────────┼────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub API Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐        │
│  │Workflow      │  │Actions       │  │Repository      │        │
│  │Dispatch API  │  │Status API    │  │Metrics API     │        │
│  └──────────────┘  └──────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Runners                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐        │
│  │Public Runners│  │Self-Hosted   │  │OpenShift       │        │
│  │(Phase 1)     │  │Runners       │  │Runners (Phase 2)│        │
│  └──────────────┘  └──────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### Component Descriptions

#### 1. Test Orchestrator
**Purpose**: Central control system for managing and coordinating all test activities

**Sub-components**:
- **Test Manager**: Orchestrates test execution, manages test configurations
- **Load Generator**: Creates and manages concurrent workflow dispatches
- **Metrics Collector**: Gathers performance data from GitHub APIs and workflow logs

#### 2. GitHub API Layer
**Purpose**: Interface layer for all GitHub API interactions

**Endpoints Used**:
- `/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` - Trigger workflows
- `/repos/{owner}/{repo}/actions/runs` - Monitor workflow status
- `/repos/{owner}/{repo}/actions/runs/{run_id}` - Get detailed run information
- `/repos/{owner}/{repo}/actions/runs/{run_id}/timing` - Get timing metrics
- `/rate_limit` - Monitor API rate limits

#### 3. Test Workflows Repository
**Purpose**: Contains standardized test workflows for different scenarios

## Testing Strategies

### 1. Performance Testing
```python
class PerformanceTest:
    """Baseline performance metrics collection"""

    metrics = {
        "workflow_queue_time": "Time from dispatch to runner pickup",
        "workflow_execution_time": "Total execution time",
        "job_startup_time": "Time to initialize runner environment",
        "step_execution_times": "Individual step timings",
        "resource_utilization": "CPU/Memory/Disk metrics if available"
    }

    test_parameters = {
        "workflow_complexity": ["simple", "medium", "complex"],
        "job_count": [1, 5, 10],
        "step_count": [5, 20, 50],
        "artifact_sizes": ["1MB", "100MB", "1GB"]
    }
```

### 2. Load Testing
```python
class LoadTest:
    """Test runner behavior under expected load"""

    scenarios = {
        "steady_load": {
            "workflows_per_minute": 10,
            "duration_minutes": 60,
            "workflow_type": "standard"
        },
        "business_hours": {
            "workflows_per_minute": 25,
            "duration_minutes": 480,  # 8 hours
            "workflow_type": "mixed"
        }
    }
```

### 3. Spike Testing
```python
class SpikeTest:
    """Test sudden load increases"""

    scenarios = {
        "deployment_spike": {
            "baseline_load": 5,  # workflows/min
            "spike_load": 100,   # workflows/min
            "spike_duration": 5,  # minutes
            "recovery_monitoring": 30  # minutes
        }
    }
```

### 4. Stress Testing
```python
class StressTest:
    """Find breaking points"""

    approach = {
        "initial_load": 10,  # workflows/min
        "increment": 10,     # increase per step
        "step_duration": 10,  # minutes per load level
        "failure_criteria": [
            "workflow_timeout > 30min",
            "queue_depth > 100",
            "failure_rate > 10%"
        ]
    }
```

### 5. Volume Testing
```python
class VolumeTest:
    """Large-scale data processing"""

    test_cases = {
        "large_artifacts": {
            "artifact_count": 100,
            "artifact_size": "500MB",
            "parallel_uploads": 10
        },
        "log_volume": {
            "log_lines_per_step": 10000,
            "parallel_jobs": 20
        }
    }
```

### 6. Capacity Testing
```python
class CapacityTest:
    """Maximum concurrent workflow handling"""

    measurements = {
        "max_concurrent_workflows": "Find saturation point",
        "max_concurrent_jobs": "Per workflow limit",
        "queue_capacity": "Maximum pending workflows",
        "resource_limits": "Runner resource constraints"
    }
```

## Implementation Plan

### Phase 1: Foundation (Current)
1. **Core Testing Framework**
   - Extend `main.py` to support batch dispatching
   - Implement concurrent workflow management
   - Add retry and error handling logic

2. **Test Workflow Templates**
   - Create standardized test workflows
   - Variable complexity levels
   - Configurable resource consumption

3. **Metrics Collection**
   - GitHub API polling for run status
   - Timing data extraction
   - Result aggregation

### Phase 2: Test Scenarios
1. **Test Configuration System**
   ```python
   # test_config.yaml
   test:
     name: "baseline_performance"
     type: "performance"
     parameters:
       workflows: 10
       complexity: "medium"
       parallel: true
     metrics:
       - queue_time
       - execution_time
       - success_rate
   ```

2. **Load Generation Engine**
   ```python
   class LoadGenerator:
       def __init__(self, config):
           self.config = config
           self.session_pool = self._create_session_pool()

       async def generate_load(self, pattern):
           """Generate load based on pattern (steady, spike, ramp)"""
           pass

       async def dispatch_workflow(self, workflow_config):
           """Dispatch single workflow with tracking"""
           pass
   ```

3. **Metrics Collector**
   ```python
   class MetricsCollector:
       def __init__(self, github_client):
           self.github = github_client
           self.metrics_db = []

       async def collect_run_metrics(self, run_id):
           """Collect all metrics for a workflow run"""
           pass

       def aggregate_metrics(self):
           """Calculate statistics across all runs"""
           pass
   ```

### Phase 3: Analysis & Reporting
1. **Real-time Dashboard**
   - Live metrics visualization
   - Queue depth monitoring
   - Success/failure rates
   - Performance trends

2. **Report Generation**
   - Test summary reports
   - Performance baselines
   - Bottleneck identification
   - Recommendations

### Phase 4: OpenShift Adaptation
1. **Environment Configuration**
   - Self-hosted runner detection
   - OpenShift-specific metrics
   - Resource constraint handling

2. **Scaled Testing**
   - Adjust for 4-runner capacity
   - Queue management strategies
   - Optimal workload distribution

## Test Workflow Examples

### Simple Test Workflow
```yaml
name: Simple Performance Test
on:
  workflow_dispatch:
    inputs:
      test_id:
        description: 'Unique test identifier'
        required: true
      complexity:
        description: 'Test complexity level'
        default: 'simple'

jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - name: Start Timer
        run: echo "START_TIME=$(date +%s)" >> $GITHUB_ENV

      - name: Simulate Work
        run: |
          case "${{ inputs.complexity }}" in
            simple) sleep 10 ;;
            medium) sleep 30 ;;
            complex) sleep 60 ;;
          esac

      - name: Generate Test Data
        run: dd if=/dev/urandom of=test.dat bs=1M count=10

      - name: Process Data
        run: |
          sha256sum test.dat
          gzip test.dat

      - name: Report Metrics
        run: |
          END_TIME=$(date +%s)
          DURATION=$((END_TIME - START_TIME))
          echo "Test ID: ${{ inputs.test_id }}"
          echo "Duration: ${DURATION}s"
```

### Parallel Jobs Test
```yaml
name: Parallel Capacity Test
on:
  workflow_dispatch:
    inputs:
      job_count:
        description: 'Number of parallel jobs'
        default: '5'

jobs:
  generate-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.set-matrix.outputs.matrix }}
    steps:
      - id: set-matrix
        run: |
          matrix=$(seq 1 ${{ inputs.job_count }} | jq -R . | jq -s -c .)
          echo "matrix=${matrix}" >> $GITHUB_OUTPUT

  parallel-job:
    needs: generate-matrix
    runs-on: ubuntu-latest
    strategy:
      matrix:
        job_id: ${{ fromJson(needs.generate-matrix.outputs.matrix) }}
      max-parallel: 10
    steps:
      - name: Execute Job ${{ matrix.job_id }}
        run: |
          echo "Starting job ${{ matrix.job_id }}"
          sleep $((RANDOM % 30 + 10))
          echo "Completed job ${{ matrix.job_id }}"
```

## Data Collection & Storage

### Metrics Database Schema
```python
# Using SQLite for simplicity, can scale to PostgreSQL
metrics_schema = {
    "test_runs": {
        "id": "UUID PRIMARY KEY",
        "test_name": "TEXT",
        "test_type": "TEXT",  # performance, load, spike, etc.
        "started_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "configuration": "JSON"
    },
    "workflow_runs": {
        "id": "INTEGER PRIMARY KEY",
        "test_run_id": "UUID REFERENCES test_runs(id)",
        "workflow_id": "TEXT",
        "github_run_id": "INTEGER",
        "dispatched_at": "TIMESTAMP",
        "started_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "queue_time_seconds": "REAL",
        "execution_time_seconds": "REAL",
        "status": "TEXT",  # success, failure, cancelled
        "error_message": "TEXT"
    },
    "job_metrics": {
        "id": "INTEGER PRIMARY KEY",
        "workflow_run_id": "INTEGER REFERENCES workflow_runs(id)",
        "job_name": "TEXT",
        "started_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "duration_seconds": "REAL",
        "runner_type": "TEXT"
    }
}
```

## Configuration Management

### Main Configuration File
```yaml
# config/test_harness.yaml
github:
  owner: "your-org"
  repo: "test-workflows"
  token: "${GITHUB_TOKEN}"

runners:
  type: "public"  # or "self-hosted"
  labels: []      # for self-hosted runner selection

tests:
  performance:
    enabled: true
    workflows:
      - simple_test.yml
      - medium_test.yml
      - complex_test.yml

  load:
    enabled: true
    steady_state_rpm: 10  # requests per minute
    peak_rpm: 50

  stress:
    enabled: true
    max_rpm: 200
    increment_step: 10

monitoring:
  poll_interval: 5  # seconds
  timeout: 3600     # seconds

reporting:
  output_format: ["json", "html", "csv"]
  dashboard_port: 8080
```

## Error Handling & Recovery

### Failure Scenarios
1. **API Rate Limiting**
   - Implement exponential backoff
   - Distribute requests across time
   - Monitor rate limit headers

2. **Workflow Failures**
   - Categorize failure types
   - Implement retry logic for transient failures
   - Log detailed error information

3. **Network Issues**
   - Connection pooling with retry
   - Timeout configuration
   - Proxy/CA certificate handling

4. **Runner Unavailability**
   - Queue monitoring
   - Timeout detection
   - Fallback strategies

## Success Metrics

### Key Performance Indicators (KPIs)
1. **Runner Efficiency**
   - Average queue time
   - Workflow completion rate
   - Resource utilization

2. **Scalability Metrics**
   - Maximum concurrent workflows
   - Queue saturation point
   - Performance degradation curve

3. **Reliability Metrics**
   - Success rate under load
   - Recovery time from failures
   - Error rate by type

## Next Steps

1. **Immediate Actions**
   - Extend `main.py` with batch dispatch capability
   - Create test workflow repository
   - Implement basic metrics collection

2. **Short-term (1-2 weeks)**
   - Build load generation engine
   - Develop test configuration system
   - Create initial test scenarios

3. **Medium-term (1 month)**
   - Implement full metrics collection
   - Build reporting dashboard
   - Complete all test type implementations

4. **Long-term**
   - OpenShift adaptation
   - Advanced analytics
   - Predictive performance modeling