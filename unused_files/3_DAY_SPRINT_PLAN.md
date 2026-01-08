# 3-Day Sprint Plan: GitHub Runner Performance Testing Harness

## Overview
Build a functional MVP testing harness in 72 hours that can perform basic performance, load, and stress testing on GitHub runners.

## Day 1: Foundation (Hours 1-24)
**Goal**: Create core infrastructure for dispatching workflows and collecting metrics

### Morning (Hours 1-8)
#### Task 1.1: Enhance Workflow Dispatcher
- **File**: `dispatcher.py`
- **Features**:
  - Batch workflow dispatching
  - Concurrent execution with asyncio
  - Rate limit handling
  - Basic retry logic

```python
# Key functions to implement:
- async def dispatch_batch(workflows: List[Dict]) -> List[str]
- async def dispatch_workflow_async(config: Dict) -> str
- async def monitor_run(run_id: str) -> Dict
- class RateLimiter for API throttling
```

#### Task 1.2: Create Test Workflow Templates
- **Location**: `test_workflows/` directory
- **Workflows**:
  - `simple_test.yml` - 30 second execution
  - `medium_test.yml` - 2 minute execution
  - `complex_test.yml` - 5 minute execution
  - `parallel_jobs.yml` - Multiple concurrent jobs
  - `data_processing.yml` - Artifact generation

### Afternoon (Hours 9-16)
#### Task 1.3: Implement Metrics Collector
- **File**: `metrics_collector.py`
- **Features**:
  - Poll GitHub API for run status
  - Extract timing data
  - Calculate queue times
  - Store metrics in memory/JSON

```python
# Key classes to implement:
- class MetricsCollector
- class WorkflowMetrics (dataclass)
- class MetricsStorage (JSON-based initially)
```

#### Task 1.4: Create Configuration System
- **File**: `config.yaml`
- **Structure**:
  - GitHub credentials
  - Test scenarios
  - Monitoring settings
  - Report configurations

### Evening (Hours 17-24)
#### Task 1.5: Basic CLI Interface
- **File**: `test_harness.py`
- **Commands**:
  - `python test_harness.py --test performance --workflows 10`
  - `python test_harness.py --test load --duration 30`
  - `python test_harness.py --list-tests`

### Day 1 Deliverables Checklist:
- [ ] Batch workflow dispatch working
- [ ] 5 test workflow templates created
- [ ] Basic metrics collection functional
- [ ] Configuration file structure defined
- [ ] CLI can trigger simple tests
- [ ] Successfully dispatched and monitored 10+ workflows

---

## Day 2: Core Testing Implementation (Hours 25-48)
**Goal**: Build test runners for performance, load, and stress testing

### Morning (Hours 25-32)
#### Task 2.1: Performance Test Runner
- **File**: `runners/performance_runner.py`
- **Features**:
  - Baseline metrics collection
  - Sequential and parallel test modes
  - Statistical analysis (avg, p95, min/max)

```python
# Implementation focus:
class PerformanceRunner:
    async def run_baseline_test(workflows: int = 10)
    async def run_parallel_test(workflows: int = 10)
    def generate_performance_report() -> Dict
```

#### Task 2.2: Load Test Runner
- **File**: `runners/load_runner.py`
- **Features**:
  - Steady-state load generation
  - Configurable workflows per minute
  - Real-time metrics tracking

```python
# Implementation focus:
class LoadRunner:
    async def generate_steady_load(wpm: int, duration: int)
    async def generate_burst_load(pattern: List[int])
    def track_active_workflows()
```

### Afternoon (Hours 33-40)
#### Task 2.3: Stress Test Runner
- **File**: `runners/stress_runner.py`
- **Features**:
  - Progressive load increase
  - Breaking point detection
  - Failure tracking

```python
# Implementation focus:
class StressRunner:
    async def find_breaking_point(initial: int, increment: int)
    def detect_failure_conditions() -> bool
    def record_breaking_point()
```

#### Task 2.4: Test Orchestrator
- **File**: `orchestrator.py`
- **Features**:
  - Coordinate multiple test types
  - Resource management
  - Test scheduling

### Evening (Hours 41-48)
#### Task 2.5: Integration Testing
- Run each test type individually
- Fix bugs and integration issues
- Optimize performance
- Document any limitations

### Day 2 Deliverables Checklist:
- [ ] Performance runner executing baseline tests
- [ ] Load runner generating steady load (10+ workflows/min)
- [ ] Stress runner finding breaking points
- [ ] All runners integrated with metrics collector
- [ ] Successfully completed at least one 30-minute load test
- [ ] Identified maximum sustainable load

---

## Day 3: Monitoring, Reporting & Production Run (Hours 49-72)
**Goal**: Add monitoring dashboard, generate reports, and run comprehensive tests

### Morning (Hours 49-56)
#### Task 3.1: Real-time Monitoring Dashboard
- **File**: `dashboard.py`
- **Technology**: Simple Flask/FastAPI web server
- **Features**:
  - Live metrics display
  - Queue depth visualization
  - Success/failure rates
  - Active workflow tracking

```python
# Implementation:
- Web server on port 8080
- WebSocket for real-time updates
- Simple HTML/JavaScript frontend
- JSON API endpoints for metrics
```

#### Task 3.2: Report Generator
- **File**: `reporting.py`
- **Outputs**:
  - JSON detailed metrics
  - HTML summary report
  - CSV for data analysis

```python
# Key functions:
- generate_html_report(test_results: Dict)
- export_csv_metrics(metrics: List[Dict])
- create_executive_summary()
```

### Afternoon (Hours 57-64)
#### Task 3.3: Production Test Suite
- **Execute Full Test Suite**:
  1. Performance baseline (30 min)
  2. Load test at 10 wpm (60 min)
  3. Spike test (30 min)
  4. Stress test to find limits (60 min)

#### Task 3.4: Data Analysis
- Analyze collected metrics
- Identify patterns
- Document findings
- Create recommendations

### Evening (Hours 65-72)
#### Task 3.5: Documentation & Cleanup
- **Files to create/update**:
  - `README.md` - How to run the harness
  - `RESULTS.md` - Initial test findings
  - `CONFIGURATION.md` - Configuration guide
  - `API_REFERENCE.md` - Code documentation

#### Task 3.6: Package for Deployment
- Requirements.txt
- Docker container (optional)
- Setup scripts
- Environment configuration

### Day 3 Deliverables Checklist:
- [ ] Dashboard showing real-time metrics
- [ ] HTML reports generated for all test types
- [ ] Completed 3+ hours of continuous testing
- [ ] Documented maximum sustainable load
- [ ] Identified performance bottlenecks
- [ ] Created user documentation
- [ ] Repository ready for handoff

---

## Critical Path Items (Must Have)

### Day 1 Critical:
1. Batch workflow dispatch
2. Basic metrics collection
3. At least 2 test workflows

### Day 2 Critical:
1. Load generator (steady-state)
2. Metrics aggregation
3. One complete test run

### Day 3 Critical:
1. Basic reporting (JSON minimum)
2. 2-hour production test
3. Documentation of findings

---

## Risk Mitigation

### Potential Blockers:
1. **GitHub API Rate Limits**
   - Solution: Implement aggressive caching
   - Fallback: Reduce polling frequency

2. **Complex Async Issues**
   - Solution: Start with simpler threading if needed
   - Fallback: Sequential execution with lower load

3. **Metrics Collection Failures**
   - Solution: Store raw API responses for later processing
   - Fallback: Manual analysis of GitHub UI data

4. **Time Constraints**
   - Solution: Focus on critical path items only
   - Fallback: Deliver working subset of features

---

## Quick Start Commands for Each Day

### Day 1 End Goal:
```bash
python test_harness.py --test simple --workflows 5
# Should successfully dispatch 5 workflows and show basic metrics
```

### Day 2 End Goal:
```bash
python test_harness.py --test load --wpm 10 --duration 30
# Should maintain 10 workflows/minute for 30 minutes
```

### Day 3 End Goal:
```bash
python test_harness.py --test suite --report html
# Should run all tests and generate comprehensive report
# Dashboard available at http://localhost:8080
```

---

## Success Criteria

### Minimum Success (Must Have):
- Can dispatch 50+ workflows programmatically
- Can sustain 10 workflows/minute for 30 minutes
- Produces metrics showing queue time and execution time
- Identifies maximum load before failure

### Target Success (Should Have):
- All 3 test types functional (performance, load, stress)
- Real-time monitoring dashboard
- HTML reports with graphs
- 2+ hours of continuous testing data

### Stretch Success (Nice to Have):
- All 6 test types implemented
- Docker containerization
- Automated failure recovery
- Predictive analytics

---

## Hour-by-Hour Schedule

### Day 1:
- Hours 1-4: Dispatcher enhancements
- Hours 5-8: Test workflows
- Hours 9-12: Metrics collector
- Hours 13-16: Configuration system
- Hours 17-20: CLI interface
- Hours 21-24: Testing & debugging

### Day 2:
- Hours 25-28: Performance runner
- Hours 29-32: Load runner
- Hours 33-36: Stress runner
- Hours 37-40: Orchestrator
- Hours 41-44: Integration
- Hours 45-48: Bug fixes

### Day 3:
- Hours 49-52: Dashboard
- Hours 53-56: Reporting
- Hours 57-60: Production tests (Round 1)
- Hours 61-64: Production tests (Round 2)
- Hours 65-68: Documentation
- Hours 69-72: Final packaging

---

## Tools & Libraries Needed

### Required:
```txt
requests>=2.31.0
aiohttp>=3.9.0
pyyaml>=6.0
asyncio (built-in)
json (built-in)
datetime (built-in)
```

### Optional but Helpful:
```txt
flask>=3.0.0  # For dashboard
jinja2>=3.1.0  # For HTML reports
matplotlib>=3.5.0  # For graphs
pandas>=2.0.0  # For data analysis
```

---

## Final Notes

### Focus Areas:
1. **Functionality over Polish**: Get it working first
2. **Data Collection Priority**: Capture everything, analyze later
3. **Incremental Development**: Test each component as built
4. **Documentation as You Go**: Comment code, update README

### Communication:
- End of each day: Summary of completed items
- Blockers: Raise immediately
- Scope changes: Discuss trade-offs

### Remember:
- MVP first, enhancements later
- Working code > perfect code
- Test data > beautiful reports
- Core features > nice-to-haves

This is achievable in 3 days with focused effort!