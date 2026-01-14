# GitHub Runner Performance Testing Harness

A portable testing framework for evaluating GitHub Actions runner capacity, performance, and scalability.

---

## Overview

This harness was built to answer critical questions about our CI/CD infrastructure:

- **How many concurrent pipelines can our runners handle?**
- **What happens to queue times under heavy load?**
- **When do we need to scale up runners?**
- **How does the system recover from traffic spikes?**

### Target Environment

| Environment | Runners | Purpose |
|-------------|---------|---------|
| OpenShift Production | 4 (dynamic) | Production CI/CD workloads |
| AWS ECS (Test Bed) | 4 | Validate harness before production |

---

## Test Types

### 1. Performance Test (Baseline)
**Purpose:** Establish baseline metrics under normal conditions

- Dispatches jobs at a steady, sustainable rate
- Measures typical queue time, execution time, and throughput
- Establishes SLA recommendations (P50, P95, P99)

**Key Question:** *What does "normal" look like?*

---

### 2. Capacity Test
**Purpose:** Determine maximum sustainable throughput

- Floods the system with concurrent jobs
- Measures efficiency and saturation point
- Identifies optimal runner count

**Key Question:** *How many jobs can we process per hour?*

---

### 3. Load Test
**Purpose:** Evaluate performance over extended periods

- Runs for 2+ hours with sustained load
- Monitors for performance degradation over time
- Assesses long-term sustainability

**Key Question:** *Can we sustain this load all day?*

---

### 4. Stress Test
**Purpose:** Find the breaking point

- Pushes beyond normal capacity
- Identifies failure modes and queue buildup
- Tests system resilience

**Key Question:** *Where does the system break?*

---

### 5. Spike Test
**Purpose:** Evaluate response to sudden load increases

- Simulates traffic bursts (e.g., release day, morning rush)
- Measures queue impact during spike
- Assesses recovery time

**Key Question:** *How do we handle a sudden rush of builds?*

---

### 6. Concurrency Discovery
**Purpose:** Discover actual runner capacity (especially with auto-scaling)

- Dispatches many jobs simultaneously (20-30 at once)
- Tracks maximum concurrent jobs running
- Reveals true runner count vs configured count

**Key Question:** *How many runners do we actually have?*

**Sample Output:**
```
Concurrent Jobs (Runners Active):
  Max Observed: 4      <-- Actual runner limit discovered
  Average: 3.5
```

This is especially useful for environments like OpenShift where runners can scale dynamically. The configured count may say 4, but auto-scaling might provide 8 or more.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                     Test Harness Architecture                    │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  Test Runner │  Orchestrates test scenarios
    │  (Python)    │  Dispatches workflows via GitHub API
    └──────┬───────┘
           │
           │ workflow_dispatch API
           ▼
    ┌──────────────┐
    │   GitHub     │  Queues workflow runs
    │   Actions    │  Assigns to available runners
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────────────────────────────┐
    │              Runner Pool (4 runners)          │
    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
    │  │Runner 1│ │Runner 2│ │Runner 3│ │Runner 4│ │
    │  └────────┘ └────────┘ └────────┘ └────────┘ │
    └──────────────────────────────────────────────┘
           │
           │ Execution complete
           ▼
    ┌──────────────┐
    │  Workflow    │  Tracks job lifecycle
    │  Tracker     │  Calculates queue/execution times
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Analyzer    │  Test-specific analysis
    │  & Reporter  │  Generates recommendations
    └──────────────┘
```

### Workflow Lifecycle Tracking

```
Job Created ──► Job Started ──► Job Completed
     │              │                │
     └──Queue Time──┘                │
                    └──Execution Time┘
     └─────────── Total Time ────────┘
```

---

## Key Metrics

| Metric | What It Measures | Why It Matters |
|--------|------------------|----------------|
| **Queue Time** | Time waiting for a runner | User-perceived delay before build starts |
| **Execution Time** | Time running on a runner | Actual build/test duration |
| **Total Time** | Queue + Execution | End-to-end user experience |
| **Throughput** | Jobs completed per hour | System capacity |
| **Utilization** | % of runners busy | Capacity headroom |
| **Success Rate** | % of jobs that pass | System reliability |

---

## Sample Test Results

### Performance Test (30 minutes, 12 jobs)

```
============================================================
ENHANCED METRICS SUMMARY
============================================================

Workflows Analyzed: 12

📊 QUEUE TIME (waiting for runner):
  Average: 4.2 seconds
  Max: 11.0 seconds
  Min: 1.0 seconds

⚙️ EXECUTION TIME (on runner):
  Average: 4.5 minutes
  Max: 5.4 minutes
  Min: 3.4 minutes

⏱️ TOTAL TIME (queue + execution):
  Average: 4.6 minutes
  Max: 5.5 minutes
  Min: 3.5 minutes

🎯 CAPACITY INSIGHTS:
  Avg execution: 4.5 minutes
  Max throughput (4 runners): 53.3 jobs/hour
```

**Analysis Output:**
```
🎯 Performance Analysis:
----------------------------------------
Overall Rating: ⭐ EXCELLENT - Production ready
Queue Health: EXCELLENT
Execution Consistency: HIGHLY_CONSISTENT
Predictability: EXCELLENT
  Highly predictable execution times

Recommended SLAs:
  P50: 4.5 minutes
  P95: 5.2 minutes
  P99: 5.4 minutes
```

---

### Spike Test (60 minutes, 29 jobs with burst)

```
============================================================
ENHANCED METRICS SUMMARY
============================================================

Workflows Analyzed: 29

📊 QUEUE TIME (waiting for runner):
  Average: 3.9 minutes
  Max: 11.4 minutes
  Min: 0.0 minutes

📈 QUEUE TREND:
  First half avg: 1.5 minutes
  Second half avg: 6.1 minutes
  Trend: INCREASING
```

**Analysis Output:**
```
⚡ Spike Test Analysis:
----------------------------------------
Max Queue During Spike: 11.4 minutes
Spike Impact: 608.0x baseline
Recovery Quality: FULL_RECOVERY
System Elasticity: MODERATELY_ELASTIC
  System handles spikes but with strain
Overall: ⭐ EXCELLENT - Handles spikes with minimal queue impact
```

---

### Capacity Test (60 minutes, 20 jobs)

```
⚡ Capacity Analysis:
----------------------------------------
Actual Throughput: 0.33 workflows/min
Efficiency: 75.2%
Capacity Usage: WELL_UTILIZED
Average Utilization: 52.3%
Saturation State: BALANCED
Runner Optimization: Current capacity is adequate with headroom
```

---

## Running the Harness

### Quick Start

```bash
# Set GitHub token
export GITHUB_TOKEN='your_pat_token'

# Run a validation test (quick smoke test)
python run_tests.py -e openshift_sandbox -p validation
```

### Command Line Options

| Option | Short | Description | Example |
|--------|-------|-------------|---------|
| `--environment` | `-e` | Target environment | `-e openshift_sandbox` |
| `--profile` | `-p` | Test profile to run | `-p performance` |
| `--test` | `-t` | Built-in test type | `-t capacity` |
| `--list` | `-l` | List available profiles | `-l` |
| `--dry-run` | | Validate config only | `--dry-run` |
| `--interactive` | `-i` | Interactive mode | `-i` |

### Execution Examples

| Test | Command | Duration | Purpose |
|------|---------|----------|---------|
| **Validation** | `python run_tests.py -e openshift_sandbox -p validation` | 5 min | Quick smoke test |
| **Performance (fast)** | `python run_tests.py -e openshift_sandbox -p performance_fast` | 10 min | Fast baseline metrics |
| **Performance (full)** | `python run_tests.py -e openshift_sandbox -p performance` | 30 min | Complete baseline |
| **Capacity (fast)** | `python run_tests.py -e openshift_sandbox -p capacity_fast` | 12 min | Quick capacity check |
| **Capacity (full)** | `python run_tests.py -e openshift_sandbox -p capacity` | 60 min | Full capacity analysis |
| **Stress (fast)** | `python run_tests.py -e openshift_sandbox -p stress_fast` | 5 min | Quick breaking point |
| **Stress (full)** | `python run_tests.py -e openshift_sandbox -p stress` | 45 min | Full stress test |
| **Load (full)** | `python run_tests.py -e openshift_sandbox -p load` | 120 min | Extended sustainability |
| **Spike (medium)** | `python run_tests.py -e openshift_sandbox -p spike_medium` | 15 min | Medium burst test |
| **Spike (full)** | `python run_tests.py -e openshift_sandbox -p spike` | 60 min | Full spike analysis |
| **Concurrency Discovery** | `python run_tests.py -e openshift_sandbox -p concurrency_discovery` | 10 min | Find max concurrent runners |
| **Concurrency Max** | `python run_tests.py -e openshift_sandbox -p concurrency_max` | 15 min | Push harder (30 jobs) |

### Other Useful Commands

```bash
# List all available test profiles
python run_tests.py -e openshift_sandbox -l

# Validate configuration without running
python run_tests.py -e openshift_sandbox --dry-run

# Interactive mode (guided)
python run_tests.py -i
```

### Test Profiles

| Profile | Duration | Jobs | Pattern |
|---------|----------|------|---------|
| `validation` | 5 min | 4 | Quick smoke test |
| `performance_fast` | 10 min | 8 | Fast baseline |
| `performance` | 30 min | 12 | Full baseline |
| `capacity_fast` | 12 min | 12 | Quick capacity |
| `capacity` | 60 min | 20 | Full capacity |
| `stress_fast` | 5 min | 10 | Quick stress |
| `stress` | 45 min | 30 | Full stress |
| `load` | 120 min | 40 | Extended load |
| `spike_medium` | 15 min | 15 | Medium spike |
| `spike` | 60 min | 29 | Full spike |
| `concurrency_discovery` | 10 min | 40 | Burst 20 jobs - find runner limit |
| `concurrency_max` | 15 min | 60 | Burst 30 jobs - push harder |

---

## Output & Reports

Each test generates:

1. **Console Summary** - Real-time metrics during test
2. **JSON Report** - Detailed metrics for each workflow
3. **Analysis Report** - Test-specific insights and recommendations
4. **Tracking File** - Raw data for later analysis

Reports are saved to:
```
test_results/
└── {environment}/
    ├── test_report_{timestamp}.json
    ├── enhanced_report_{timestamp}.json
    ├── tracking/
    │   └── {test_type}_{timestamp}_{id}.json
    └── analysis/
        └── {test_run_id}_analysis.json
```

---

## Key Findings (Example)

Based on testing with 4 runners:

| Finding | Value | Implication |
|---------|-------|-------------|
| Max throughput | ~53 jobs/hour | 4 runners can handle ~53 builds/hour |
| Avg execution | 4.5 minutes | Typical CI job duration |
| Queue at capacity | 11+ minutes | Jobs wait 11 min when overwhelmed |
| Recovery time | ~5 jobs | System recovers after spike clears |

### Capacity Planning

```
With 4 runners @ 4.5 min avg execution:
- Theoretical max: 53 jobs/hour
- Sustainable rate: ~40 jobs/hour (75% utilization)
- Add runners when: Queue time consistently > 2 minutes
```

---

## Architecture Highlights

- **Portable**: Works with any GitHub runner environment (OpenShift, ECS, self-hosted)
- **Non-destructive**: Uses sleep-based test workflows (no actual builds)
- **Configurable**: YAML-based environment and test profiles
- **Async**: Efficient parallel workflow tracking
- **Extensible**: Pluggable analyzers for different test types

---

## Next Steps

1. **Production Baseline**: Run full test suite on OpenShift production
2. **Capacity Planning**: Determine if 4 runners is sufficient
3. **Auto-scaling Validation**: Test dynamic runner scaling behavior
4. **SLA Definition**: Establish queue time SLAs based on findings
