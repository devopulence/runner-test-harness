# GitHub Runner Performance Testing Strategies

## Overview
This document provides detailed testing strategies and implementation guidelines for each type of performance test in the GitHub Runner Testing Harness.

## Test Strategy Matrix

| Test Type | Purpose | Key Metrics | Duration | Load Pattern |
|-----------|---------|-------------|----------|--------------|
| Performance | Baseline metrics | Queue/Execution time | 30-60 min | Steady |
| Load | Normal operations | Throughput, Success rate | 2-8 hours | Steady |
| Spike | Sudden load handling | Recovery time, Queue depth | 1-2 hours | Burst |
| Stress | Breaking point | Max capacity, Failure rate | 2-4 hours | Incremental |
| Volume | Data processing | Processing time, Memory usage | 1-3 hours | Steady |
| Capacity | Max concurrent | Saturation point, Resource limits | 2-4 hours | Incremental |

## 1. Performance Testing Strategy

### Objective
Establish baseline performance metrics for GitHub runners under controlled conditions.

### Test Scenarios

#### Scenario 1: Simple Workflow Performance
```python
test_config = {
    "name": "simple_workflow_baseline",
    "workflows": 10,
    "workflow_type": "simple",  # 5 steps, minimal processing
    "parallel": False,  # Sequential to get clean measurements
    "interval_seconds": 30,  # Time between dispatches
    "expected_metrics": {
        "queue_time": "< 10 seconds",
        "execution_time": "< 60 seconds",
        "total_time": "< 70 seconds"
    }
}
```

#### Scenario 2: Complex Workflow Performance
```python
test_config = {
    "name": "complex_workflow_baseline",
    "workflows": 10,
    "workflow_type": "complex",  # 20+ steps, data processing
    "parallel": False,
    "interval_seconds": 60,
    "expected_metrics": {
        "queue_time": "< 10 seconds",
        "execution_time": "< 300 seconds",
        "total_time": "< 310 seconds"
    }
}
```

#### Scenario 3: Parallel Jobs Performance
```python
test_config = {
    "name": "parallel_jobs_baseline",
    "workflows": 5,
    "jobs_per_workflow": 5,
    "parallel": True,
    "expected_metrics": {
        "job_parallelism": "> 3",  # Average parallel jobs
        "total_completion": "< 180 seconds"
    }
}
```

### Implementation
```python
class PerformanceTestRunner:
    def __init__(self, github_client, config):
        self.github = github_client
        self.config = config
        self.results = []

    async def run_test(self):
        """Execute performance test scenario"""
        for i in range(self.config["workflows"]):
            # Dispatch workflow
            run_id = await self.dispatch_workflow(
                workflow_type=self.config["workflow_type"]
            )

            # Collect metrics
            metrics = await self.collect_metrics(run_id)
            self.results.append(metrics)

            # Wait for interval
            await asyncio.sleep(self.config.get("interval_seconds", 30))

        return self.analyze_results()

    def analyze_results(self):
        """Calculate statistics from test results"""
        return {
            "avg_queue_time": self.calculate_average("queue_time"),
            "avg_execution_time": self.calculate_average("execution_time"),
            "p95_queue_time": self.calculate_percentile("queue_time", 95),
            "p95_execution_time": self.calculate_percentile("execution_time", 95),
            "success_rate": self.calculate_success_rate()
        }
```

## 2. Load Testing Strategy

### Objective
Validate system behavior under expected production load conditions.

### Test Scenarios

#### Scenario 1: Steady State Load
```python
load_test_config = {
    "name": "steady_state_load",
    "duration_minutes": 120,
    "workflows_per_minute": 15,
    "workflow_distribution": {
        "simple": 0.5,    # 50% simple workflows
        "medium": 0.3,    # 30% medium complexity
        "complex": 0.2    # 20% complex workflows
    },
    "success_criteria": {
        "success_rate": "> 95%",
        "avg_queue_time": "< 30 seconds",
        "p95_total_time": "< 300 seconds"
    }
}
```

#### Scenario 2: Business Hours Simulation
```python
business_hours_config = {
    "name": "business_hours_simulation",
    "duration_minutes": 480,  # 8 hours
    "load_pattern": [
        {"hour": 0, "workflows_per_minute": 5},   # Start of day
        {"hour": 1, "workflows_per_minute": 15},  # Ramp up
        {"hour": 2, "workflows_per_minute": 25},  # Morning peak
        {"hour": 3, "workflows_per_minute": 20},  # Mid-morning
        {"hour": 4, "workflows_per_minute": 15},  # Lunch
        {"hour": 5, "workflows_per_minute": 25},  # Afternoon peak
        {"hour": 6, "workflows_per_minute": 15},  # End of day
        {"hour": 7, "workflows_per_minute": 5}    # Wind down
    ]
}
```

### Implementation
```python
class LoadTestRunner:
    def __init__(self, github_client, config):
        self.github = github_client
        self.config = config
        self.active_runs = []
        self.completed_runs = []

    async def generate_steady_load(self):
        """Generate consistent load over time"""
        end_time = time.time() + (self.config["duration_minutes"] * 60)

        while time.time() < end_time:
            # Calculate workflows for this minute
            workflows_this_minute = self.config["workflows_per_minute"]

            # Dispatch workflows with proper spacing
            for i in range(workflows_this_minute):
                workflow_type = self.select_workflow_type()
                asyncio.create_task(self.dispatch_and_track(workflow_type))

                # Space out dispatches within the minute
                await asyncio.sleep(60 / workflows_this_minute)

            # Monitor active runs
            await self.monitor_active_runs()

    def select_workflow_type(self):
        """Select workflow type based on distribution"""
        rand = random.random()
        cumulative = 0
        for workflow_type, probability in self.config["workflow_distribution"].items():
            cumulative += probability
            if rand <= cumulative:
                return workflow_type
        return "simple"  # Default fallback
```

## 3. Spike Testing Strategy

### Objective
Assess system resilience to sudden load increases and recovery capability.

### Test Scenarios

#### Scenario 1: Deployment Spike
```python
deployment_spike_config = {
    "name": "deployment_spike",
    "phases": [
        {"name": "baseline", "duration_min": 30, "workflows_per_min": 5},
        {"name": "spike", "duration_min": 5, "workflows_per_min": 100},
        {"name": "recovery", "duration_min": 30, "workflows_per_min": 5}
    ],
    "monitoring": {
        "queue_depth_threshold": 50,
        "recovery_time_target": "< 10 minutes",
        "failure_tolerance": "< 5%"
    }
}
```

#### Scenario 2: Multi-Wave Spike
```python
multi_wave_config = {
    "name": "multi_wave_spike",
    "waves": 3,
    "wave_pattern": {
        "baseline_duration": 20,  # minutes
        "spike_duration": 3,      # minutes
        "spike_multiplier": 20    # 20x baseline load
    }
}
```

### Implementation
```python
class SpikeTestRunner:
    def __init__(self, github_client, config):
        self.github = github_client
        self.config = config
        self.metrics_timeline = []

    async def run_spike_test(self):
        """Execute spike test with monitoring"""
        for phase in self.config["phases"]:
            print(f"Starting phase: {phase['name']}")

            # Start monitoring task
            monitor_task = asyncio.create_task(
                self.monitor_system_metrics()
            )

            # Generate load for this phase
            await self.generate_phase_load(phase)

            # Stop monitoring
            monitor_task.cancel()

            # Analyze phase results
            self.analyze_phase(phase["name"])

    async def monitor_system_metrics(self):
        """Continuous monitoring during spike test"""
        while True:
            metrics = {
                "timestamp": datetime.now(),
                "queue_depth": await self.get_queue_depth(),
                "active_runs": await self.get_active_run_count(),
                "avg_queue_time": await self.get_avg_queue_time(),
                "failure_rate": await self.get_failure_rate()
            }
            self.metrics_timeline.append(metrics)
            await asyncio.sleep(10)  # Monitor every 10 seconds
```

## 4. Stress Testing Strategy

### Objective
Identify system breaking points and maximum sustainable load.

### Test Approach

#### Progressive Load Increase
```python
stress_test_config = {
    "name": "progressive_stress",
    "initial_load": 5,  # workflows/min
    "increment": 5,     # increase per step
    "step_duration": 15,  # minutes per load level
    "max_load": 200,    # safety limit
    "failure_conditions": [
        {"metric": "queue_time", "threshold": "> 300 seconds"},
        {"metric": "failure_rate", "threshold": "> 10%"},
        {"metric": "timeout_rate", "threshold": "> 5%"},
        {"metric": "api_errors", "threshold": "> 1%"}
    ]
}
```

### Implementation
```python
class StressTestRunner:
    def __init__(self, github_client, config):
        self.github = github_client
        self.config = config
        self.breaking_point = None

    async def find_breaking_point(self):
        """Progressively increase load until failure"""
        current_load = self.config["initial_load"]

        while current_load <= self.config["max_load"]:
            print(f"Testing load level: {current_load} workflows/min")

            # Run at this load level
            test_result = await self.test_load_level(
                current_load,
                self.config["step_duration"]
            )

            # Check failure conditions
            if self.check_failure_conditions(test_result):
                self.breaking_point = current_load
                print(f"Breaking point found at {current_load} workflows/min")
                break

            # Increase load
            current_load += self.config["increment"]

        return self.generate_stress_report()

    def check_failure_conditions(self, metrics):
        """Check if any failure condition is met"""
        for condition in self.config["failure_conditions"]:
            metric_value = metrics.get(condition["metric"])
            threshold = condition["threshold"]

            if self.evaluate_threshold(metric_value, threshold):
                print(f"Failure condition met: {condition}")
                return True
        return False
```

## 5. Volume Testing Strategy

### Objective
Test system capability to handle large volumes of data and artifacts.

### Test Scenarios

#### Scenario 1: Large Artifact Handling
```python
artifact_volume_config = {
    "name": "large_artifact_processing",
    "test_cases": [
        {
            "name": "many_small_artifacts",
            "artifact_count": 100,
            "artifact_size": "10MB",
            "parallel_uploads": 10
        },
        {
            "name": "few_large_artifacts",
            "artifact_count": 5,
            "artifact_size": "1GB",
            "parallel_uploads": 2
        },
        {
            "name": "mixed_artifacts",
            "artifacts": [
                {"count": 50, "size": "5MB"},
                {"count": 10, "size": "100MB"},
                {"count": 2, "size": "500MB"}
            ]
        }
    ]
}
```

#### Scenario 2: Log Volume Testing
```python
log_volume_config = {
    "name": "log_stress_test",
    "scenarios": [
        {
            "name": "verbose_logging",
            "log_lines_per_step": 10000,
            "steps": 20,
            "parallel_jobs": 5
        },
        {
            "name": "continuous_streaming",
            "stream_duration_seconds": 300,
            "lines_per_second": 100,
            "parallel_streams": 10
        }
    ]
}
```

### Test Workflow for Volume Testing
```yaml
name: Volume Test - Large Artifacts
on:
  workflow_dispatch:
    inputs:
      artifact_size_mb:
        description: 'Size of each artifact in MB'
        required: true
      artifact_count:
        description: 'Number of artifacts to create'
        required: true

jobs:
  generate-artifacts:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        artifact_id: ${{ fromJson(github.event.inputs.artifact_count) }}
    steps:
      - name: Generate Large File
        run: |
          dd if=/dev/urandom of=artifact_${{ matrix.artifact_id }}.dat \
             bs=1M count=${{ inputs.artifact_size_mb }}

      - name: Upload Artifact
        uses: actions/upload-artifact@v3
        with:
          name: test-artifact-${{ matrix.artifact_id }}
          path: artifact_${{ matrix.artifact_id }}.dat

  process-artifacts:
    needs: generate-artifacts
    runs-on: ubuntu-latest
    steps:
      - name: Download All Artifacts
        uses: actions/download-artifact@v3

      - name: Process Artifacts
        run: |
          total_size=$(du -sh . | cut -f1)
          echo "Total artifacts size: $total_size"
          find . -name "*.dat" -exec sha256sum {} \;
```

## 6. Capacity Testing Strategy

### Objective
Determine maximum concurrent workflow capacity and optimal load distribution.

### Test Approach

#### Concurrent Workflow Saturation
```python
capacity_test_config = {
    "name": "concurrent_saturation",
    "test_phases": [
        {"concurrent_workflows": 10, "duration_min": 10},
        {"concurrent_workflows": 20, "duration_min": 10},
        {"concurrent_workflows": 50, "duration_min": 10},
        {"concurrent_workflows": 100, "duration_min": 10},
        {"concurrent_workflows": 200, "duration_min": 10}
    ],
    "metrics": {
        "queue_saturation": "Point where queue starts growing",
        "optimal_concurrency": "Max workflows without degradation",
        "resource_limits": "CPU/Memory/Network bottlenecks"
    }
}
```

### Implementation
```python
class CapacityTestRunner:
    def __init__(self, github_client, config):
        self.github = github_client
        self.config = config
        self.capacity_metrics = []

    async def test_concurrent_capacity(self):
        """Test different levels of concurrency"""
        for phase in self.config["test_phases"]:
            concurrent = phase["concurrent_workflows"]
            print(f"Testing {concurrent} concurrent workflows")

            # Launch all workflows simultaneously
            tasks = []
            start_time = time.time()

            for i in range(concurrent):
                task = asyncio.create_task(
                    self.dispatch_and_monitor(f"workflow_{i}")
                )
                tasks.append(task)

            # Wait for all to complete or timeout
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Analyze results
            metrics = self.analyze_concurrent_results(
                results,
                concurrent,
                start_time
            )
            self.capacity_metrics.append(metrics)

            # Check if we've hit capacity limits
            if self.is_capacity_limit_reached(metrics):
                print(f"Capacity limit reached at {concurrent} workflows")
                break

            # Cool down period between phases
            await asyncio.sleep(60)

    def is_capacity_limit_reached(self, metrics):
        """Determine if system has reached capacity limits"""
        indicators = [
            metrics["avg_queue_time"] > 120,  # 2+ minute queue
            metrics["failure_rate"] > 0.1,     # 10%+ failures
            metrics["timeout_rate"] > 0.05,    # 5%+ timeouts
            metrics["queue_growth_rate"] > 0   # Queue growing
        ]
        return sum(indicators) >= 2  # At least 2 indicators
```

## Test Execution Framework

### Main Test Orchestrator
```python
class TestHarness:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.github = GitHubClient(self.config["github"])
        self.test_runners = {
            "performance": PerformanceTestRunner,
            "load": LoadTestRunner,
            "spike": SpikeTestRunner,
            "stress": StressTestRunner,
            "volume": VolumeTestRunner,
            "capacity": CapacityTestRunner
        }
        self.results = {}

    async def run_test_suite(self, test_types=None):
        """Execute requested test types"""
        test_types = test_types or self.config["enabled_tests"]

        for test_type in test_types:
            if test_type in self.test_runners:
                print(f"\n{'='*50}")
                print(f"Starting {test_type.upper()} testing")
                print('='*50)

                runner_class = self.test_runners[test_type]
                runner = runner_class(
                    self.github,
                    self.config["tests"][test_type]
                )

                self.results[test_type] = await runner.run_test()

                # Generate intermediate report
                self.generate_test_report(test_type)

        # Generate final comprehensive report
        self.generate_final_report()

    def generate_test_report(self, test_type):
        """Generate report for individual test type"""
        report = TestReport(test_type, self.results[test_type])
        report.save(f"reports/{test_type}_report.json")
        report.print_summary()

    def generate_final_report(self):
        """Generate comprehensive test suite report"""
        final_report = ComprehensiveReport(self.results)
        final_report.generate_html("reports/final_report.html")
        final_report.generate_csv("reports/metrics.csv")
        final_report.print_executive_summary()
```

## Monitoring & Alerting

### Real-time Monitoring
```python
class TestMonitor:
    def __init__(self, alert_config):
        self.alert_config = alert_config
        self.metrics_buffer = []

    async def monitor_test_execution(self):
        """Continuous monitoring during test execution"""
        while self.test_active:
            metrics = await self.collect_current_metrics()
            self.metrics_buffer.append(metrics)

            # Check alert conditions
            await self.check_alerts(metrics)

            # Update dashboard
            await self.update_dashboard(metrics)

            await asyncio.sleep(5)  # 5-second monitoring interval

    async def check_alerts(self, metrics):
        """Check and trigger alerts based on thresholds"""
        for alert in self.alert_config:
            if self.evaluate_alert_condition(alert, metrics):
                await self.send_alert(alert, metrics)
```

## Reporting Templates

### Executive Summary Report
```markdown
# GitHub Runner Performance Test Report

## Executive Summary
- **Test Period**: [Start] to [End]
- **Total Workflows Executed**: [Count]
- **Overall Success Rate**: [Percentage]
- **Peak Concurrent Workflows**: [Number]

## Key Findings
1. **Performance Baseline**
   - Average Queue Time: [Time]
   - Average Execution Time: [Time]
   - P95 Total Time: [Time]

2. **Capacity Limits**
   - Maximum Sustainable Load: [Workflows/min]
   - Breaking Point: [Workflows/min]
   - Optimal Concurrency: [Number]

3. **Recommendations**
   - [Recommendation 1]
   - [Recommendation 2]
   - [Recommendation 3]
```

## OpenShift Adaptation Considerations

### Adjustments for 4-Runner Capacity
```python
openshift_config = {
    "runner_capacity": 4,
    "test_adjustments": {
        "max_concurrent": 4,  # Cannot exceed runner count
        "queue_strategy": "depth_focused",  # Focus on queue behavior
        "load_pattern": "controlled",  # Careful load management
        "metrics_focus": [
            "queue_depth",
            "wait_time",
            "resource_utilization",
            "scheduling_efficiency"
        ]
    },
    "special_tests": [
        "runner_starvation",  # All runners busy scenarios
        "priority_handling",  # Job priority testing
        "recovery_time",      # Time to clear backed-up queue
        "optimal_batch_size"  # Best workflow batch size for 4 runners
    ]
}