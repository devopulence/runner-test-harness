"""
Standardized reporting module for all test types.
Provides consistent metrics across performance, load, stress, capacity tests.
"""
from typing import Dict, List, Any
from datetime import datetime
import json
from pathlib import Path


class StandardizedReport:
    """Generate standardized reports for any test type with consistent metrics."""

    def __init__(self, test_type: str, environment: str):
        self.test_type = test_type
        self.environment = environment
        self.metrics = {
            'queue_times': [],
            'execution_times': [],
            'total_times': []
        }

    def add_job_metrics(self, queue_time: float, execution_time: float, total_time: float):
        """Add metrics for a single job."""
        self.metrics['queue_times'].append(queue_time)
        self.metrics['execution_times'].append(execution_time)
        self.metrics['total_times'].append(total_time)

    def calculate_statistics(self, values: List[float]) -> Dict[str, float]:
        """Calculate min, max, avg, p95 for a list of values."""
        if not values:
            return {'min': 0, 'max': 0, 'avg': 0, 'p95': 0}

        sorted_values = sorted(values)
        p95_index = int(len(sorted_values) * 0.95)

        return {
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'p95': sorted_values[p95_index] if p95_index < len(sorted_values) else max(values)
        }

    def generate_report(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate standardized report structure."""

        # Calculate statistics
        queue_stats = self.calculate_statistics(self.metrics['queue_times'])
        exec_stats = self.calculate_statistics(self.metrics['execution_times'])
        total_stats = self.calculate_statistics(self.metrics['total_times'])

        # Calculate derived metrics
        total_jobs = len(self.metrics['total_times'])
        jobs_queued = sum(1 for q in self.metrics['queue_times'] if q > 0.1)  # > 6 seconds

        queue_pct = 0
        if sum(self.metrics['total_times']) > 0:
            queue_pct = (sum(self.metrics['queue_times']) / sum(self.metrics['total_times'])) * 100

        report = {
            'test_metadata': {
                'test_type': self.test_type,
                'environment': self.environment,
                'timestamp': datetime.utcnow().isoformat(),
                'duration_minutes': test_config.get('duration_minutes', 0),
                'runners_detected': test_config.get('runner_count', 0)
            },

            'workload': {
                'total_workflows': test_config.get('total_workflows', total_jobs),
                'dispatch_rate': test_config.get('dispatch_rate', 0),
                'workflow_type': test_config.get('workflow_type', 'unknown')
            },

            # Developer-focused metrics (what users experience)
            'developer_metrics': {
                'total_time': {
                    'average': total_stats['avg'],
                    'minimum': total_stats['min'],
                    'maximum': total_stats['max'],
                    'p95': total_stats['p95'],
                    'unit': 'minutes'
                },
                'summary': f"Jobs take {total_stats['avg']:.1f} minutes on average (range: {total_stats['min']:.1f}-{total_stats['max']:.1f} min)"
            },

            # DevOps-focused metrics (system performance)
            'devops_metrics': {
                'queue_time': {
                    'average': queue_stats['avg'],
                    'minimum': queue_stats['min'],
                    'maximum': queue_stats['max'],
                    'jobs_queued': jobs_queued,
                    'total_jobs': total_jobs,
                    'queued_percentage': (jobs_queued / total_jobs * 100) if total_jobs > 0 else 0,
                    'unit': 'minutes'
                },
                'execution_time': {
                    'average': exec_stats['avg'],
                    'minimum': exec_stats['min'],
                    'maximum': exec_stats['max'],
                    'unit': 'minutes'
                },
                'time_breakdown': {
                    'queue_percentage': queue_pct,
                    'execution_percentage': 100 - queue_pct
                }
            },

            'runner_metrics': {
                'utilization': test_config.get('runner_utilization', {}),
                'runner_count': test_config.get('runner_count', 0),
                'runner_labels': test_config.get('runner_labels', [])
            },

            'throughput': {
                'completed_workflows': total_jobs,
                'success_rate': test_config.get('success_rate', 100),
                'average_throughput_per_hour': (total_jobs / test_config.get('duration_minutes', 30)) * 60 if test_config.get('duration_minutes') else 0
            },

            'raw_metrics': self.metrics
        }

        return report

    def save_report(self, report: Dict[str, Any], output_dir: str = "test_results"):
        """Save report to JSON and return path."""
        output_path = Path(output_dir) / f"{self.test_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        return output_path

    def format_summary(self, report: Dict[str, Any]) -> str:
        """Generate human-readable summary."""
        dev = report['developer_metrics']
        ops = report['devops_metrics']

        summary = f"""
📊 {report['test_metadata']['test_type'].upper()} TEST RESULTS
{'=' * 60}

Environment: {report['test_metadata']['environment']}
Runners: {report['test_metadata']['runners_detected']}
Duration: {report['test_metadata']['duration_minutes']:.1f} minutes

FOR DEVELOPERS:
  • Average Total Time: {dev['total_time']['average']:.1f} minutes
  • Range: {dev['total_time']['minimum']:.1f} - {dev['total_time']['maximum']:.1f} minutes

FOR DEVOPS:
  • Queue Time: {ops['queue_time']['average']:.1f} min avg (max: {ops['queue_time']['maximum']:.1f} min)
  • Execution Time: {ops['execution_time']['average']:.1f} min avg
  • Queue Impact: {ops['time_breakdown']['queue_percentage']:.1f}% of total time
  • Jobs Queued: {ops['queue_time']['jobs_queued']}/{ops['queue_time']['total_jobs']} ({ops['queue_time']['queued_percentage']:.1f}%)

THROUGHPUT:
  • Completed: {report['throughput']['completed_workflows']} workflows
  • Rate: {report['throughput']['average_throughput_per_hour']:.1f} jobs/hour
"""
        return summary