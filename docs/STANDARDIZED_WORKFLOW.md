# Standardized Test Workflow Documentation

## Overview
The `build_job.yml` workflow provides a standardized, configurable workflow for all GitHub runner performance testing. It simulates realistic CI/CD pipeline operations with configurable durations and workload types.

## Workflow Location
- **File**: `.github/workflows/build_job.yml`
- **Name**: `Realistic Build Job`

## Configuration Options

### Input Parameters

#### 1. workload_type (required)
Determines the duration and intensity of the simulated build:

| Type | Duration Range | Use Case |
|------|---------------|----------|
| `test` | 30-60 seconds | Quick validation, capacity testing |
| `light` | 2-3 minutes | Light CI jobs, unit tests only |
| `standard` | 3-5 minutes | Typical CI/CD builds |
| `heavy` | 5-8 minutes | Complex builds with extensive testing |

#### 2. enable_randomization (optional, default: true)
- `true`: Adds realistic variance within the duration range
- `false`: Uses fixed base duration for consistent timing

#### 3. job_name (optional, default: 'build')
- Custom identifier for tracking specific job types
- Useful for differentiating multiple test scenarios

## Duration Configuration

### Location in Workflow
All durations are defined in a single location (lines 48-68 in `build_job.yml`):

```bash
case "${{ inputs.workload_type }}" in
  test)
    BASE=45     # 45 seconds
    MIN=30      # 30 seconds
    MAX=60      # 60 seconds
    ;;
  light)
    BASE=150    # 2.5 minutes
    MIN=120     # 2 minutes
    MAX=180     # 3 minutes
    ;;
  standard)
    BASE=240    # 4 minutes
    MIN=180     # 3 minutes
    MAX=300     # 5 minutes
    ;;
  heavy)
    BASE=390    # 6.5 minutes
    MIN=300     # 5 minutes
    MAX=480     # 8 minutes
    ;;
esac
```

### Modifying Durations
To adjust timing for your environment:
1. Edit the `BASE`, `MIN`, and `MAX` values in seconds
2. All workflow phases automatically adjust proportionally
3. No other changes needed - phases scale automatically

## Workflow Phases

The workflow automatically distributes time across realistic CI/CD phases:

| Phase | Time Allocation | Activities Simulated |
|-------|----------------|---------------------|
| Initialization | Fixed ~5s | Workflow setup, environment prep |
| Dependencies | 15-30s | Package manager operations |
| Compilation | 30% | Source code compilation |
| Testing | 40% | Unit (40%), Integration (35%), E2E (25%) |
| Artifact Creation | 25% | Bundling, Docker images, documentation |
| Quality Gates | 5% | Coverage, security scans, compliance |

## Using for Different Test Types

### Performance Testing
```yaml
workload_type: standard
enable_randomization: true
```
- Establishes baseline performance metrics
- 3-5 minute builds simulate typical CI/CD

### Load Testing
```yaml
workload_type: standard
enable_randomization: true
```
- Same as performance but with sustained rate
- Tests system under expected production load

### Stress Testing
```yaml
workload_type: heavy
enable_randomization: true
```
- 5-8 minute builds increase resource usage
- Tests system limits and breaking points

### Spike Testing
Mix of workload types:
- Start with `light` (baseline)
- Spike to `heavy` (stress period)
- Return to `light` (recovery)

### Capacity Testing
```yaml
workload_type: test
enable_randomization: false
```
- 30-60 second jobs for maximum concurrency
- Tests how many parallel jobs can run

### Soak Testing
```yaml
workload_type: light
enable_randomization: true
```
- 2-3 minute jobs for extended duration
- Tests system stability over time

## Triggering the Workflow

### Via GitHub API
```python
payload = {
    "ref": "main",
    "inputs": {
        "workload_type": "standard",
        "enable_randomization": "true",
        "job_name": "perf-test-001"
    }
}
```

### Via GitHub UI
1. Navigate to Actions tab
2. Select "Realistic Build Job"
3. Click "Run workflow"
4. Select options from dropdown

### Via Test Harness
The test orchestrator automatically sets appropriate workload types based on test configuration.

## Metrics Collection

The workflow provides detailed timing information:

### Available Metrics
- **Total Duration**: Actual execution time
- **Phase Timing**: Each phase reports its duration
- **Variance**: Percentage deviation from base duration
- **Runner Info**: Which runner executed the job

### Output Format
```
===============================================
Build Simulation Complete
===============================================
Job: perf-test-001
Type: standard
Total Duration: 4m 23s
Variance from baseline: +3%
Runner: ecs-runner-abc123
Status: success
Completed: 2025-01-04 13:45:23 UTC
===============================================
```

## Best Practices

### 1. Consistent Testing
- Use the same `workload_type` for comparable results
- Document which type was used in test reports

### 2. Randomization
- Enable for realistic production simulation
- Disable for reproducible benchmark tests

### 3. Monitoring
- Track queue time vs execution time
- Monitor phase completion for bottlenecks

### 4. Scaling Tests
- Start with `test` type for quick validation
- Progress to `standard` for baseline metrics
- Use `heavy` only for stress testing

## Customization Guide

### Adding New Workload Types
To add a new workload type (e.g., "extreme" for 10+ minutes):

1. Add to workflow input options:
```yaml
options:
  - test
  - light
  - standard
  - heavy
  - extreme  # New option
```

2. Add case in duration calculation:
```bash
extreme)
  BASE=720    # 12 minutes
  MIN=600     # 10 minutes
  MAX=900     # 15 minutes
  ;;
```

### Adjusting Phase Distribution
To change how time is distributed across phases, modify the percentage calculations:

```bash
# Current distribution
COMPILE_TIME=$(( ${{ steps.duration.outputs.duration }} * 30 / 100 ))  # 30%
TEST_TIME=$(( ${{ steps.duration.outputs.duration }} * 40 / 100 ))     # 40%
ARTIFACT_TIME=$(( ${{ steps.duration.outputs.duration }} * 25 / 100 )) # 25%
QUALITY_TIME=$(( ${{ steps.duration.outputs.duration }} * 5 / 100 ))   # 5%
```

## Troubleshooting

### Jobs Running Too Fast/Slow
- Check `workload_type` setting
- Verify runner resources match expectations
- Review workflow logs for actual phase timings

### Inconsistent Timings
- Set `enable_randomization: false` for consistent durations
- Check for resource contention on runners

### Queue Time Issues
- Not a workflow issue - indicates runner capacity limits
- Expected behavior when dispatch rate exceeds runner availability

## Summary

This standardized workflow provides:
- **Flexibility**: 4 workload types cover all testing needs
- **Realism**: Simulates actual CI/CD pipeline phases
- **Consistency**: Single configuration point for all durations
- **Portability**: Works on any runner (GitHub-hosted or self-hosted)
- **Observability**: Detailed timing output for analysis

Use this single workflow for all performance, load, stress, and capacity testing to ensure consistent, comparable results across all test types.