# GitHub Runner Performance Test Harness

## Overview

A portable performance testing harness designed to evaluate GitHub runners in environments with a **4-runner constraint**. Originally developed for testing AWS ECS Fargate runners, this harness is designed to be **portable to OpenShift production environments**.

### Key Features
- **Portable Design**: Works identically in AWS ECS and OpenShift environments
- **Realistic Workload Simulation**: Uses sleep-based workflows with randomization to simulate real CI/CD workloads (5-30 minute durations)
- **7 Test Types**: Performance, Scalability, Load, Stress, Spike, Volume, and Capacity testing
- **4-Runner Constraint Testing**: Specifically designed to test environments with exactly 4 runners
- **Environment Switching**: Easy configuration-based switching between environments
- **No Cloud Dependencies**: Pure GitHub Actions implementation for maximum portability

## Quick Start

### Prerequisites
1. GitHub repository with 4 self-hosted runners configured
2. GitHub Personal Access Token (PAT) with `repo`, `workflow`, and `actions:read` permissions
3. Python 3.7+

### Installation
```bash
# Install dependencies
make setup
# or
pip install requests urllib3 pyyaml

# Set GitHub token
export GITHUB_TOKEN='ghp_your_token_here'
```

### Run Your First Test

#### AWS ECS Environment (Default)
```bash
# Quick performance test
make test-aws

# Or using the Python script directly
python run_tests.py -e aws_ecs -t performance
```

#### OpenShift Environment
```bash
# First, update config/environments/openshift_prod.yaml with your settings
# Then run:
make test-openshift

# Or
python run_tests.py -e openshift_prod -t performance
```

## Test Types

### 1. Performance Test
Baseline performance measurement to establish normal operating metrics.
```bash
make test-performance
```

### 2. Capacity Test
Determines maximum throughput with 4-runner constraint.
```bash
make test-capacity
```

### 3. Stress Test
Tests beyond normal capacity to find breaking points.
```bash
make test-stress
```

### 4. Load Test
Sustained load testing for stability verification.
```bash
make test-load
```

### 5. Spike Test
Tests system response to sudden traffic spikes.
```bash
make test-spike
```

## Workflows

The harness includes 5 realistic workflow templates in `.github/workflows/realistic/`:

1. **build_job.yml** - Simulates CI build process (5-30 min)
2. **deployment_pipeline.yml** - Simulates deployment to environments (7-30 min)
3. **security_scan.yml** - Simulates security scanning (6-30 min)
4. **multi_stage_pipeline.yml** - Complex multi-job pipeline for testing parallelism
5. **container_pipeline.yml** - Container build/push simulation (Docker-in-Docker)

Each workflow includes:
- Randomized durations (±20% variance)
- Configurable workload types (light/standard/heavy)
- Realistic phase simulation (compile, test, artifact creation, etc.)

## Configuration

### Environment Configuration
Environments are configured in YAML files under `config/environments/`:

- `aws_ecs.yaml` - AWS ECS Fargate configuration
- `openshift_prod.yaml` - OpenShift production configuration

Key configuration sections:
```yaml
environment:
  name: aws-ecs
  runner_count: 4  # Hard limit

github:
  owner: YourOrg
  repo: YourRepo
  runner_labels:
    - self-hosted
    - ecs-fargate

test_profiles:
  performance:
    duration_minutes: 30
    workflows: [build_job]
    jobs_per_minute: 0.5
```

### Switching Environments
```bash
# Set environment variable
export TEST_ENV=openshift_prod

# Run test with specific environment
python run_tests.py -e openshift_prod -t performance
```

## Interactive Mode

For a guided experience:
```bash
make interactive
# or
python run_tests.py -i
```

This will:
1. List available environments
2. Let you select an environment
3. Show available test profiles
4. Run selected tests
5. Display results

## Understanding Results

### Metrics Collected
- **Queue Time**: Time jobs wait for available runner
- **Execution Time**: Time jobs take to complete
- **Throughput**: Jobs completed per hour
- **Runner Utilization**: Percentage of time runners are busy
- **Concurrent Jobs**: Number of jobs running simultaneously

### Sample Output
```
TEST RESULTS SUMMARY
====================
Workflows:
  Total: 24
  Successful: 23
  Failed: 1
  Success Rate: 95.8%

Queue Time (seconds):
  Min: 5.2
  Max: 187.3
  Mean: 42.7
  Median: 31.5
  P95: 156.2

Runner Utilization:
  Average: 87.3%
  Peak: 100.0%

Test Duration: 30.2 minutes
```

### Reports
Reports are saved to `test_results/<environment>/test_report_YYYYMMDD_HHMMSS.json`

## OpenShift Deployment

### 1. Prepare OpenShift Environment
Ensure your OpenShift cluster has 4 GitHub runners configured with appropriate labels.

### 2. Update Configuration
Edit `config/environments/openshift_prod.yaml`:
```yaml
github:
  owner: YourOrg  # Your GitHub organization
  repo: YourRepo  # Your repository

network:
  proxy:
    enabled: true
    http_proxy: "http://your-proxy:8080"
  ssl:
    ca_bundle: "/path/to/ca-cert.crt"
```

### 3. Test Connectivity
```bash
# Validate configuration
python run_tests.py -e openshift_prod --dry-run
```

### 4. Run Tests
```bash
# Start with performance baseline
python run_tests.py -e openshift_prod -t performance

# Then run capacity test
python run_tests.py -e openshift_prod -t capacity
```

## Safety Features

For production environments:
- **Dry Run Mode**: Validate without running tests
- **Rate Limiting**: Configurable job dispatch rates
- **Abort Capability**: Ctrl+C to stop tests gracefully
- **Failure Limits**: Auto-stop on high failure rates
- **Cooldown Periods**: Time between test profiles

## Troubleshooting

### Common Issues

1. **"GITHUB_TOKEN not set"**
   ```bash
   export GITHUB_TOKEN='ghp_your_token_here'
   ```

2. **"Workflow file not found"**
   Ensure workflows are pushed to your repository:
   ```bash
   git add .github/workflows/realistic/
   git commit -m "Add test workflows"
   git push
   ```

3. **"No runners available"**
   Check runners are online:
   - GitHub UI: Settings → Actions → Runners
   - Verify runner labels match configuration

4. **Corporate Proxy Issues**
   Update `openshift_prod.yaml` with proxy settings:
   ```yaml
   network:
     proxy:
       enabled: true
       http_proxy: "http://proxy:8080"
       https_proxy: "http://proxy:8080"
       no_proxy: "localhost,127.0.0.1"
   ```

## Advanced Usage

### Custom Test Profiles
Add to environment configuration:
```yaml
test_profiles:
  my_custom_test:
    duration_minutes: 45
    workflows: [build_job, security_scan]
    dispatch_pattern: steady
    jobs_per_minute: 1.5
```

Run with:
```bash
python run_tests.py -e aws_ecs -p my_custom_test
```

### Continuous Testing
For ongoing monitoring:
```bash
# Run test every hour
while true; do
  python run_tests.py -e aws_ecs -t performance
  sleep 3600
done
```

## Key Design Decisions

1. **Sleep-based Simulation**: Realistic timing without actual build overhead
2. **Randomization**: ±20% variance to simulate real-world variability
3. **Configuration-driven**: Easy environment switching via YAML
4. **No Cloud Dependencies**: Pure GitHub Actions for portability
5. **4-Runner Focus**: Specifically designed for constrained environments

## Next Steps

1. **Baseline in Test Environment**: Run full test suite on AWS ECS
2. **Deploy to OpenShift**: Move harness to production environment
3. **Measure Capacity**: Determine if 4 runners are sufficient
4. **Optimize**: Adjust runner count or workflow design based on results

## Support

For issues or questions:
- Check `logs/` directory for detailed logs
- Review workflow run history in GitHub Actions
- Validate configuration with `--dry-run`

## License

This test harness is provided as-is for testing GitHub runner performance in constrained environments.