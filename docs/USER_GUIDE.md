# GitHub Runner Performance Testing Harness

## User Guide

A portable test harness for evaluating GitHub runner performance, scalability, and capacity. Designed to work across different environments (AWS ECS, OpenShift) with minimal configuration changes.

---

## Quick Start

### Prerequisites
- Python 3.11+
- GitHub Personal Access Token with `workflow` scope
- Self-hosted GitHub runners (ECS Fargate or OpenShift)

### Running a Test

```bash
# Set your GitHub token
export GITHUB_TOKEN="your_token_here"

# Run a test profile
python run_tests.py -e aws_ecs -p performance

# Run with specific workload type
python run_tests.py -e aws_ecs -p capacity -w standard
```

### Available Test Profiles

| Profile | Duration | Pattern | Purpose |
|---------|----------|---------|---------|
| `validation` | 5 min | steady | Quick validation |
| `performance` | 30 min | steady | Baseline metrics |
| `capacity` | 60 min | steady | Max throughput |
| `load` | 120 min | steady | Sustained operation |
| `stress` | 45 min | burst | Burst handling |
| `spike` | 60 min | spike | Traffic spike response |

Fast variants (`performance_fast`, `capacity_fast`, etc.) are available for quick validation.

### Workload Types

| Type | Duration | Use Case |
|------|----------|----------|
| `test` | 30-60 sec | Quick validation |
| `light` | 2-3 min | Light CI jobs |
| `standard` | 3-5 min | Typical CI/CD |
| `heavy` | 5-8 min | Complex builds |

---

## Architecture

### File Structure

```
pythonProject/
├── .github/workflows/
│   └── build_job.yml           # Primary test workflow
├── config/
│   ├── base_config.yaml        # Base configuration
│   └── environments/
│       ├── aws_ecs.yaml        # AWS ECS environment
│       └── openshift_prod.yaml # OpenShift environment
├── src/
│   ├── orchestrator/
│   │   ├── environment_switcher.py  # Config loader
│   │   ├── scenario_runner.py       # Test executor
│   │   └── workflow_tracker.py      # GitHub API tracker
│   └── analysis/
│       └── test_specific_analyzer.py # Results analyzer
├── run_tests.py                # Main entry point
└── test_results/               # Output directory
```

### How It Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  run_tests.py   │────▶│EnvironmentSwitcher│────▶│  Load Config    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Test Results   │◀────│  ScenarioRunner  │◀────│  Test Profile   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │ GitHub API       │
                        │ (workflow_dispatch)│
                        └──────────────────┘
```

1. **run_tests.py** - Entry point, parses CLI arguments
2. **EnvironmentSwitcher** - Loads and parses environment config
3. **ScenarioRunner** - Executes test profile, dispatches workflows
4. **WorkflowTracker** - Tracks workflow runs via GitHub API
5. **Analyzer** - Generates analysis and recommendations

---

## Configuration System

### Environment Configuration (`config/environments/*.yaml`)

Each environment has its own configuration file. The key sections are:

#### 1. Environment Info
```yaml
environment:
  name: aws-ecs
  description: AWS ECS Fargate GitHub Runners
  type: test
```

#### 2. GitHub Settings
```yaml
github:
  owner: your-org
  repo: your-repo
  runner_labels:
    - self-hosted
    - ecs-fargate
    - aws
    - linux
```

#### 3. Runner Configuration
```yaml
runners:
  count: 4                    # Number of runners
  max_job_duration: 3600      # Timeout in seconds
```

#### 4. Primary Workflow (PORTABLE)
```yaml
workflows:
  directory: .github/workflows

  # CHANGE THIS FOR DIFFERENT ENVIRONMENTS
  primary:
    name: default
    file: build_job.yml       # ← Change this for OpenShift
    description: Primary test workflow

  workload_types:
    test:
      duration_range: "30-60s"
    standard:
      duration_range: "3-5min"
    # ... etc
```

#### 5. Test Profiles
```yaml
test_profiles:
  performance:
    duration_minutes: 30
    dispatch_pattern: steady
    jobs_per_minute: 1.2
    workload_inputs:
      workload_type: standard
```

### How Configuration is Loaded

1. `EnvironmentSwitcher` reads the YAML file
2. Parses `workflows.primary` to get the workflow file
3. Test profiles automatically use the primary workflow
4. `ScenarioRunner` uses the config to dispatch workflows

```python
# Simplified flow
switcher = EnvironmentSwitcher()
env = switcher.load_environment('aws_ecs')

# env.workflows = [WorkflowConfig(name='default', file='build_job.yml')]
# env.test_profiles['performance'].workflows = ['default']
```

---

## Switching Environments

### From AWS ECS to OpenShift

1. **Edit `config/environments/openshift_prod.yaml`**:
```yaml
workflows:
  primary:
    file: your_openshift_workflow.yml  # Your workflow file
```

2. **Update runner labels**:
```yaml
github:
  runner_labels:
    - self-hosted
    - openshift
    - linux
```

3. **Run tests**:
```bash
python run_tests.py -e openshift_prod -p performance
```

That's it! All test profiles automatically use the new workflow.

---

## Key Files Explained

### `.github/workflows/build_job.yml`

The primary test workflow. Accepts inputs:
- `workload_type`: test, light, standard, heavy
- `enable_randomization`: true/false
- `job_name`: Used for tracking (auto-generated)

The workflow simulates CI/CD work using sleep commands based on workload type.

### `src/orchestrator/environment_switcher.py`

Loads and parses environment configuration:
- Supports both old (`workflows.available[]`) and new (`workflows.primary`) config structures
- Test profiles without explicit workflow lists default to the primary workflow
- Validates workflow files exist

### `src/orchestrator/scenario_runner.py`

Executes test profiles:
- Dispatches workflows via GitHub API
- Tracks workflow status and metrics
- Waits for all workflows to complete
- Generates reports

### `src/orchestrator/workflow_tracker.py`

Tracks GitHub workflow runs:
- Uses baseline run_id approach to match dispatches with runs
- Calculates queue time at **job level** (not workflow level)
- Queue time = `job.started_at - job.created_at`

### `src/analysis/test_specific_analyzer.py`

Analyzes results by test type:
- Performance: baseline metrics, SLA recommendations
- Capacity: throughput, saturation analysis
- Load: degradation patterns, sustainability
- Stress: breaking points, resilience
- Spike: elasticity, recovery quality

---

## Metrics Collected

| Metric | Description | Source |
|--------|-------------|--------|
| Queue Time | Time waiting for runner | `job.started_at - job.created_at` |
| Execution Time | Time running on runner | `job.completed_at - job.started_at` |
| Total Time | End-to-end duration | Queue + Execution |
| Runner Utilization | % of runners busy | Active jobs / Runner count |
| Throughput | Jobs completed per hour | Calculated from results |

---

## Output Files

After each test run:

```
test_results/aws-ecs/
├── test_report_YYYYMMDD_HHMMSS.json      # Main results
├── enhanced_report_*.json                 # Detailed metrics
├── analysis/
│   └── *_analysis.json                    # Test-specific analysis
└── tracking/
    └── *.json                             # Workflow tracking data
```

---

## Troubleshooting

### "Workflow not found" error
- Check that `workflows.primary.file` matches an actual file in `.github/workflows/`

### Queue times showing 0
- Ensure workflow tracker is using job-level timestamps
- Check that workflows are actually completing (not timing out)

### Rate limit exceeded
- GitHub API has 5000 calls/hour limit
- Reduce polling frequency or test duration

### Workflows not completing
- Check runner status in GitHub Actions
- Verify runner labels match config

---

## Recent Changes (Portability Update)

### Before
- Workflow names hardcoded in 12+ places
- Each test profile listed `workflows: [build_job]`
- Multiple unused workflow files

### After
- Single `workflows.primary.file` configuration
- Test profiles automatically use primary workflow
- Clean workflow directory (only `build_job.yml`)
- Backwards compatible with old config structure

### Migration
If you have an old config with `workflows.available[]`, it still works. New configs should use:

```yaml
workflows:
  primary:
    file: your_workflow.yml
```
