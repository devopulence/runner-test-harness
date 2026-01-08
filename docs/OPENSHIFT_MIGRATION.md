# OpenShift Migration Plan

## Overview

This document outlines the steps required to migrate the GitHub Runner Performance Testing Harness from AWS ECS to OpenShift production environment.

---

## Pre-Migration Checklist

### 1. OpenShift Environment Requirements

- [ ] 4 GitHub Runner pods deployed and registered
- [ ] Runners have labels configured (e.g., `self-hosted`, `openshift`, `linux`)
- [ ] Network connectivity to GitHub API (direct or via proxy)
- [ ] GitHub PAT with `workflow` scope available

### 2. Workflow Requirements

- [ ] OpenShift-compatible workflow file created (or existing pipeline identified)
- [ ] Workflow accepts `workload_type` input parameter
- [ ] Workflow uses correct runner labels

---

## Migration Steps

### Step 1: Create OpenShift Environment Configuration

Create a new file `config/environments/openshift_prod.yaml`:

```yaml
# OpenShift Production Environment Configuration
environment:
  name: openshift-prod
  description: OpenShift Production GitHub Runners
  type: production

github:
  owner: your-org              # Your GitHub organization
  repo: your-repo              # Your repository
  runner_labels:
    - self-hosted
    - openshift
    - linux
    # Add any additional labels your OpenShift runners have

runners:
  count: 4                     # OpenShift has 4 runners
  max_job_duration: 3600

workflows:
  directory: .github/workflows

  # IMPORTANT: Update this to your OpenShift workflow
  primary:
    name: default
    file: openshift_pipeline.yml    # ← Your OpenShift workflow file
    description: OpenShift CI/CD pipeline

  workload_types:
    test:
      description: Fast jobs for validation
      duration_range: "30-60s"
    light:
      description: Light workload
      duration_range: "2-3min"
    standard:
      description: Standard CI/CD workload
      duration_range: "3-5min"
    heavy:
      description: Heavy build workload
      duration_range: "5-8min"

  default_inputs:
    enable_randomization: true

# Test profiles - automatically use the primary workflow above
test_profiles:
  validation:
    duration_minutes: 5
    dispatch_pattern: steady
    jobs_per_minute: 1.0
    workload_inputs:
      workload_type: test

  performance:
    duration_minutes: 30
    dispatch_pattern: steady
    jobs_per_minute: 1.2
    workload_inputs:
      workload_type: standard

  capacity:
    duration_minutes: 60
    dispatch_pattern: steady
    jobs_per_minute: 1.0
    workload_inputs:
      workload_type: standard

  load:
    duration_minutes: 120
    dispatch_pattern: steady
    jobs_per_minute: 0.8
    workload_inputs:
      workload_type: standard

  stress:
    duration_minutes: 45
    dispatch_pattern: burst
    burst_size: 8
    burst_interval: 900
    workload_inputs:
      workload_type: standard

  spike:
    duration_minutes: 60
    dispatch_pattern: spike
    normal_rate: 0.2
    spike_rate: 2.0
    spike_duration: 600
    spike_start: 1200
    workload_inputs:
      workload_type: standard

# Network configuration for corporate environment
network:
  proxy:
    enabled: true                           # Enable if behind proxy
    http_proxy: http://proxy.corp:8080      # Your proxy URL
    https_proxy: http://proxy.corp:8080
    no_proxy: localhost,127.0.0.1

  ssl:
    verify: true
    ca_bundle: /path/to/ca-bundle.crt       # Corporate CA bundle

# Logging
logging:
  level: INFO
  file: logs/openshift_prod_test.log
  console: true

# Metrics
metrics:
  collection_interval: 30
  github_api:
    enabled: true
    endpoints:
      - workflow_runs
      - jobs
      - runners

# Reporting
reporting:
  format: json
  output_directory: test_results/openshift-prod
```

### Step 2: Create or Adapt Workflow File

Option A: **Create a test workflow** (similar to `build_job.yml`)

```yaml
# .github/workflows/openshift_pipeline.yml
name: OpenShift Test Pipeline

on:
  workflow_dispatch:
    inputs:
      workload_type:
        description: 'Workload type'
        required: false
        default: 'standard'
        type: choice
        options:
          - test
          - light
          - standard
          - heavy
      enable_randomization:
        description: 'Enable duration randomization'
        required: false
        default: 'true'
        type: boolean
      job_name:
        description: 'Job name for tracking'
        required: false
        default: ''
        type: string

jobs:
  build:
    runs-on: [self-hosted, openshift, linux]  # ← Your OpenShift labels
    steps:
      - name: Simulate CI/CD Work
        run: |
          # Duration based on workload type
          case "${{ inputs.workload_type }}" in
            test)    BASE=45 ;;
            light)   BASE=150 ;;
            standard) BASE=240 ;;
            heavy)   BASE=390 ;;
            *)       BASE=240 ;;
          esac

          if [ "${{ inputs.enable_randomization }}" = "true" ]; then
            VARIANCE=$((BASE / 4))
            DURATION=$((BASE + RANDOM % VARIANCE - VARIANCE / 2))
          else
            DURATION=$BASE
          fi

          echo "Simulating ${{ inputs.workload_type }} workload for ${DURATION}s"
          sleep $DURATION
```

Option B: **Use existing pipeline** with modifications
- Add `workflow_dispatch` trigger with `workload_type` input
- Map workload types to different pipeline stages or configurations

### Step 3: Configure Network (If Needed)

If OpenShift environment requires proxy or custom certificates:

```bash
# Set environment variables before running tests
export HTTP_PROXY="http://proxy.corp:8080"
export HTTPS_PROXY="http://proxy.corp:8080"
export REQUESTS_CA_BUNDLE="/path/to/ca-bundle.crt"
```

Or configure in the YAML file (the harness applies these automatically).

### Step 4: Validate Setup

```bash
# Set GitHub token
export GITHUB_TOKEN="your_token_here"

# List available environments
python run_tests.py --list-environments

# Run quick validation test
python run_tests.py -e openshift_prod -p validation

# Check results
ls test_results/openshift-prod/
```

### Step 5: Run Full Test Suite

```bash
# Performance baseline (30 min)
python run_tests.py -e openshift_prod -p performance

# Capacity test (60 min)
python run_tests.py -e openshift_prod -p capacity

# Load test (120 min)
python run_tests.py -e openshift_prod -p load

# Stress test (45 min)
python run_tests.py -e openshift_prod -p stress

# Spike test (60 min)
python run_tests.py -e openshift_prod -p spike
```

---

## Configuration Changes Summary

| What to Change | Where | Example |
|----------------|-------|---------|
| Workflow file | `workflows.primary.file` | `openshift_pipeline.yml` |
| Runner labels | `github.runner_labels` | `[self-hosted, openshift, linux]` |
| GitHub org/repo | `github.owner`, `github.repo` | Your values |
| Proxy settings | `network.proxy.*` | Corporate proxy URLs |
| CA certificate | `network.ssl.ca_bundle` | Path to cert bundle |

---

## What Does NOT Need to Change

- Test profile definitions (duration, patterns, rates)
- Analysis logic
- Metrics collection
- Report generation
- The harness code itself

The harness is designed to be portable. Only configuration changes are needed.

---

## Comparing Results

After running tests in both environments, compare:

| Metric | AWS ECS | OpenShift | Notes |
|--------|---------|-----------|-------|
| Mean Queue Time | X sec | Y sec | Lower is better |
| P95 Queue Time | X sec | Y sec | Consistency indicator |
| Max Queue Time | X sec | Y sec | Worst case |
| Throughput | X jobs/hr | Y jobs/hr | Capacity indicator |
| Success Rate | X% | Y% | Should be 100% |

Key questions to answer:
1. Does OpenShift have similar capacity to the AWS simulation?
2. Are queue times acceptable for your CI/CD SLAs?
3. Where is the breaking point for concurrent jobs?

---

## Troubleshooting

### Runners Not Picking Up Jobs

1. Check runner labels match config:
   ```bash
   # In GitHub repo settings → Actions → Runners
   # Verify labels match github.runner_labels in config
   ```

2. Verify runners are online and idle

### Network/Proxy Issues

1. Test GitHub API connectivity:
   ```bash
   curl -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/repos/OWNER/REPO/actions/runners
   ```

2. Check proxy configuration in environment

### Workflow Not Found

1. Verify `workflows.primary.file` matches actual filename
2. Check workflow is in `.github/workflows/` directory
3. Ensure workflow has `workflow_dispatch` trigger

---

## Rollback Plan

If issues arise, you can always:
1. Switch back to AWS ECS environment:
   ```bash
   python run_tests.py -e aws_ecs -p validation
   ```
2. The harness maintains separate result directories per environment
3. No changes are made to the production systems - only workflow dispatches

---

## Timeline Estimate

| Phase | Tasks |
|-------|-------|
| Setup | Create config, deploy/identify workflow, verify runners |
| Validation | Run validation test, verify metrics collection |
| Full Testing | Run all 5 test profiles (~5.25 hours) |
| Analysis | Review results, compare with AWS baseline |