"""
Metrics Collector for GitHub Runner Performance Testing
Collects, stores, and analyzes workflow execution metrics
"""

import json
import asyncio
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
import aiohttp
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class WorkflowMetrics:
    """Detailed metrics for a workflow run"""
    run_id: int
    workflow_id: str
    test_id: str
    test_type: str = "unknown"

    # Timing metrics (in seconds)
    queue_time: Optional[float] = None
    execution_time: Optional[float] = None
    total_time: Optional[float] = None

    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status
    status: str = "unknown"
    conclusion: Optional[str] = None
    success: bool = False

    # Job metrics
    total_jobs: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    job_metrics: List[Dict] = field(default_factory=list)

    # Additional metadata
    runner_type: Optional[str] = None
    html_url: Optional[str] = None
    repository: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key in ['created_at', 'started_at', 'completed_at']:
            if data[key] and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowMetrics':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        for key in ['created_at', 'started_at', 'completed_at']:
            if data.get(key) and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        return cls(**data)


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across multiple workflow runs"""
    test_id: str
    test_type: str
    total_runs: int
    successful_runs: int
    failed_runs: int

    # Timing statistics (in seconds)
    avg_queue_time: float
    avg_execution_time: float
    avg_total_time: float

    min_queue_time: float
    max_queue_time: float
    p50_queue_time: float
    p95_queue_time: float
    p99_queue_time: float

    min_execution_time: float
    max_execution_time: float
    p50_execution_time: float
    p95_execution_time: float
    p99_execution_time: float

    # Success metrics
    success_rate: float
    failure_rate: float

    # Throughput
    workflows_per_minute: float
    jobs_per_minute: float

    # Time window
    start_time: datetime
    end_time: datetime
    duration_seconds: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat()
        return data


class MetricsStorage:
    """JSON-based metrics storage (can be upgraded to database later)"""

    def __init__(self, storage_path: str = "./metrics"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.current_test_id = None
        self.metrics_buffer = []

    def set_test_id(self, test_id: str):
        """Set current test ID for this session"""
        self.current_test_id = test_id
        self.metrics_buffer = []

    def add_metric(self, metric: WorkflowMetrics):
        """Add a metric to the buffer"""
        self.metrics_buffer.append(metric)

    def save_metrics(self, filename: Optional[str] = None):
        """Save metrics to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{self.current_test_id}_{timestamp}.json"

        filepath = self.storage_path / filename

        data = {
            "test_id": self.current_test_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": [m.to_dict() for m in self.metrics_buffer]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved {len(self.metrics_buffer)} metrics to {filepath}")
        return filepath

    def load_metrics(self, filename: str) -> List[WorkflowMetrics]:
        """Load metrics from JSON file"""
        filepath = self.storage_path / filename

        with open(filepath, 'r') as f:
            data = json.load(f)

        metrics = []
        for metric_data in data.get('metrics', []):
            metrics.append(WorkflowMetrics.from_dict(metric_data))

        return metrics

    def get_all_test_files(self) -> List[Path]:
        """Get all test metric files"""
        return list(self.storage_path.glob("metrics_*.json"))


class MetricsCollector:
    """Collects metrics from GitHub API"""

    def __init__(self, github_token: str, storage: Optional[MetricsStorage] = None):
        self.github_token = github_token
        self.storage = storage or MetricsStorage()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self.session = None

    async def __aenter__(self):
        """Context manager entry"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()

    async def collect_run_metrics(self, owner: str, repo: str, run_id: int) -> WorkflowMetrics:
        """Collect metrics for a single workflow run"""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get run {run_id}: {response.status}")
                    return None

                data = await response.json()

                # Parse timestamps
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                started_at = None
                completed_at = None

                if data.get("run_started_at"):
                    started_at = datetime.fromisoformat(data["run_started_at"].replace("Z", "+00:00"))

                if data.get("updated_at") and data.get("conclusion"):
                    completed_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

                # Calculate timing metrics
                queue_time = None
                execution_time = None
                total_time = None

                if started_at:
                    queue_time = (started_at - created_at).total_seconds()

                if started_at and completed_at:
                    execution_time = (completed_at - started_at).total_seconds()
                    total_time = (completed_at - created_at).total_seconds()

                # Get job metrics
                job_metrics = await self.collect_job_metrics(owner, repo, run_id)

                metrics = WorkflowMetrics(
                    run_id=run_id,
                    workflow_id=data.get("path", "").split("/")[-1],
                    test_id=data.get("name", f"run_{run_id}"),
                    status=data["status"],
                    conclusion=data.get("conclusion"),
                    success=data.get("conclusion") == "success",
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    queue_time=queue_time,
                    execution_time=execution_time,
                    total_time=total_time,
                    html_url=data["html_url"],
                    repository=f"{owner}/{repo}",
                    job_metrics=job_metrics,
                    total_jobs=len(job_metrics),
                    successful_jobs=sum(1 for j in job_metrics if j.get("conclusion") == "success"),
                    failed_jobs=sum(1 for j in job_metrics if j.get("conclusion") == "failure")
                )

                # Store metric
                self.storage.add_metric(metrics)

                return metrics

        except Exception as e:
            logger.error(f"Error collecting metrics for run {run_id}: {str(e)}")
            return None

    async def collect_job_metrics(self, owner: str, repo: str, run_id: int) -> List[Dict]:
        """Collect metrics for all jobs in a workflow run"""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                jobs = []

                for job in data.get("jobs", []):
                    job_started = None
                    job_completed = None

                    if job.get("started_at"):
                        job_started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))

                    if job.get("completed_at"):
                        job_completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))

                    job_duration = None
                    if job_started and job_completed:
                        job_duration = (job_completed - job_started).total_seconds()

                    jobs.append({
                        "id": job["id"],
                        "name": job["name"],
                        "status": job["status"],
                        "conclusion": job.get("conclusion"),
                        "started_at": job_started.isoformat() if job_started else None,
                        "completed_at": job_completed.isoformat() if job_completed else None,
                        "duration_seconds": job_duration,
                        "runner_name": job.get("runner_name"),
                        "runner_id": job.get("runner_id")
                    })

                return jobs

        except Exception as e:
            logger.error(f"Error collecting job metrics: {str(e)}")
            return []

    async def collect_batch_metrics(self, runs: List[tuple]) -> List[WorkflowMetrics]:
        """Collect metrics for multiple workflow runs"""
        tasks = []
        for owner, repo, run_id in runs:
            tasks.append(self.collect_run_metrics(owner, repo, run_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        metrics = []
        for result in results:
            if isinstance(result, WorkflowMetrics):
                metrics.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Error in batch collection: {str(result)}")

        return metrics


class MetricsAnalyzer:
    """Analyzes collected metrics"""

    @staticmethod
    def calculate_percentile(values: List[float], percentile: float) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    @classmethod
    def aggregate_metrics(cls, metrics: List[WorkflowMetrics], test_id: str, test_type: str) -> AggregatedMetrics:
        """Aggregate multiple workflow metrics"""
        if not metrics:
            raise ValueError("No metrics to aggregate")

        # Filter out incomplete metrics
        complete_metrics = [m for m in metrics if m.total_time is not None]

        if not complete_metrics:
            raise ValueError("No complete metrics to aggregate")

        # Extract timing values
        queue_times = [m.queue_time for m in complete_metrics if m.queue_time is not None]
        exec_times = [m.execution_time for m in complete_metrics if m.execution_time is not None]
        total_times = [m.total_time for m in complete_metrics]

        # Calculate time window
        start_times = [m.created_at for m in complete_metrics if m.created_at]
        end_times = [m.completed_at for m in complete_metrics if m.completed_at]

        start_time = min(start_times) if start_times else datetime.now()
        end_time = max(end_times) if end_times else datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Calculate throughput
        workflows_per_minute = (len(complete_metrics) / duration) * 60 if duration > 0 else 0
        total_jobs = sum(m.total_jobs for m in complete_metrics)
        jobs_per_minute = (total_jobs / duration) * 60 if duration > 0 else 0

        return AggregatedMetrics(
            test_id=test_id,
            test_type=test_type,
            total_runs=len(metrics),
            successful_runs=sum(1 for m in metrics if m.success),
            failed_runs=sum(1 for m in metrics if not m.success),

            # Queue time statistics
            avg_queue_time=statistics.mean(queue_times) if queue_times else 0,
            min_queue_time=min(queue_times) if queue_times else 0,
            max_queue_time=max(queue_times) if queue_times else 0,
            p50_queue_time=cls.calculate_percentile(queue_times, 50),
            p95_queue_time=cls.calculate_percentile(queue_times, 95),
            p99_queue_time=cls.calculate_percentile(queue_times, 99),

            # Execution time statistics
            avg_execution_time=statistics.mean(exec_times) if exec_times else 0,
            min_execution_time=min(exec_times) if exec_times else 0,
            max_execution_time=max(exec_times) if exec_times else 0,
            p50_execution_time=cls.calculate_percentile(exec_times, 50),
            p95_execution_time=cls.calculate_percentile(exec_times, 95),
            p99_execution_time=cls.calculate_percentile(exec_times, 99),

            # Total time
            avg_total_time=statistics.mean(total_times),

            # Success metrics
            success_rate=(sum(1 for m in metrics if m.success) / len(metrics)) * 100,
            failure_rate=(sum(1 for m in metrics if not m.success) / len(metrics)) * 100,

            # Throughput
            workflows_per_minute=workflows_per_minute,
            jobs_per_minute=jobs_per_minute,

            # Time window
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration
        )

    @staticmethod
    def print_summary(aggregated: AggregatedMetrics):
        """Print a formatted summary of aggregated metrics"""
        print("\n" + "=" * 60)
        print(f"PERFORMANCE TEST SUMMARY - {aggregated.test_id}")
        print("=" * 60)

        print(f"\nTest Type: {aggregated.test_type}")
        print(f"Duration: {aggregated.duration_seconds:.1f} seconds")
        print(f"Total Runs: {aggregated.total_runs}")
        print(f"Success Rate: {aggregated.success_rate:.1f}%")

        print("\n📊 Queue Time Statistics:")
        print(f"  Average: {aggregated.avg_queue_time:.1f}s")
        print(f"  Min/Max: {aggregated.min_queue_time:.1f}s / {aggregated.max_queue_time:.1f}s")
        print(f"  P50/P95/P99: {aggregated.p50_queue_time:.1f}s / "
              f"{aggregated.p95_queue_time:.1f}s / {aggregated.p99_queue_time:.1f}s")

        print("\n⚡ Execution Time Statistics:")
        print(f"  Average: {aggregated.avg_execution_time:.1f}s")
        print(f"  Min/Max: {aggregated.min_execution_time:.1f}s / {aggregated.max_execution_time:.1f}s")
        print(f"  P50/P95/P99: {aggregated.p50_execution_time:.1f}s / "
              f"{aggregated.p95_execution_time:.1f}s / {aggregated.p99_execution_time:.1f}s")

        print("\n🚀 Throughput:")
        print(f"  Workflows/min: {aggregated.workflows_per_minute:.1f}")
        print(f"  Jobs/min: {aggregated.jobs_per_minute:.1f}")

        print("=" * 60 + "\n")