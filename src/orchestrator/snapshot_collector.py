"""
Snapshot Collector Module
Persists all GitHub API poll data to JSON for accurate metrics calculation.

Every 30-second poll captures complete workflow/job/runner data.
No data is discarded. All metrics calculated from persisted snapshots.
"""

import json
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyMetrics:
    """Final calculated concurrency metrics from snapshots"""
    # Workflows
    max_concurrent_workflows: int = 0
    avg_concurrent_workflows: float = 0.0
    min_concurrent_workflows: int = 0

    # Jobs
    max_concurrent_jobs: int = 0
    avg_concurrent_jobs: float = 0.0
    min_concurrent_jobs: int = 0

    # Runners (auto-discovered)
    max_concurrent_runners: int = 0
    avg_concurrent_runners: float = 0.0
    total_unique_runners: int = 0
    discovered_runners: List[str] = field(default_factory=list)

    # Sample count
    total_snapshots: int = 0


class SnapshotCollector:
    """
    Collects and persists all GitHub API poll data.

    Every poll captures:
    - All in-progress workflow runs (our tracked ones)
    - All jobs for each workflow run
    - Runner names from job data (auto-discovered)
    - Timestamps for everything

    Data is persisted incrementally to a JSON file.
    Final metrics are calculated from the complete dataset.
    """

    def __init__(self, test_run_id: str, environment: str, output_dir: str = "test_results"):
        """
        Initialize the snapshot collector.

        Args:
            test_run_id: Unique identifier for this test run
            environment: Environment name (e.g., "openshift-sandbox")
            output_dir: Base directory for output files
        """
        self.test_run_id = test_run_id
        self.environment = environment
        self.output_dir = Path(output_dir) / environment
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.snapshots_file = self.output_dir / f"{test_run_id}_snapshots.json"

        # In-memory storage
        self.snapshots: List[Dict[str, Any]] = []
        self.all_discovered_runners: Set[str] = set()

        # Initialize the file
        self._init_file()

        logger.info(f"Snapshot collector initialized: {self.snapshots_file}")

    def _init_file(self):
        """Initialize the JSON file with metadata"""
        initial_data = {
            "test_run_id": self.test_run_id,
            "environment": self.environment,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "snapshots": []
        }
        with open(self.snapshots_file, 'w') as f:
            json.dump(initial_data, f, indent=2)

    def add_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Add a snapshot from a poll cycle.

        Args:
            snapshot: Dict containing:
                - timestamp: When the snapshot was taken
                - workflows: List of workflow run data
                - Each workflow contains its jobs with runner info
        """
        # Add timestamp if not present
        if "timestamp" not in snapshot:
            snapshot["timestamp"] = datetime.now().isoformat()

        # Extract runner names from this snapshot
        for workflow in snapshot.get("workflows", []):
            for job in workflow.get("jobs", []):
                runner_name = job.get("runner_name")
                if runner_name:
                    self.all_discovered_runners.add(runner_name)

        # Store in memory
        self.snapshots.append(snapshot)

        # Append to file (read, update, write)
        self._append_to_file(snapshot)

        # Log summary
        wf_count = len(snapshot.get("workflows", []))
        job_count = sum(len(w.get("jobs", [])) for w in snapshot.get("workflows", []))
        active_jobs = sum(
            1 for w in snapshot.get("workflows", [])
            for j in w.get("jobs", [])
            if j.get("status") == "in_progress"
        )
        active_runners = set(
            j.get("runner_name")
            for w in snapshot.get("workflows", [])
            for j in w.get("jobs", [])
            if j.get("status") == "in_progress" and j.get("runner_name")
        )

        logger.info(f"Snapshot #{len(self.snapshots)}: "
                   f"workflows={wf_count}, jobs={job_count}, "
                   f"active_jobs={active_jobs}, active_runners={len(active_runners)}")

    def _append_to_file(self, snapshot: Dict[str, Any]) -> None:
        """Append a snapshot to the JSON file"""
        try:
            with open(self.snapshots_file, 'r') as f:
                data = json.load(f)

            data["snapshots"].append(snapshot)

            with open(self.snapshots_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error appending snapshot to file: {e}")

    def finalize(self) -> None:
        """Mark the collection as complete and update file"""
        try:
            with open(self.snapshots_file, 'r') as f:
                data = json.load(f)

            data["completed_at"] = datetime.now().isoformat()
            data["total_snapshots"] = len(self.snapshots)
            data["discovered_runners"] = list(self.all_discovered_runners)

            with open(self.snapshots_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"Snapshot collection finalized: {len(self.snapshots)} snapshots, "
                       f"{len(self.all_discovered_runners)} unique runners discovered")
        except Exception as e:
            logger.error(f"Error finalizing snapshot file: {e}")

    def calculate_metrics(self) -> ConcurrencyMetrics:
        """
        Calculate concurrency metrics from all collected snapshots.

        Returns:
            ConcurrencyMetrics with max/avg/min for workflows, jobs, runners
        """
        if not self.snapshots:
            logger.warning("No snapshots collected, returning empty metrics")
            return ConcurrencyMetrics()

        # Extract counts from each snapshot
        workflow_counts = []
        job_counts = []
        runner_counts = []

        for snapshot in self.snapshots:
            workflows = snapshot.get("workflows", [])

            # Count in-progress workflows
            in_progress_workflows = [
                w for w in workflows
                if w.get("status") == "in_progress"
            ]
            workflow_counts.append(len(in_progress_workflows))

            # Count in-progress jobs and active runners
            active_jobs = 0
            active_runners = set()

            for workflow in workflows:
                for job in workflow.get("jobs", []):
                    if job.get("status") == "in_progress":
                        active_jobs += 1
                        runner_name = job.get("runner_name")
                        if runner_name:
                            active_runners.add(runner_name)

            job_counts.append(active_jobs)
            runner_counts.append(len(active_runners))

        # Calculate statistics
        metrics = ConcurrencyMetrics(
            # Workflows
            max_concurrent_workflows=max(workflow_counts) if workflow_counts else 0,
            avg_concurrent_workflows=statistics.mean(workflow_counts) if workflow_counts else 0.0,
            min_concurrent_workflows=min(workflow_counts) if workflow_counts else 0,

            # Jobs
            max_concurrent_jobs=max(job_counts) if job_counts else 0,
            avg_concurrent_jobs=statistics.mean(job_counts) if job_counts else 0.0,
            min_concurrent_jobs=min(job_counts) if job_counts else 0,

            # Runners
            max_concurrent_runners=max(runner_counts) if runner_counts else 0,
            avg_concurrent_runners=statistics.mean(runner_counts) if runner_counts else 0.0,
            total_unique_runners=len(self.all_discovered_runners),
            discovered_runners=list(self.all_discovered_runners),

            # Sample count
            total_snapshots=len(self.snapshots)
        )

        return metrics

    def get_snapshots_file_path(self) -> str:
        """Get the path to the snapshots file"""
        return str(self.snapshots_file)

    @classmethod
    def load_from_file(cls, file_path: str) -> 'SnapshotCollector':
        """
        Load a snapshot collector from a previously saved file.

        Args:
            file_path: Path to the snapshots JSON file

        Returns:
            SnapshotCollector with loaded data
        """
        with open(file_path, 'r') as f:
            data = json.load(f)

        collector = cls(
            test_run_id=data["test_run_id"],
            environment=data["environment"]
        )
        collector.snapshots = data.get("snapshots", [])
        collector.all_discovered_runners = set(data.get("discovered_runners", []))

        # Re-extract runners from snapshots if not in file
        if not collector.all_discovered_runners:
            for snapshot in collector.snapshots:
                for workflow in snapshot.get("workflows", []):
                    for job in workflow.get("jobs", []):
                        runner_name = job.get("runner_name")
                        if runner_name:
                            collector.all_discovered_runners.add(runner_name)

        return collector

    def print_summary(self) -> None:
        """Print a summary of collected data and calculated metrics"""
        metrics = self.calculate_metrics()

        print("\n" + "=" * 60)
        print("CONCURRENCY METRICS (from observed snapshots)")
        print("=" * 60)

        print(f"\nSnapshots collected: {metrics.total_snapshots}")

        print(f"\n📊 CONCURRENT WORKFLOWS:")
        print(f"  Max: {metrics.max_concurrent_workflows}")
        print(f"  Avg: {metrics.avg_concurrent_workflows:.1f}")
        print(f"  Min: {metrics.min_concurrent_workflows}")

        print(f"\n⚙️ CONCURRENT JOBS:")
        print(f"  Max: {metrics.max_concurrent_jobs}")
        print(f"  Avg: {metrics.avg_concurrent_jobs:.1f}")
        print(f"  Min: {metrics.min_concurrent_jobs}")

        print(f"\n🖥️ CONCURRENT RUNNERS (auto-discovered):")
        print(f"  Max active at once: {metrics.max_concurrent_runners}")
        print(f"  Avg active: {metrics.avg_concurrent_runners:.1f}")
        print(f"  Total unique runners: {metrics.total_unique_runners}")
        if metrics.discovered_runners:
            print(f"  Runner names: {', '.join(metrics.discovered_runners)}")

        print("\n" + "=" * 60)
