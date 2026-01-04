"""
Enhanced Performance Test Analyzer
Analyzes test results and provides interpretations and recommendations.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import statistics


class PerformanceAnalyzer:
    """Analyzes performance test results and provides insights."""

    def __init__(self, test_results_path: str = None, captured_metrics_path: str = None):
        self.test_results_path = test_results_path
        self.captured_metrics_path = captured_metrics_path
        self.thresholds = self._load_thresholds()

    def _load_thresholds(self) -> Dict:
        """Define performance thresholds for analysis."""
        return {
            'queue_time': {
                'excellent': 0.5,  # < 30 seconds
                'good': 2.0,       # < 2 minutes
                'acceptable': 5.0,  # < 5 minutes
                'poor': 10.0       # > 10 minutes is problematic
            },
            'utilization': {
                'optimal': (70, 85),  # 70-85% is optimal
                'high': 95,           # > 95% might be overloaded
                'low': 50             # < 50% is underutilized
            },
            'queue_impact': {
                'minimal': 10,     # < 10% is minimal impact
                'moderate': 30,    # < 30% is moderate
                'significant': 50  # > 50% is significant
            }
        }

    def analyze_queue_behavior(self, queue_times: List[float]) -> Dict[str, Any]:
        """Analyze queue time patterns and provide insights."""
        if not queue_times:
            return {"error": "No queue data available"}

        avg_queue = statistics.mean(queue_times)
        max_queue = max(queue_times)
        min_queue = min(queue_times)

        # Calculate percentiles
        sorted_queues = sorted(queue_times)
        p50 = sorted_queues[len(sorted_queues) // 2]
        p95_idx = int(len(sorted_queues) * 0.95)
        p95 = sorted_queues[p95_idx] if p95_idx < len(sorted_queues) else max_queue

        # Determine queue health
        if avg_queue < self.thresholds['queue_time']['excellent']:
            health = 'EXCELLENT'
            interpretation = "Virtually no queuing - runners immediately available"
        elif avg_queue < self.thresholds['queue_time']['good']:
            health = 'GOOD'
            interpretation = "Minor queuing - acceptable for most use cases"
        elif avg_queue < self.thresholds['queue_time']['acceptable']:
            health = 'ACCEPTABLE'
            interpretation = "Moderate queuing - users experiencing delays"
        else:
            health = 'POOR'
            interpretation = "Significant queuing - capacity insufficient for workload"

        # Calculate queue growth pattern
        queue_growth = self._analyze_queue_growth(queue_times)

        return {
            'metrics': {
                'average': avg_queue,
                'minimum': min_queue,
                'maximum': max_queue,
                'median': p50,
                'p95': p95,
                'jobs_queued': sum(1 for q in queue_times if q > 0.1)
            },
            'health': health,
            'interpretation': interpretation,
            'growth_pattern': queue_growth,
            'recommendations': self._get_queue_recommendations(avg_queue, max_queue, queue_growth)
        }

    def _analyze_queue_growth(self, queue_times: List[float]) -> str:
        """Analyze how queue times change over the test duration."""
        if len(queue_times) < 3:
            return "INSUFFICIENT_DATA"

        # Split into thirds
        third = len(queue_times) // 3
        first_third = statistics.mean(queue_times[:third]) if queue_times[:third] else 0
        middle_third = statistics.mean(queue_times[third:2*third]) if queue_times[third:2*third] else 0
        last_third = statistics.mean(queue_times[2*third:]) if queue_times[2*third:] else 0

        # Determine pattern
        if last_third > middle_third > first_third:
            if last_third > first_third * 2:
                return "EXPONENTIAL_GROWTH"
            return "LINEAR_GROWTH"
        elif last_third < middle_third < first_third:
            return "RECOVERING"
        elif abs(last_third - first_third) < 0.5:  # Less than 30 seconds difference
            return "STABLE"
        else:
            return "VARIABLE"

    def _get_queue_recommendations(self, avg_queue: float, max_queue: float, pattern: str) -> List[str]:
        """Generate recommendations based on queue analysis."""
        recommendations = []

        # Based on average queue time
        if avg_queue > self.thresholds['queue_time']['acceptable']:
            recommendations.append("CRITICAL: Add more runners or reduce workload")
        elif avg_queue > self.thresholds['queue_time']['good']:
            recommendations.append("Consider adding 1-2 more runners for better performance")

        # Based on pattern
        if pattern == "EXPONENTIAL_GROWTH":
            recommendations.append("Queue growing rapidly - system cannot keep up with demand")
            recommendations.append("Reduce dispatch rate by 30-50% or add runners")
        elif pattern == "LINEAR_GROWTH":
            recommendations.append("Queue growing steadily - approaching capacity limit")
            recommendations.append("Current rate is slightly above sustainable level")

        # Based on max queue
        if max_queue > 10:
            recommendations.append(f"Peak queue time ({max_queue:.1f} min) exceeds 10 minutes")
            recommendations.append("Users experiencing significant delays during peak")

        if not recommendations:
            recommendations.append("System performing within acceptable parameters")

        return recommendations

    def analyze_execution_times(self, exec_times: List[float], expected_range: Tuple[float, float]) -> Dict[str, Any]:
        """Analyze execution time consistency and performance."""
        if not exec_times:
            return {"error": "No execution data available"}

        avg_exec = statistics.mean(exec_times)
        min_expected, max_expected = expected_range

        # Calculate variance
        if len(exec_times) > 1:
            std_dev = statistics.stdev(exec_times)
            cv = (std_dev / avg_exec) * 100  # Coefficient of variation
        else:
            std_dev = 0
            cv = 0

        # Determine consistency
        if cv < 10:
            consistency = "HIGHLY_CONSISTENT"
            interpretation = "Execution times very predictable"
        elif cv < 20:
            consistency = "CONSISTENT"
            interpretation = "Normal variation in execution times"
        elif cv < 30:
            consistency = "MODERATE_VARIATION"
            interpretation = "Some variation - check for resource contention"
        else:
            consistency = "HIGH_VARIATION"
            interpretation = "Significant variation - investigate runner performance"

        # Check if within expected range
        within_range = sum(1 for t in exec_times if min_expected <= t <= max_expected)
        range_compliance = (within_range / len(exec_times)) * 100

        return {
            'metrics': {
                'average': avg_exec,
                'minimum': min(exec_times),
                'maximum': max(exec_times),
                'std_deviation': std_dev,
                'coefficient_variation': cv
            },
            'consistency': consistency,
            'interpretation': interpretation,
            'range_compliance': {
                'expected_range': f"{min_expected}-{max_expected} minutes",
                'within_range_pct': range_compliance,
                'assessment': 'GOOD' if range_compliance > 90 else 'INVESTIGATE'
            },
            'recommendations': self._get_execution_recommendations(avg_exec, cv, range_compliance)
        }

    def _get_execution_recommendations(self, avg_exec: float, cv: float, compliance: float) -> List[str]:
        """Generate recommendations based on execution analysis."""
        recommendations = []

        if cv > 30:
            recommendations.append("High variation suggests runner performance issues")
            recommendations.append("Check: Runner resources, network stability, noisy neighbors")

        if compliance < 90:
            recommendations.append(f"Only {compliance:.0f}% of jobs completed within expected time")
            recommendations.append("Investigate outliers for root cause")

        if not recommendations:
            recommendations.append("Execution times are stable and predictable")

        return recommendations

    def analyze_utilization(self, utilization_data: List[float], runner_count: int) -> Dict[str, Any]:
        """Analyze runner utilization patterns."""
        if not utilization_data:
            return {"error": "No utilization data available"}

        avg_util = statistics.mean(utilization_data) * 100
        peak_util = max(utilization_data) * 100

        # Count time at different utilization levels
        time_at_100 = sum(1 for u in utilization_data if u >= 0.99) / len(utilization_data) * 100
        time_above_90 = sum(1 for u in utilization_data if u >= 0.90) / len(utilization_data) * 100
        time_below_50 = sum(1 for u in utilization_data if u < 0.50) / len(utilization_data) * 100

        # Determine efficiency
        optimal_min, optimal_max = self.thresholds['utilization']['optimal']
        if optimal_min <= avg_util <= optimal_max:
            efficiency = "OPTIMAL"
            interpretation = f"Excellent balance - runners efficiently utilized"
        elif avg_util > self.thresholds['utilization']['high']:
            efficiency = "OVERLOADED"
            interpretation = f"Runners constantly busy - no spare capacity"
        elif avg_util < self.thresholds['utilization']['low']:
            efficiency = "UNDERUTILIZED"
            interpretation = f"Runners often idle - excess capacity"
        else:
            efficiency = "GOOD"
            interpretation = f"Acceptable utilization level"

        return {
            'metrics': {
                'average': avg_util,
                'peak': peak_util,
                'time_at_100_pct': time_at_100,
                'time_above_90_pct': time_above_90,
                'time_below_50_pct': time_below_50
            },
            'efficiency': efficiency,
            'interpretation': interpretation,
            'capacity_analysis': self._analyze_capacity(avg_util, time_at_100, runner_count),
            'recommendations': self._get_utilization_recommendations(avg_util, time_at_100, runner_count)
        }

    def _analyze_capacity(self, avg_util: float, time_at_100: float, runner_count: int) -> Dict[str, Any]:
        """Analyze system capacity."""
        if time_at_100 > 50:
            status = "AT_CAPACITY"
            headroom = 0
        else:
            headroom = 100 - avg_util
            if headroom > 30:
                status = "SIGNIFICANT_HEADROOM"
            elif headroom > 15:
                status = "MODERATE_HEADROOM"
            else:
                status = "LIMITED_HEADROOM"

        # Calculate theoretical max throughput increase
        max_increase = (100 / avg_util - 1) * 100 if avg_util > 0 else 0

        return {
            'status': status,
            'headroom_pct': headroom,
            'max_throughput_increase_pct': max_increase,
            'interpretation': f"System can handle {max_increase:.0f}% more load before saturation"
        }

    def _get_utilization_recommendations(self, avg_util: float, time_at_100: float, runner_count: int) -> List[str]:
        """Generate recommendations based on utilization."""
        recommendations = []

        if avg_util > 95:
            recommendations.append(f"Add 1-2 runners to current {runner_count} for breathing room")
        elif avg_util > 85:
            recommendations.append("Monitor closely - approaching capacity limits")
        elif avg_util < 50:
            recommendations.append(f"Consider reducing to {runner_count - 1} runners")
            recommendations.append("Or increase workload to better utilize resources")

        if time_at_100 > 50:
            recommendations.append("Runners at 100% for majority of test - definite bottleneck")

        return recommendations if recommendations else ["Utilization levels are appropriate"]

    def generate_insights(self, queue_times: List[float], exec_times: List[float],
                         total_times: List[float], runner_count: int,
                         dispatch_rate: float) -> Dict[str, Any]:
        """Generate comprehensive insights from all metrics."""

        # Calculate key relationships
        queue_impact = (sum(queue_times) / sum(total_times) * 100) if sum(total_times) > 0 else 0
        avg_total = statistics.mean(total_times) if total_times else 0

        # Determine bottleneck
        if queue_impact > self.thresholds['queue_impact']['significant']:
            bottleneck = "QUEUE_TIME"
            bottleneck_desc = "Primary bottleneck is waiting for available runners"
        elif statistics.mean(exec_times) > 10:
            bottleneck = "EXECUTION_TIME"
            bottleneck_desc = "Primary bottleneck is job execution duration"
        else:
            bottleneck = "BALANCED"
            bottleneck_desc = "No single bottleneck identified"

        # Calculate sustainable rate
        avg_exec = statistics.mean(exec_times) if exec_times else 4
        sustainable_rate = (runner_count * 60) / avg_exec  # jobs per hour / 60

        # Determine if current rate is sustainable
        if dispatch_rate <= sustainable_rate * 0.8:
            rate_assessment = "WELL_BELOW_CAPACITY"
        elif dispatch_rate <= sustainable_rate:
            rate_assessment = "SUSTAINABLE"
        elif dispatch_rate <= sustainable_rate * 1.2:
            rate_assessment = "SLIGHTLY_ABOVE_CAPACITY"
        else:
            rate_assessment = "UNSUSTAINABLE"

        return {
            'summary': {
                'bottleneck': bottleneck,
                'bottleneck_description': bottleneck_desc,
                'queue_impact_pct': queue_impact,
                'rate_assessment': rate_assessment
            },
            'capacity': {
                'current_runners': runner_count,
                'sustainable_rate': f"{sustainable_rate:.2f} jobs/minute",
                'current_rate': f"{dispatch_rate:.2f} jobs/minute",
                'rate_ratio': dispatch_rate / sustainable_rate if sustainable_rate > 0 else 0
            },
            'user_experience': self._assess_user_experience(avg_total, queue_impact),
            'system_health': self._assess_system_health(queue_impact, rate_assessment),
            'key_findings': self._generate_key_findings(queue_times, exec_times, queue_impact, bottleneck),
            'action_items': self._generate_action_items(bottleneck, rate_assessment, queue_impact, runner_count)
        }

    def _assess_user_experience(self, avg_total: float, queue_impact: float) -> Dict[str, str]:
        """Assess the user experience based on metrics."""
        if avg_total < 5 and queue_impact < 20:
            rating = "EXCELLENT"
            description = "Fast builds with minimal waiting"
        elif avg_total < 10 and queue_impact < 40:
            rating = "GOOD"
            description = "Acceptable build times with some queuing"
        elif avg_total < 15:
            rating = "FAIR"
            description = "Noticeable delays impacting productivity"
        else:
            rating = "POOR"
            description = "Significant delays frustrating developers"

        return {
            'rating': rating,
            'description': description,
            'avg_wait_time': f"{avg_total:.1f} minutes"
        }

    def _assess_system_health(self, queue_impact: float, rate_assessment: str) -> str:
        """Assess overall system health."""
        if rate_assessment in ["SUSTAINABLE", "WELL_BELOW_CAPACITY"] and queue_impact < 30:
            return "HEALTHY - System operating within capacity"
        elif rate_assessment == "SLIGHTLY_ABOVE_CAPACITY" and queue_impact < 50:
            return "STRESSED - System near capacity limits"
        else:
            return "OVERLOADED - System beyond sustainable capacity"

    def _generate_key_findings(self, queue_times: List[float], exec_times: List[float],
                               queue_impact: float, bottleneck: str) -> List[str]:
        """Generate key findings list."""
        findings = []

        # Queue findings
        if queue_impact > 40:
            findings.append(f"⚠️ Queue time represents {queue_impact:.0f}% of total time - significant impact")

        # Execution findings
        if exec_times:
            cv = (statistics.stdev(exec_times) / statistics.mean(exec_times) * 100) if len(exec_times) > 1 else 0
            if cv > 30:
                findings.append(f"⚠️ High variation in execution times (CV: {cv:.0f}%) suggests instability")

        # Bottleneck finding
        findings.append(f"🔍 Primary bottleneck: {bottleneck.replace('_', ' ').lower()}")

        # Positive findings
        if queue_impact < 20:
            findings.append("✅ Minimal queuing indicates good capacity match")

        return findings

    def _generate_action_items(self, bottleneck: str, rate_assessment: str,
                              queue_impact: float, runner_count: int) -> List[str]:
        """Generate prioritized action items."""
        actions = []

        if bottleneck == "QUEUE_TIME":
            if rate_assessment == "UNSUSTAINABLE":
                actions.append(f"🔴 HIGH: Add 2-3 runners to current {runner_count}")
            elif rate_assessment == "SLIGHTLY_ABOVE_CAPACITY":
                actions.append(f"🟡 MEDIUM: Add 1 runner or reduce dispatch rate by 20%")

        if bottleneck == "EXECUTION_TIME":
            actions.append("🟡 MEDIUM: Optimize workflow to reduce execution time")
            actions.append("💡 Consider splitting large jobs into smaller parallel tasks")

        if queue_impact > 50:
            actions.append("🔴 HIGH: Implement job priority queuing for critical builds")

        if not actions:
            actions.append("✅ No immediate actions required - system performing well")

        return actions

    def generate_report(self, test_data: Dict[str, Any]) -> str:
        """Generate a comprehensive analysis report."""
        # This would be the main entry point that uses all the analysis methods
        # and generates a complete report
        pass