# GitHub Runner Performance Testing Harness

A comprehensive testing framework for evaluating the performance, scalability, and capacity of GitHub workflow runners.

## 🚀 Quick Start for Devopulence/test-workflows

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token with workflow permissions
- Target repository: `Devopulence/test-workflows`

### Installation & Setup

```bash
# 1. Install dependencies
make install
# or: pip install -r requirements.txt

# 2. Set GitHub token (REQUIRED)
export GITHUB_TOKEN="your_github_token_here"

# 3. Upload workflows to your repository
make setup
# or: bash setup_workflows.sh

# 4. Verify everything works
make quick-test
# or: python quick_test.py
```

### Running Tests

```bash
# Using Makefile (recommended)
make performance  # Run performance test (5 workflows)
make load        # Run load test (10 min @ 5 wpm)
make stress      # Find breaking point
make test        # Run full test suite

# Or using Python directly
python test_harness.py --test performance
python test_harness.py --test load
python test_harness.py --test stress
python test_harness.py  # Full suite

# Other useful commands
make validate    # Check configuration
make show-config # Display current settings
make clean       # Clean up old results
```

### Configuration

The harness is pre-configured for `Devopulence/test-workflows`. When switching to self-hosted runners, update the `self-hosted` section in `config.yaml`:

```yaml
self-hosted:
  github:
    owner: "your-internal-org"
    repo: "internal-test-workflows"
```

## 📊 Test Types

### Performance Test
- Establishes baseline metrics
- Runs workflows sequentially for clean measurements
- Calculates queue time, execution time, and success rates

### Load Test
- Generates steady-state load
- Tests system under normal operating conditions
- Configurable workflow distribution

### Stress Test
- Progressively increases load to find breaking point
- Identifies system limits
- Monitors failure conditions

## 🏗️ Architecture

```
test_harness.py          # Main CLI interface
├── dispatcher.py        # Async workflow dispatch engine
├── metrics_collector.py # Metrics collection and analysis
├── config_manager.py    # Configuration management
├── config.yaml         # Main configuration file
└── test_workflows/     # Test workflow templates
    ├── simple_test.yml
    ├── medium_test.yml
    ├── complex_test.yml
    ├── parallel_jobs.yml
    └── data_processing.yml
```

## 📈 Metrics Collected

- **Queue Time**: Time from dispatch to runner pickup
- **Execution Time**: Time from start to completion
- **Total Time**: End-to-end workflow time
- **Success Rate**: Percentage of successful runs
- **Throughput**: Workflows/jobs per minute
- **Percentiles**: P50, P95, P99 for timing metrics

## 📁 Output

Results are stored in:
- `./metrics/` - Raw metrics data (JSON)
- `./results/` - Test results and summaries
- `./reports/` - Generated reports (coming in Day 3)

## 🔧 Configuration Options

### Test Scenarios

Each test type can be configured in `config.yaml`:

```yaml
test_scenarios:
  performance:
    enabled: true
    workflow_count: 10
    workflow_types: ["simple", "medium"]

  load:
    enabled: true
    steady_state:
      workflows_per_minute: 10
      duration_minutes: 30
```

### Environment-Specific Settings

```yaml
environments:
  development:
    github:
      rate_limit: 5

  production:
    github:
      rate_limit: 20
```

## 🎯 Day 1 Accomplishments

✅ **Completed Components:**
- Batch workflow dispatcher with async support
- Metrics collector with aggregation
- Configuration management system
- 5 test workflow templates
- CLI interface for test execution
- Basic performance, load, and stress test runners

## 📅 Upcoming (Day 2 & 3)

**Day 2:**
- Enhanced test runners
- Load generation patterns
- Test orchestration improvements
- Integration testing

**Day 3:**
- Real-time monitoring dashboard
- HTML/CSV report generation
- Production test runs
- Documentation

## 🐛 Troubleshooting

### Common Issues

1. **Rate Limiting**
   - Reduce `rate_limit` in config.yaml
   - Increase intervals between dispatches

2. **Workflow Not Found**
   - Ensure workflows exist in target repository
   - Check workflow file names match config

3. **Authentication Errors**
   - Verify GITHUB_TOKEN has correct permissions
   - Token needs: `repo`, `workflow`, `actions:read`

## 📝 Examples

### Running a Quick Performance Test

```bash
# Minimal performance test
python test_harness.py --test performance --environment development
```

### Running a 30-Minute Load Test

```bash
# Edit config.yaml to set load parameters
python test_harness.py --test load
```

### Finding the Breaking Point

```bash
# Stress test with progressive load
python test_harness.py --test stress
```

## 🤝 Contributing

This is a 3-day sprint project. Focus areas:
- Day 1: Foundation ✅
- Day 2: Core testing features (in progress)
- Day 3: Monitoring & reporting

## 📄 License

Internal use only - PNC work project

## 🆘 Support

For issues or questions, check:
- Configuration with `--validate`
- Available tests with `--list-tests`
- Logs in console output
- Metrics in `./metrics/` directory

---

**Current Status**: Day 1 Complete - Foundation Built ✅

Ready to dispatch workflows and collect metrics!