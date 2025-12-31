# GitHub Runner Performance Testing - Setup Guide

## 🚀 Quick Setup for Devopulence/test-workflows

This guide will help you set up and run performance tests on your GitHub runners using the `Devopulence/test-workflows` repository.

## Prerequisites

1. **GitHub Personal Access Token** with the following permissions:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
   - `actions:read` (Read action results)

2. **Python 3.8+** installed

## Step 1: Set Up Environment

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set your GitHub token as environment variable
export GITHUB_TOKEN='your_github_token_here'
```

⚠️ **Security Note**: Never commit your token to the repository. Always use environment variables.

## Step 2: Upload Workflows to Your Repository

We need to upload the test workflow files to your `Devopulence/test-workflows` repository:

```bash
# Make the setup script executable
chmod +x setup_workflows.sh

# Run the setup script to upload workflows
./setup_workflows.sh
```

This will:
- Create the repository if it doesn't exist
- Upload all 5 test workflow templates to `.github/workflows/`
- Verify the uploads were successful

## Step 3: Verify Setup

Run the quick test to ensure everything is working:

```bash
python quick_test.py
```

This will:
- Check repository access
- Verify workflows are present
- Dispatch a single test workflow
- Monitor its execution
- Report success or failure

Expected output:
```
✅ Repository found: Devopulence/test-workflows
✅ Found 5 workflow(s)
✅ Workflow dispatched successfully!
✅ SUCCESS! The testing harness is working correctly!
```

## Step 4: Run Performance Tests

### Option A: Quick Performance Test (5 workflows)
```bash
python test_harness.py --test performance --environment development
```

### Option B: Load Test (10 workflows/minute for 10 minutes)
```bash
python test_harness.py --test load --environment development
```

### Option C: Stress Test (Find breaking point)
```bash
python test_harness.py --test stress
```

### Option D: Full Test Suite
```bash
python test_harness.py
```

## Configuration Overview

The `config.yaml` is already configured for your repository:
- **Owner**: Devopulence
- **Repository**: test-workflows
- **Default Environment**: development (lighter load for initial testing)

### Test Scenarios (Development Environment)

| Test Type | Configuration | Duration |
|-----------|--------------|----------|
| Performance | 5 workflows, sequential | ~5 minutes |
| Load | 5 workflows/min | 10 minutes |
| Stress | Progressive increase | 30-60 minutes |

## Switching to Self-Hosted Runners

When you're ready to test self-hosted runners on OpenShift:

1. **Update config.yaml** in the `self-hosted` environment section:
```yaml
self-hosted:
  github:
    owner: "your-internal-org"  # Your internal GitHub org
    repo: "internal-test-workflows"  # Your internal test repo
```

2. **Run tests with self-hosted environment**:
```bash
python test_harness.py --environment self-hosted
```

The self-hosted configuration is already optimized for 4-runner capacity on OpenShift.

## Understanding the Output

### Metrics Collected
- **Queue Time**: Time from workflow dispatch to runner pickup
- **Execution Time**: Time from start to completion
- **Success Rate**: Percentage of successful runs
- **Throughput**: Workflows processed per minute

### Results Location
- **Metrics**: `./metrics/` - Raw metrics in JSON format
- **Results**: `./results/` - Test summaries
- **Config Snapshot**: `./results/config_snapshot.json`

### Example Output
```
📊 Queue Time Statistics:
  Average: 5.2s
  Min/Max: 2.1s / 12.3s
  P50/P95/P99: 4.5s / 10.2s / 11.8s

⚡ Execution Time Statistics:
  Average: 35.6s
  Min/Max: 30.1s / 45.2s
  P50/P95/P99: 34.2s / 42.1s / 44.5s

🚀 Throughput:
  Workflows/min: 9.8
```

## Troubleshooting

### Issue: "Repository not found"
**Solution**: Run `./setup_workflows.sh` to create the repository and upload workflows

### Issue: "Workflow dispatch failed"
**Possible causes**:
1. Token doesn't have workflow permissions
2. Workflows not uploaded to repository
3. Branch protection rules blocking dispatch

### Issue: "Rate limit exceeded"
**Solution**:
- Wait for rate limit to reset (check with `python quick_test.py`)
- Reduce `rate_limit` in config.yaml
- Use a different token

### Issue: "Workflows timing out"
**Solution**:
- Increase `workflow_timeout` in config.yaml
- Check GitHub Actions tab for stuck workflows
- Ensure runners are available

## Test Workflow Descriptions

| Workflow | Purpose | Duration | Complexity |
|----------|---------|----------|------------|
| `simple_test.yml` | Basic performance baseline | 30-90s | Low |
| `medium_test.yml` | Data processing & compression | 2-3 min | Medium |
| `complex_test.yml` | Parallel jobs with aggregation | 3-5 min | High |
| `parallel_jobs.yml` | Test runner parallelism | 1-2 min | Parallel |
| `data_processing.yml` | Volume & I/O testing | 3-5 min | Data-intensive |

## Next Steps

1. **Start with simple tests** to understand baseline performance
2. **Gradually increase load** to find optimal throughput
3. **Run stress tests** to identify breaking points
4. **Document findings** for capacity planning
5. **Prepare for self-hosted** runner migration

## Support

For issues:
1. Check configuration: `python test_harness.py --validate`
2. View available tests: `python test_harness.py --list-tests`
3. Review logs in console output
4. Check GitHub Actions tab for workflow status

## Security Best Practices

1. **Never commit tokens** - Always use environment variables
2. **Use separate test repositories** - Don't test on production repos
3. **Monitor rate limits** - Avoid hitting GitHub API limits
4. **Clean up test data** - Remove old workflow runs periodically
5. **Rotate tokens regularly** - Update tokens every 90 days

---

**Ready to test!** Start with `python quick_test.py` to verify everything is working.