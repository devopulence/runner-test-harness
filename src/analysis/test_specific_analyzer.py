"""
Test-Specific Analyzers
Each test type has unique analysis requirements and focus areas
"""
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from src.analysis.performance_analyzer import PerformanceAnalyzer


class BaseTestAnalyzer(ABC):
    """Base class for test-specific analyzers."""

    def __init__(self):
        self.perf_analyzer = PerformanceAnalyzer()

    @abstractmethod
    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Perform test-specific analysis."""
        pass

    @abstractmethod
    def get_key_metrics(self) -> List[str]:
        """Return the key metrics this test type focuses on."""
        pass

    @abstractmethod
    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate test-specific recommendations."""
        pass


class PerformanceTestAnalyzer(BaseTestAnalyzer):
    """
    Performance Test Analysis
    Focus: Baseline metrics, consistency, predictability
    """

    def get_key_metrics(self) -> List[str]:
        return ["queue_time", "execution_time", "consistency", "predictability"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance test results focusing on baseline behavior."""
        analysis = {
            "test_type": "performance",
            "timestamp": datetime.now().isoformat(),
            "focus": "Baseline performance and consistency"
        }

        # Core metrics
        queue_times = metrics.get('queue_times', [])
        exec_times = metrics.get('execution_times', [])
        total_times = metrics.get('total_times', [])

        # Check if we have data to analyze
        if not queue_times and not exec_times:
            analysis["status"] = "NO_DATA"
            analysis["message"] = "No completed workflows to analyze"
            return analysis

        # Queue behavior analysis
        if queue_times:
            analysis["queue_analysis"] = self.perf_analyzer.analyze_queue_behavior(queue_times)
        else:
            analysis["queue_analysis"] = {"health": "UNKNOWN", "interpretation": "No queue data available"}

        # Execution consistency analysis
        if exec_times:
            analysis["execution_analysis"] = self.perf_analyzer.analyze_execution_times(
                exec_times,
                expected_range=(3, 5)  # Standard workload
            )
        else:
            analysis["execution_analysis"] = {"consistency": "UNKNOWN", "interpretation": "No execution data available"}

        # Predictability score (lower variance = more predictable)
        if total_times:
            mean_total = statistics.mean(total_times)
            stdev_total = statistics.stdev(total_times) if len(total_times) > 1 else 0
            cv_total = (stdev_total / mean_total * 100) if mean_total > 0 else 0

            analysis["predictability"] = {
                "score": "EXCELLENT" if cv_total < 10 else "GOOD" if cv_total < 25 else "FAIR" if cv_total < 40 else "POOR",
                "coefficient_variation": cv_total,
                "interpretation": self._interpret_predictability(cv_total)
            }

        # Baseline establishment
        analysis["baseline_metrics"] = {
            "recommended_sla": {
                "p50": statistics.median(total_times) if total_times else 0,
                "p95": statistics.quantiles(total_times, n=20)[18] if len(total_times) > 1 else total_times[0] if total_times else 0,
                "p99": statistics.quantiles(total_times, n=100)[98] if len(total_times) > 10 else max(total_times) if total_times else 0
            },
            "typical_range": {
                "min": min(total_times) if total_times else 0,
                "max": max(total_times) if total_times else 0
            }
        }

        # Performance rating
        analysis["overall_rating"] = self._calculate_performance_rating(analysis)

        return analysis

    def _interpret_predictability(self, cv: float) -> str:
        if cv < 10:
            return "Highly predictable - excellent for setting SLAs"
        elif cv < 25:
            return "Good predictability - suitable for production"
        elif cv < 40:
            return "Moderate variability - may need investigation"
        else:
            return "High variability - investigate sources of inconsistency"

    def _calculate_performance_rating(self, analysis: Dict) -> str:
        queue_health = analysis["queue_analysis"]["health"]
        exec_consistency = analysis["execution_analysis"]["consistency"]
        predictability = analysis.get("predictability", {}).get("score", "UNKNOWN")

        if queue_health == "EXCELLENT" and exec_consistency == "CONSISTENT" and predictability == "EXCELLENT":
            return "⭐ EXCELLENT - Production ready"
        elif queue_health in ["EXCELLENT", "GOOD"] and exec_consistency in ["CONSISTENT", "MOSTLY_CONSISTENT"]:
            return "✅ GOOD - Minor optimizations needed"
        elif queue_health == "POOR" or exec_consistency == "HIGH_VARIATION":
            return "⚠️ NEEDS IMPROVEMENT - Address issues before production"
        else:
            return "⚡ FAIR - Some optimization recommended"

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Queue-based recommendations
        queue_health = analysis["queue_analysis"]["health"]
        if queue_health == "POOR":
            recommendations.append("🔴 Critical: Reduce queue times by adding runners or optimizing dispatch rate")
        elif queue_health == "MODERATE":
            recommendations.append("🟡 Consider adding 1-2 runners to improve queue performance")

        # Consistency recommendations
        if analysis["execution_analysis"]["consistency"] == "HIGH_VARIATION":
            recommendations.append("🔴 Investigate sources of execution time variance")

        # Predictability recommendations
        if analysis["predictability"]["coefficient_variation"] > 40:
            recommendations.append("🟡 High variability detected - establish more consistent baselines")

        return recommendations


class LoadTestAnalyzer(BaseTestAnalyzer):
    """
    Load Test Analysis
    Focus: Sustained performance, throughput, degradation patterns
    """

    def get_key_metrics(self) -> List[str]:
        return ["throughput", "degradation_rate", "sustained_performance", "error_rate"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze load test results focusing on sustained performance."""
        analysis = {
            "test_type": "load",
            "timestamp": datetime.now().isoformat(),
            "focus": "Sustained load handling and throughput"
        }

        # Time-based analysis (divide test into intervals)
        total_duration = metrics.get('duration_minutes', 30)
        queue_times = metrics.get('queue_times', [])
        exec_times = metrics.get('execution_times', [])

        # Analyze degradation over time
        if queue_times and len(queue_times) > 10:
            # Split into thirds to see progression
            third = len(queue_times) // 3
            early_queues = queue_times[:third]
            mid_queues = queue_times[third:2*third]
            late_queues = queue_times[2*third:]

            early_avg = statistics.mean(early_queues) if early_queues else 0
            mid_avg = statistics.mean(mid_queues) if mid_queues else 0
            late_avg = statistics.mean(late_queues) if late_queues else 0

            # Calculate degradation
            degradation_pct = ((late_avg - early_avg) / early_avg * 100) if early_avg > 0 else 0

            analysis["degradation_analysis"] = {
                "early_avg_queue": early_avg,
                "mid_avg_queue": mid_avg,
                "late_avg_queue": late_avg,
                "degradation_percent": degradation_pct,
                "pattern": self._classify_degradation(degradation_pct),
                "interpretation": self._interpret_degradation(degradation_pct)
            }

        # Throughput analysis
        workflow_count = metrics.get('job_count', 0)
        if total_duration > 0:
            throughput_per_min = workflow_count / total_duration
            throughput_per_hour = throughput_per_min * 60

            analysis["throughput_analysis"] = {
                "workflows_per_minute": throughput_per_min,
                "workflows_per_hour": throughput_per_hour,
                "sustained": throughput_per_min > 1.0,  # Assuming 1 wf/min is minimum acceptable
                "rating": self._rate_throughput(throughput_per_min, metrics.get('runner_count', 4))
            }

        # Error analysis
        failed = metrics.get('failed_workflows', 0)
        total = metrics.get('total_workflows', workflow_count)
        error_rate = (failed / total * 100) if total > 0 else 0

        analysis["reliability"] = {
            "error_rate": error_rate,
            "total_failures": failed,
            "reliability_score": "EXCELLENT" if error_rate < 1 else "GOOD" if error_rate < 5 else "FAIR" if error_rate < 10 else "POOR"
        }

        # Load sustainability
        analysis["sustainability"] = self._assess_sustainability(analysis)

        return analysis

    def _classify_degradation(self, degradation_pct: float) -> str:
        if degradation_pct < 10:
            return "STABLE"
        elif degradation_pct < 25:
            return "GRADUAL_DEGRADATION"
        elif degradation_pct < 50:
            return "MODERATE_DEGRADATION"
        else:
            return "SEVERE_DEGRADATION"

    def _interpret_degradation(self, degradation_pct: float) -> str:
        if degradation_pct < 10:
            return "System maintains performance under sustained load"
        elif degradation_pct < 25:
            return "Acceptable degradation - system handles load well"
        elif degradation_pct < 50:
            return "Noticeable degradation - consider optimization"
        else:
            return "Severe degradation - system struggles with sustained load"

    def _rate_throughput(self, per_minute: float, runner_count: int) -> str:
        expected = runner_count / 4  # Assuming 4-minute average job
        ratio = per_minute / expected if expected > 0 else 0

        if ratio > 0.9:
            return "EXCELLENT"
        elif ratio > 0.7:
            return "GOOD"
        elif ratio > 0.5:
            return "FAIR"
        else:
            return "POOR"

    def _assess_sustainability(self, analysis: Dict) -> Dict[str, Any]:
        degradation = analysis.get("degradation_analysis", {}).get("pattern", "UNKNOWN")
        reliability = analysis.get("reliability", {}).get("reliability_score", "UNKNOWN")
        throughput = analysis.get("throughput_analysis", {}).get("rating", "UNKNOWN")

        if degradation == "STABLE" and reliability == "EXCELLENT" and throughput in ["EXCELLENT", "GOOD"]:
            verdict = "HIGHLY_SUSTAINABLE"
            description = "System can handle this load indefinitely"
        elif degradation in ["STABLE", "GRADUAL_DEGRADATION"] and reliability in ["EXCELLENT", "GOOD"]:
            verdict = "SUSTAINABLE"
            description = "System handles load well with acceptable degradation"
        elif degradation == "SEVERE_DEGRADATION" or reliability == "POOR":
            verdict = "NOT_SUSTAINABLE"
            description = "System cannot sustain this load level"
        else:
            verdict = "MARGINALLY_SUSTAINABLE"
            description = "System can handle load but with concerns"

        return {"verdict": verdict, "description": description}

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Degradation recommendations
        degradation = analysis.get("degradation_analysis", {}).get("pattern", "")
        if degradation == "SEVERE_DEGRADATION":
            recommendations.append("🔴 Critical: Severe performance degradation under load - add resources")
        elif degradation == "MODERATE_DEGRADATION":
            recommendations.append("🟡 Noticeable degradation - optimize queue management")

        # Throughput recommendations
        throughput_rating = analysis.get("throughput_analysis", {}).get("rating", "")
        if throughput_rating == "POOR":
            recommendations.append("🔴 Throughput below expectations - review runner capacity")

        # Reliability recommendations
        error_rate = analysis.get("reliability", {}).get("error_rate", 0)
        if error_rate > 5:
            recommendations.append("🟡 High error rate under load - investigate failures")

        # Sustainability recommendations
        sustainability = analysis.get("sustainability", {}).get("verdict", "")
        if sustainability == "NOT_SUSTAINABLE":
            recommendations.append("🔴 Load level is not sustainable - reduce load or add capacity")

        return recommendations


class StressTestAnalyzer(BaseTestAnalyzer):
    """
    Stress Test Analysis
    Focus: Breaking points, failure patterns, recovery behavior
    """

    def get_key_metrics(self) -> List[str]:
        return ["breaking_point", "failure_rate", "max_queue_time", "recovery_time"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze stress test results focusing on system limits."""
        analysis = {
            "test_type": "stress",
            "timestamp": datetime.now().isoformat(),
            "focus": "System limits and failure patterns"
        }

        queue_times = metrics.get('queue_times', [])
        failed = metrics.get('failed_workflows', 0)
        total = metrics.get('total_workflows', 0)

        # Breaking point analysis
        if queue_times:
            max_queue = max(queue_times)
            p95_queue = statistics.quantiles(queue_times, n=20)[18] if len(queue_times) > 1 else queue_times[0]

            analysis["stress_metrics"] = {
                "max_queue_time": max_queue,
                "p95_queue_time": p95_queue,
                "queue_explosion": max_queue > (p95_queue * 2),  # Queue explosion indicator
                "breaking_point_reached": max_queue > 10 or (failed / total > 0.1 if total > 0 else False)
            }

            # Identify when system broke
            if len(queue_times) > 10:
                for i in range(len(queue_times) - 5):
                    window = queue_times[i:i+5]
                    if statistics.mean(window) > 5:  # 5 min queue indicates stress
                        analysis["stress_metrics"]["breaking_point_index"] = i
                        analysis["stress_metrics"]["breaking_point_pct"] = (i / len(queue_times)) * 100
                        break

        # Failure pattern analysis
        analysis["failure_analysis"] = {
            "total_failures": failed,
            "failure_rate": (failed / total * 100) if total > 0 else 0,
            "system_resilience": self._assess_resilience(failed, total, max(queue_times) if queue_times else 0)
        }

        # Stress handling capability
        analysis["stress_handling"] = self._rate_stress_handling(analysis)

        return analysis

    def _assess_resilience(self, failed: int, total: int, max_queue: float) -> str:
        failure_rate = (failed / total * 100) if total > 0 else 0

        if failure_rate < 5 and max_queue < 10:
            return "HIGH_RESILIENCE - System handles stress well"
        elif failure_rate < 10 and max_queue < 15:
            return "MODERATE_RESILIENCE - Acceptable stress handling"
        elif failure_rate < 20:
            return "LOW_RESILIENCE - System struggles under stress"
        else:
            return "POOR_RESILIENCE - System fails under stress"

    def _rate_stress_handling(self, analysis: Dict) -> Dict[str, str]:
        breaking_point = analysis.get("stress_metrics", {}).get("breaking_point_reached", False)
        resilience = analysis.get("failure_analysis", {}).get("system_resilience", "")

        if not breaking_point and "HIGH" in resilience:
            return {
                "rating": "EXCELLENT",
                "description": "System handles extreme stress without breaking"
            }
        elif not breaking_point:
            return {
                "rating": "GOOD",
                "description": "System maintains operation under stress"
            }
        elif "MODERATE" in resilience:
            return {
                "rating": "FAIR",
                "description": "System shows stress but continues operating"
            }
        else:
            return {
                "rating": "POOR",
                "description": "System breaks under stress conditions"
            }

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Breaking point recommendations
        if analysis.get("stress_metrics", {}).get("breaking_point_reached"):
            recommendations.append("🔴 System reached breaking point - critical capacity issue")
            breaking_pct = analysis.get("stress_metrics", {}).get("breaking_point_pct", 100)
            if breaking_pct < 50:
                recommendations.append("🔴 System broke early in test - urgent capacity review needed")

        # Resilience recommendations
        if "POOR" in analysis.get("failure_analysis", {}).get("system_resilience", ""):
            recommendations.append("🔴 Poor stress resilience - implement circuit breakers")
        elif "LOW" in analysis.get("failure_analysis", {}).get("system_resilience", ""):
            recommendations.append("🟡 Low resilience - add retry logic and timeouts")

        # Queue explosion recommendations
        if analysis.get("stress_metrics", {}).get("queue_explosion"):
            recommendations.append("🟡 Queue explosion detected - implement backpressure mechanisms")

        return recommendations


class CapacityTestAnalyzer(BaseTestAnalyzer):
    """
    Capacity Test Analysis
    Focus: Maximum throughput, saturation point, optimal runner count
    """

    def get_key_metrics(self) -> List[str]:
        return ["max_throughput", "saturation_point", "optimal_runners", "efficiency"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze capacity test results focusing on maximum capabilities."""
        analysis = {
            "test_type": "capacity",
            "timestamp": datetime.now().isoformat(),
            "focus": "Maximum system capacity and optimization"
        }

        runner_count = metrics.get('runner_count', 4)
        workflow_count = metrics.get('job_count', 0)
        duration = metrics.get('duration_minutes', 30)
        utilization = metrics.get('runner_utilization', [])

        # Throughput analysis
        if duration > 0:
            actual_throughput = workflow_count / duration
            theoretical_max = runner_count / 4  # Assuming 4-min average job
            efficiency = (actual_throughput / theoretical_max * 100) if theoretical_max > 0 else 0

            analysis["capacity_metrics"] = {
                "actual_throughput": actual_throughput,
                "theoretical_max": theoretical_max,
                "efficiency_percent": efficiency,
                "capacity_utilized": self._classify_capacity_usage(efficiency)
            }

        # Saturation analysis
        if utilization:
            avg_util = statistics.mean(utilization)
            max_util = max(utilization)
            time_at_max = sum(1 for u in utilization if u > 0.95) / len(utilization) * 100

            analysis["saturation_analysis"] = {
                "average_utilization": avg_util * 100,
                "peak_utilization": max_util * 100,
                "time_at_saturation_pct": time_at_max,
                "saturation_state": self._classify_saturation(avg_util, time_at_max)
            }

        # Optimal runner calculation
        queue_times = metrics.get('queue_times', [])
        if queue_times and duration > 0:
            avg_queue = statistics.mean(queue_times)
            if avg_queue > 2:  # If queue > 2 minutes, need more runners
                queue_ratio = avg_queue / 2
                suggested_runners = int(runner_count * queue_ratio)
            else:
                suggested_runners = runner_count

            analysis["optimization"] = {
                "current_runners": runner_count,
                "optimal_runners": suggested_runners,
                "recommendation": self._runner_recommendation(runner_count, suggested_runners, avg_queue)
            }

        # Overall capacity assessment
        analysis["capacity_assessment"] = self._assess_capacity(analysis)

        return analysis

    def _classify_capacity_usage(self, efficiency: float) -> str:
        if efficiency > 90:
            return "NEAR_MAXIMUM"
        elif efficiency > 70:
            return "HIGH_UTILIZATION"
        elif efficiency > 50:
            return "MODERATE_UTILIZATION"
        else:
            return "UNDERUTILIZED"

    def _classify_saturation(self, avg_util: float, time_at_max: float) -> str:
        if avg_util > 0.95 and time_at_max > 50:
            return "OVERSATURATED"
        elif avg_util > 0.85 and time_at_max > 30:
            return "SATURATED"
        elif avg_util > 0.70:
            return "NEAR_SATURATION"
        else:
            return "COMFORTABLE"

    def _runner_recommendation(self, current: int, optimal: int, avg_queue: float) -> str:
        if optimal > current:
            return f"Add {optimal - current} runners to eliminate queue bottleneck"
        elif avg_queue < 0.5:
            return f"Consider reducing to {current - 1} runners (overcapacity)"
        else:
            return "Current runner count is optimal"

    def _assess_capacity(self, analysis: Dict) -> Dict[str, str]:
        efficiency = analysis.get("capacity_metrics", {}).get("efficiency_percent", 0)
        saturation = analysis.get("saturation_analysis", {}).get("saturation_state", "")

        if efficiency > 85 and saturation == "NEAR_SATURATION":
            return {
                "verdict": "OPTIMAL_CAPACITY",
                "description": "System operating at optimal capacity"
            }
        elif saturation == "OVERSATURATED":
            return {
                "verdict": "INSUFFICIENT_CAPACITY",
                "description": "System needs more capacity"
            }
        elif efficiency < 50:
            return {
                "verdict": "EXCESS_CAPACITY",
                "description": "System has excess unused capacity"
            }
        else:
            return {
                "verdict": "ADEQUATE_CAPACITY",
                "description": "System has adequate capacity with room for growth"
            }

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Capacity recommendations
        capacity = analysis.get("capacity_assessment", {}).get("verdict", "")
        if capacity == "INSUFFICIENT_CAPACITY":
            optimal = analysis.get("optimization", {}).get("optimal_runners", 0)
            current = analysis.get("optimization", {}).get("current_runners", 4)
            recommendations.append(f"🔴 Add {optimal - current} runners to meet capacity demands")
        elif capacity == "EXCESS_CAPACITY":
            recommendations.append("💡 Consider reducing runners to save costs")

        # Saturation recommendations
        saturation = analysis.get("saturation_analysis", {}).get("saturation_state", "")
        if saturation == "OVERSATURATED":
            recommendations.append("🔴 System is oversaturated - add capacity immediately")

        # Efficiency recommendations
        efficiency = analysis.get("capacity_metrics", {}).get("efficiency_percent", 0)
        if efficiency < 70:
            recommendations.append("🟡 Low efficiency - investigate dispatch patterns")

        return recommendations


class SpikeTestAnalyzer(BaseTestAnalyzer):
    """
    Spike Test Analysis
    Focus: Response to sudden load, recovery time, elasticity
    """

    def get_key_metrics(self) -> List[str]:
        return ["spike_response_time", "recovery_time", "queue_spillover", "elasticity"]

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze spike test results focusing on sudden load handling."""
        analysis = {
            "test_type": "spike",
            "timestamp": datetime.now().isoformat(),
            "focus": "Response to sudden load increases"
        }

        queue_times = metrics.get('queue_times', [])

        if queue_times and len(queue_times) > 10:
            # Find the spike point (where queue suddenly increases)
            spike_index = self._find_spike_point(queue_times)

            if spike_index:
                pre_spike = queue_times[:spike_index]
                spike_period = queue_times[spike_index:spike_index + 10] if spike_index + 10 < len(queue_times) else queue_times[spike_index:]
                post_spike = queue_times[spike_index + 10:] if spike_index + 10 < len(queue_times) else []

                analysis["spike_response"] = {
                    "pre_spike_avg": statistics.mean(pre_spike) if pre_spike else 0,
                    "spike_peak": max(spike_period) if spike_period else 0,
                    "spike_avg": statistics.mean(spike_period) if spike_period else 0,
                    "response_multiplier": max(spike_period) / statistics.mean(pre_spike) if pre_spike and statistics.mean(pre_spike) > 0 else 0
                }

                # Recovery analysis
                if post_spike:
                    recovery_time = self._calculate_recovery_time(post_spike, pre_spike)
                    analysis["recovery"] = {
                        "recovery_time_periods": recovery_time,
                        "post_spike_avg": statistics.mean(post_spike),
                        "recovered": statistics.mean(post_spike) < statistics.mean(pre_spike) * 1.2 if pre_spike else False,
                        "recovery_quality": self._assess_recovery_quality(pre_spike, post_spike)
                    }

            # Elasticity assessment
            analysis["elasticity"] = self._assess_elasticity(analysis)

        # Spike handling rating
        analysis["spike_handling_rating"] = self._rate_spike_handling(analysis)

        return analysis

    def _find_spike_point(self, queue_times: List[float]) -> Optional[int]:
        """Find where the spike occurs (sudden increase in queue times)."""
        for i in range(1, len(queue_times) - 1):
            if queue_times[i] > queue_times[i-1] * 2:  # Sudden doubling
                return i
        return None

    def _calculate_recovery_time(self, post_spike: List[float], pre_spike: List[float]) -> int:
        """Calculate how many periods it takes to recover to pre-spike levels."""
        baseline = statistics.mean(pre_spike) * 1.2 if pre_spike else 0
        for i, qt in enumerate(post_spike):
            if qt <= baseline:
                return i + 1
        return len(post_spike)

    def _assess_recovery_quality(self, pre_spike: List[float], post_spike: List[float]) -> str:
        if not pre_spike or not post_spike:
            return "UNKNOWN"

        pre_avg = statistics.mean(pre_spike)
        post_avg = statistics.mean(post_spike)

        if post_avg <= pre_avg * 1.1:
            return "FULL_RECOVERY"
        elif post_avg <= pre_avg * 1.3:
            return "GOOD_RECOVERY"
        elif post_avg <= pre_avg * 1.5:
            return "PARTIAL_RECOVERY"
        else:
            return "POOR_RECOVERY"

    def _assess_elasticity(self, analysis: Dict) -> Dict[str, str]:
        response = analysis.get("spike_response", {})
        recovery = analysis.get("recovery", {})

        multiplier = response.get("response_multiplier", 0)
        recovered = recovery.get("recovered", False)

        if multiplier < 3 and recovered:
            return {
                "rating": "HIGHLY_ELASTIC",
                "description": "System handles spikes excellently"
            }
        elif multiplier < 5 and recovered:
            return {
                "rating": "ELASTIC",
                "description": "System handles spikes well"
            }
        elif recovered:
            return {
                "rating": "MODERATELY_ELASTIC",
                "description": "System handles spikes but with strain"
            }
        else:
            return {
                "rating": "RIGID",
                "description": "System struggles with load spikes"
            }

    def _rate_spike_handling(self, analysis: Dict) -> str:
        elasticity = analysis.get("elasticity", {}).get("rating", "")
        recovery = analysis.get("recovery", {}).get("recovery_quality", "")

        if elasticity == "HIGHLY_ELASTIC" and recovery == "FULL_RECOVERY":
            return "⭐ EXCELLENT - Handles spikes seamlessly"
        elif elasticity in ["HIGHLY_ELASTIC", "ELASTIC"] and recovery in ["FULL_RECOVERY", "GOOD_RECOVERY"]:
            return "✅ GOOD - Manages spikes effectively"
        elif elasticity == "RIGID" or recovery == "POOR_RECOVERY":
            return "⚠️ POOR - Cannot handle sudden load changes"
        else:
            return "⚡ FAIR - Some spike handling capability"

    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        recommendations = []

        # Elasticity recommendations
        elasticity = analysis.get("elasticity", {}).get("rating", "")
        if elasticity == "RIGID":
            recommendations.append("🔴 System is rigid - implement auto-scaling or queue management")
        elif elasticity == "MODERATELY_ELASTIC":
            recommendations.append("🟡 Improve elasticity with better queue handling")

        # Recovery recommendations
        recovery = analysis.get("recovery", {}).get("recovery_quality", "")
        if recovery == "POOR_RECOVERY":
            recommendations.append("🔴 Poor recovery from spikes - add burst capacity")
        elif recovery == "PARTIAL_RECOVERY":
            recommendations.append("🟡 Slow recovery - optimize queue processing")

        # Response multiplier recommendations
        multiplier = analysis.get("spike_response", {}).get("response_multiplier", 0)
        if multiplier > 10:
            recommendations.append("🔴 Extreme queue growth during spikes - critical issue")
        elif multiplier > 5:
            recommendations.append("🟡 High spike impact - consider dedicated spike handling")

        return recommendations


class TestAnalyzerFactory:
    """Factory for creating test-specific analyzers."""

    _analyzers = {
        "performance": PerformanceTestAnalyzer,
        "load": LoadTestAnalyzer,
        "stress": StressTestAnalyzer,
        "capacity": CapacityTestAnalyzer,
        "spike": SpikeTestAnalyzer
    }

    @classmethod
    def get_analyzer(cls, test_type: str) -> BaseTestAnalyzer:
        """Get the appropriate analyzer for a test type."""
        analyzer_class = cls._analyzers.get(test_type.lower())
        if not analyzer_class:
            # Default to performance analyzer if unknown
            analyzer_class = PerformanceTestAnalyzer
        return analyzer_class()

    @classmethod
    def list_test_types(cls) -> List[str]:
        """List all supported test types."""
        return list(cls._analyzers.keys())