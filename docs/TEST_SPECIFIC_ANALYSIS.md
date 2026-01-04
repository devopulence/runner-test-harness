# Test-Specific Analysis System

## Overview

Each test type has unique goals and requires different analysis focus. The test-specific analysis system automatically runs the appropriate analysis after each test, providing insights tailored to what matters most for that test type.

## Automatic Analysis

When you run any test:
```bash
python run_tests.py -e aws_ecs -t performance
```

You now get:
1. **Standard metrics** (queue, execution, throughput)
2. **Test-specific analysis** (automatic, based on test type)
3. **Targeted recommendations** (specific to findings)
4. **Saved analysis** with test run ID for historical tracking

## Test Types and Their Focus

### 1. Performance Test
**Goal**: Establish baseline performance metrics

**Key Metrics**:
- Queue time consistency
- Execution time predictability
- Overall stability
- Recommended SLAs

**Analysis Focus**:
```
🎯 Performance Analysis:
----------------------------------------
Overall Rating: ⭐ EXCELLENT - Production ready
Queue Health: EXCELLENT
Execution Consistency: CONSISTENT
Predictability: EXCELLENT
  Highly predictable - excellent for setting SLAs

Recommended SLAs:
  P50: 3.5 minutes
  P95: 4.8 minutes
  P99: 5.2 minutes
```

**When to Use**:
- Setting baseline expectations
- Validating normal operation
- Establishing SLAs

### 2. Load Test
**Goal**: Verify sustained performance under continuous load

**Key Metrics**:
- Performance degradation over time
- Throughput sustainability
- Error rates under load
- System stability

**Analysis Focus**:
```
📈 Load Test Analysis:
----------------------------------------
Performance Degradation: GRADUAL_DEGRADATION
  Acceptable degradation - system handles load well
Throughput: 60.0 workflows/hour
  Rating: GOOD
Load Sustainability: SUSTAINABLE
  System handles load well with acceptable degradation
```

**When to Use**:
- Testing production workloads
- Validating sustained operation
- Finding degradation patterns

### 3. Stress Test
**Goal**: Find breaking points and failure modes

**Key Metrics**:
- Maximum queue times
- Breaking point identification
- Failure rates
- System resilience

**Analysis Focus**:
```
💥 Stress Test Analysis:
----------------------------------------
Max Queue Time: 25.3 minutes
Breaking Point Reached: Yes
Failure Rate: 15.2%
System Resilience: LOW_RESILIENCE - System struggles under stress
Stress Handling: FAIR
  System shows stress but continues operating
```

**When to Use**:
- Finding system limits
- Testing failure scenarios
- Validating error handling

### 4. Capacity Test
**Goal**: Determine maximum throughput and optimal configuration

**Key Metrics**:
- Maximum sustainable throughput
- Runner efficiency
- Saturation points
- Optimal runner count

**Analysis Focus**:
```
⚡ Capacity Analysis:
----------------------------------------
Actual Throughput: 0.95 workflows/min
Efficiency: 95.0%
Capacity Usage: NEAR_MAXIMUM
Average Utilization: 92.5%
Saturation State: NEAR_SATURATION
Runner Optimization: Current runner count is optimal
```

**When to Use**:
- Capacity planning
- Optimizing runner count
- Finding maximum throughput

### 5. Spike Test
**Goal**: Test response to sudden load increases

**Key Metrics**:
- Spike response time
- Recovery behavior
- System elasticity
- Queue spillover

**Analysis Focus**:
```
⚡ Spike Test Analysis:
----------------------------------------
Spike Impact: 4.5x baseline
Recovery Quality: GOOD_RECOVERY
System Elasticity: ELASTIC
  System handles spikes well
Overall: ✅ GOOD - Manages spikes effectively
```

**When to Use**:
- Testing burst scenarios
- Validating auto-scaling
- Assessing elasticity

## Analysis Components

### 1. Health Ratings

Each test provides health ratings using consistent indicators:
- ⭐ **EXCELLENT** - Exceptional performance, production ready
- ✅ **GOOD** - Meets requirements with minor improvements possible
- ⚡ **FAIR** - Acceptable but optimization recommended
- ⚠️ **NEEDS IMPROVEMENT** - Issues to address before production
- ❌ **POOR** - Critical issues requiring immediate attention

### 2. Recommendations

Recommendations are color-coded by priority:
- 🔴 **Critical** - Must fix immediately
- 🟡 **Important** - Should address soon
- 💡 **Suggested** - Nice to have improvements

Example recommendations:
```
📋 Recommendations:
----------------------------------------
  🔴 Critical: Reduce queue times by adding runners
  🟡 Consider adding 1-2 runners to improve queue performance
  💡 Consider reducing to 3 runners (overcapacity)
```

### 3. Automated Insights

Each analyzer provides specific insights:

**Performance Test**:
- Baseline establishment
- Predictability scoring
- SLA recommendations

**Load Test**:
- Degradation patterns
- Sustainability assessment
- Throughput analysis

**Stress Test**:
- Breaking point identification
- Resilience scoring
- Failure analysis

**Capacity Test**:
- Efficiency calculations
- Saturation analysis
- Optimization recommendations

**Spike Test**:
- Elasticity rating
- Recovery analysis
- Response multipliers

## Output Files

Analysis results are saved automatically:

```
test_results/
├── aws-ecs/
│   ├── analysis/
│   │   ├── performance_20260104_093000_abc123_analysis.json
│   │   ├── load_20260104_103000_def456_analysis.json
│   │   └── stress_20260104_113000_ghi789_analysis.json
│   └── tracking/
│       └── performance_20260104_093000_abc123.json
```

Each analysis file contains:
- Test run ID for tracking
- Test type
- Complete analysis results
- Metrics used
- Generated recommendations

## Using Analysis Results

### Viewing Results
Analysis appears automatically after each test:
```bash
python run_tests.py -e aws_ecs -t performance
# ... test runs ...
# ... standard metrics display ...

🔬 Running performance test analysis...
============================================================
[Analysis results display here]
```

### Accessing Historical Analysis
```bash
# List all test runs
python analyze_specific_test.py --list

# View specific analysis
cat test_results/aws-ecs/analysis/performance_20260104_093000_abc123_analysis.json | jq
```

### Comparing Tests
Since each test run has unique tracking and analysis:
```python
# Compare two performance tests
import json

with open('test_results/aws-ecs/analysis/performance_run1_analysis.json') as f:
    run1 = json.load(f)

with open('test_results/aws-ecs/analysis/performance_run2_analysis.json') as f:
    run2 = json.load(f)

# Compare queue health
print(f"Run 1 Queue: {run1['analysis']['queue_analysis']['health']}")
print(f"Run 2 Queue: {run2['analysis']['queue_analysis']['health']}")
```

## Customizing Analysis

### Adding New Test Types

1. Create a new analyzer class:
```python
class CustomTestAnalyzer(BaseTestAnalyzer):
    def get_key_metrics(self) -> List[str]:
        return ["your", "key", "metrics"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        # Your analysis logic
        return analysis

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        # Your recommendations
        return recommendations
```

2. Register in TestAnalyzerFactory:
```python
_analyzers = {
    "custom": CustomTestAnalyzer,
    # ... other analyzers
}
```

### Adjusting Thresholds

Each analyzer has configurable thresholds. Example:
```python
# In PerformanceTestAnalyzer
def analyze(self, metrics):
    # Adjust expected execution time range
    analysis["execution_analysis"] = self.perf_analyzer.analyze_execution_times(
        exec_times,
        expected_range=(2, 4)  # Changed from (3, 5)
    )
```

## Best Practices

1. **Run the right test for your goal**:
   - Performance → Baselines
   - Load → Production readiness
   - Stress → Failure modes
   - Capacity → Scaling decisions
   - Spike → Burst handling

2. **Pay attention to recommendations**:
   - 🔴 Critical items block production
   - 🟡 Important items affect reliability
   - 💡 Suggestions improve efficiency

3. **Track trends over time**:
   - Compare analysis from multiple runs
   - Look for degradation patterns
   - Monitor improvements after changes

4. **Use test-specific insights**:
   - Don't judge a stress test by performance metrics
   - Don't judge a performance test by capacity metrics
   - Each test type has its own success criteria

## Troubleshooting

### Analysis Failed
If you see "⚠️ Analysis failed":
1. Check that metrics were collected
2. Verify test completed successfully
3. Check logs for specific errors

### Missing Metrics
Some analyses require specific metrics:
- Queue times (from job-level API data)
- Utilization (from runner monitoring)
- Failure counts (from workflow status)

### Inconsistent Results
If analyses vary widely:
1. Ensure consistent test duration
2. Check for external factors (other workloads)
3. Verify runner configuration matches