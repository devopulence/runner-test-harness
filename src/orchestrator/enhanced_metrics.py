"""
Enhanced Metrics Module
Properly tracks queue time, execution time, and total time for capacity analysis
"""

import json
import statistics
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class EnhancedMetrics:
    """
    Enhanced metrics tracking that separates:
    - Queue Time: Time waiting for available runner
    - Execution Time: Time running on runner (includes overhead)
    - Step Time: Time actually executing workflow steps
    - Total Time: Queue + Execution (what users experience)
    """

    def __init__(self):
        self.workflows = []
        self.queue_times = []
        self.execution_times = []
        self.total_times = []
        self.step_times = []  # If we can extract from GitHub

    def add_workflow(self, workflow_data: Dict):
        """Add a completed workflow's metrics"""
        queue_time = workflow_data.get("queue_time", 0)
        execution_time = workflow_data.get("execution_time", 0)
        total_time = queue_time + execution_time

        self.workflows.append({
            "id": workflow_data.get("run_id"),
            "name": workflow_data.get("workflow_name"),
            "queue_time": queue_time,
            "execution_time": execution_time,
            "total_time": total_time,
            "queued_at": workflow_data.get("queued_at"),
            "started_at": workflow_data.get("started_at"),
            "completed_at": workflow_data.get("completed_at")
        })

        self.queue_times.append(queue_time)
        self.execution_times.append(execution_time)
        self.total_times.append(total_time)

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive statistics for all three metrics"""
        stats = {
            "workflow_count": len(self.workflows),
            "queue_time": self._calculate_metric_stats(self.queue_times),
            "execution_time": self._calculate_metric_stats(self.execution_times),
            "total_time": self._calculate_metric_stats(self.total_times)
        }

        # Calculate capacity insights
        if self.execution_times:
            avg_execution = statistics.mean(self.execution_times)
            stats["capacity_insights"] = {
                "avg_execution_minutes": avg_execution / 60,
                "theoretical_throughput_per_runner_per_hour": 3600 / avg_execution if avg_execution > 0 else 0,
                "theoretical_throughput_4_runners_per_hour": (3600 / avg_execution * 4) if avg_execution > 0 else 0
            }

        # Calculate queue growth rate
        if len(self.queue_times) > 1:
            # Check if queue times are increasing
            first_half = self.queue_times[:len(self.queue_times)//2]
            second_half = self.queue_times[len(self.queue_times)//2:]

            if first_half and second_half:
                first_avg = statistics.mean(first_half)
                second_avg = statistics.mean(second_half)
                queue_growth = second_avg - first_avg
                stats["queue_growth"] = {
                    "first_half_avg_minutes": first_avg / 60,
                    "second_half_avg_minutes": second_avg / 60,
                    "growth_minutes": queue_growth / 60,
                    "trend": "increasing" if queue_growth > 0 else "stable" if queue_growth == 0 else "decreasing"
                }

        return stats

    def _calculate_metric_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistics for a metric"""
        if not values:
            return {
                "min": 0,
                "max": 0,
                "mean": 0,
                "median": 0,
                "p95": 0,
                "stdev": 0
            }

        stats = {
            "min_seconds": min(values),
            "max_seconds": max(values),
            "mean_seconds": statistics.mean(values),
            "median_seconds": statistics.median(values),
            "min_minutes": min(values) / 60,
            "max_minutes": max(values) / 60,
            "mean_minutes": statistics.mean(values) / 60,
            "median_minutes": statistics.median(values) / 60
        }

        if len(values) > 1:
            stats["p95_seconds"] = statistics.quantiles(values, n=20)[18]
            stats["p95_minutes"] = stats["p95_seconds"] / 60
            stats["stdev_seconds"] = statistics.stdev(values)
            stats["stdev_minutes"] = stats["stdev_seconds"] / 60
        else:
            stats["p95_seconds"] = values[0]
            stats["p95_minutes"] = values[0] / 60
            stats["stdev_seconds"] = 0
            stats["stdev_minutes"] = 0

        return stats

    def generate_report(self, test_name: str, output_dir: str = "test_results") -> str:
        """Generate enhanced metrics report"""
        stats = self.calculate_statistics()

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"enhanced_report_{test_name}_{timestamp}.json"

        # Prepare report
        report = {
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_workflows": stats["workflow_count"],
                "queue_time_avg_min": stats["queue_time"]["mean_minutes"] if "mean_minutes" in stats["queue_time"] else 0,
                "execution_time_avg_min": stats["execution_time"]["mean_minutes"] if "mean_minutes" in stats["execution_time"] else 0,
                "total_time_avg_min": stats["total_time"]["mean_minutes"] if "mean_minutes" in stats["total_time"] else 0
            },
            "detailed_statistics": stats,
            "workflows": self.workflows
        }

        # Save report
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        # Also print summary to console
        self.print_summary(stats)

        return str(report_file)

    def print_summary(self, stats: Dict[str, Any]):
        """Print a clear summary of the three key metrics"""
        print("\n" + "="*60)
        print("ENHANCED METRICS SUMMARY")
        print("="*60)

        print(f"\nWorkflows Analyzed: {stats['workflow_count']}")

        print("\n📊 QUEUE TIME (waiting for runner):")
        if "queue_time" in stats and "mean_minutes" in stats["queue_time"]:
            qt = stats["queue_time"]
            # Show seconds if queue times are under 1 minute
            if qt['mean_seconds'] < 60:
                print(f"  Average: {qt['mean_seconds']:.1f} seconds")
                print(f"  Max: {qt['max_seconds']:.1f} seconds")
                print(f"  Min: {qt['min_seconds']:.1f} seconds")
            else:
                print(f"  Average: {qt['mean_minutes']:.1f} minutes")
                print(f"  Max: {qt['max_minutes']:.1f} minutes")
                print(f"  Min: {qt['min_minutes']:.1f} minutes")

        print("\n⚙️ EXECUTION TIME (on runner):")
        if "execution_time" in stats and "mean_minutes" in stats["execution_time"]:
            et = stats["execution_time"]
            print(f"  Average: {et['mean_minutes']:.1f} minutes")
            print(f"  Max: {et['max_minutes']:.1f} minutes")
            print(f"  Min: {et['min_minutes']:.1f} minutes")

        print("\n⏱️ TOTAL TIME (queue + execution):")
        if "total_time" in stats and "mean_minutes" in stats["total_time"]:
            tt = stats["total_time"]
            print(f"  Average: {tt['mean_minutes']:.1f} minutes")
            print(f"  Max: {tt['max_minutes']:.1f} minutes")
            print(f"  Min: {tt['min_minutes']:.1f} minutes")

        if "capacity_insights" in stats:
            print("\n🎯 CAPACITY INSIGHTS:")
            ci = stats["capacity_insights"]
            print(f"  Avg execution: {ci['avg_execution_minutes']:.1f} minutes")
            print(f"  Max throughput (4 runners): {ci['theoretical_throughput_4_runners_per_hour']:.1f} jobs/hour")

        if "queue_growth" in stats:
            print("\n📈 QUEUE TREND:")
            qg = stats["queue_growth"]
            # Show seconds if values are under 1 minute
            first_half_sec = qg['first_half_avg_minutes'] * 60
            second_half_sec = qg['second_half_avg_minutes'] * 60
            if first_half_sec < 60 and second_half_sec < 60:
                print(f"  First half avg: {first_half_sec:.1f} seconds")
                print(f"  Second half avg: {second_half_sec:.1f} seconds")
            else:
                print(f"  First half avg: {qg['first_half_avg_minutes']:.1f} minutes")
                print(f"  Second half avg: {qg['second_half_avg_minutes']:.1f} minutes")
            print(f"  Trend: {qg['trend'].upper()}")

        print("\n" + "="*60)