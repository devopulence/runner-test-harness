"""
Test Scenario Runner Module
Executes various performance test scenarios against GitHub runners
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import random
import statistics
import os
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.orchestrator.environment_switcher import EnvironmentConfig, TestProfile
from src.orchestrator.workflow_tracker import WorkflowTracker
from src.orchestrator.enhanced_metrics import EnhancedMetrics
from src.orchestrator.test_run_tracker import TestRunTracker
from main import trigger_workflow_dispatch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WorkflowRun:
    """Represents a single workflow run"""
    workflow_name: str
    run_id: Optional[int] = None
    status: str = "pending"
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    queue_time: Optional[float] = None
    execution_time: Optional[float] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tracking_id: Optional[str] = None


@dataclass
class TestMetrics:
    """Metrics collected during test execution"""
    total_workflows: int = 0
    successful_workflows: int = 0
    failed_workflows: int = 0
    queue_times: List[float] = field(default_factory=list)
    execution_times: List[float] = field(default_factory=list)
    throughput_per_minute: List[float] = field(default_factory=list)
    runner_utilization: List[float] = field(default_factory=list)
    concurrent_jobs: List[int] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate statistical metrics"""
        stats = {
            "total_workflows": self.total_workflows,
            "successful_workflows": self.successful_workflows,
            "failed_workflows": self.failed_workflows,
            "success_rate": self.successful_workflows / self.total_workflows if self.total_workflows > 0 else 0,
            "duration_minutes": (self.end_time - self.start_time).total_seconds() / 60 if self.start_time and self.end_time else 0
        }

        # Queue time statistics
        if self.queue_times:
            stats["queue_time"] = {
                "min": min(self.queue_times),
                "max": max(self.queue_times),
                "mean": statistics.mean(self.queue_times),
                "median": statistics.median(self.queue_times),
                "p95": statistics.quantiles(self.queue_times, n=20)[18] if len(self.queue_times) > 1 else self.queue_times[0],
                "stdev": statistics.stdev(self.queue_times) if len(self.queue_times) > 1 else 0
            }

        # Execution time statistics
        if self.execution_times:
            stats["execution_time"] = {
                "min": min(self.execution_times),
                "max": max(self.execution_times),
                "mean": statistics.mean(self.execution_times),
                "median": statistics.median(self.execution_times),
                "p95": statistics.quantiles(self.execution_times, n=20)[18] if len(self.execution_times) > 1 else self.execution_times[0],
                "stdev": statistics.stdev(self.execution_times) if len(self.execution_times) > 1 else 0
            }

        # Throughput statistics
        if self.throughput_per_minute:
            stats["throughput"] = {
                "min": min(self.throughput_per_minute),
                "max": max(self.throughput_per_minute),
                "mean": statistics.mean(self.throughput_per_minute),
                "total_jobs_per_hour": statistics.mean(self.throughput_per_minute) * 60
            }

        # Runner utilization
        if self.runner_utilization:
            stats["runner_utilization"] = {
                "min": min(self.runner_utilization),
                "max": max(self.runner_utilization),
                "mean": statistics.mean(self.runner_utilization)
            }

        return stats


class ScenarioRunner:
    """
    Executes test scenarios against GitHub runners
    """

    def __init__(self, environment: EnvironmentConfig, github_token: str):
        """
        Initialize the scenario runner

        Args:
            environment: Environment configuration
            github_token: GitHub authentication token
        """
        self.environment = environment
        self.github_token = github_token
        self.active_workflows: Dict[str, WorkflowRun] = {}
        self.completed_workflows: List[WorkflowRun] = []
        self.metrics = TestMetrics()

        # GitHub API client setup
        self.github_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # Initialize workflow tracker
        self.tracker = WorkflowTracker(
            github_token=github_token,
            owner=environment.github_owner,
            repo=environment.github_repo
        )

        # Initialize enhanced metrics
        self.enhanced_metrics = EnhancedMetrics()

        # Test control flags
        self.test_running = False
        self.abort_requested = False
        self.polling_task = None

        # Test run tracker for identifying workflows
        self.test_run_tracker = None

    async def run_test_profile(self, profile_name: str) -> TestMetrics:
        """
        Run a specific test profile

        Args:
            profile_name: Name of the test profile to run

        Returns:
            Test metrics
        """
        profile = self.environment.test_profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Test profile '{profile_name}' not found")

        logger.info(f"Starting test profile: {profile_name}")
        logger.info(f"Duration: {profile.duration_minutes} minutes")
        logger.info(f"Pattern: {profile.dispatch_pattern}")
        logger.info(f"Workflows: {profile.workflows}")

        self.test_running = True
        self.metrics = TestMetrics()
        self.metrics.start_time = datetime.now()

        # Initialize test run tracker for this test
        self.test_run_tracker = TestRunTracker(
            test_type=profile_name,
            environment=self.environment.name if hasattr(self.environment, 'name') else 'aws-ecs'
        )
        logger.info(f"Test Run ID: {self.test_run_tracker.test_run_id}")

        # Start polling task for workflow status updates
        self.polling_task = asyncio.create_task(self._poll_workflow_status())

        try:
            if profile.dispatch_pattern == "steady":
                await self._run_steady_load(profile)
            elif profile.dispatch_pattern == "burst":
                await self._run_burst_load(profile)
            elif profile.dispatch_pattern == "spike":
                await self._run_spike_load(profile)
            else:
                raise ValueError(f"Unknown dispatch pattern: {profile.dispatch_pattern}")
        finally:
            self.test_running = False
            self.metrics.end_time = datetime.now()

            # Stop polling and wait for final updates
            if self.polling_task:
                await asyncio.sleep(5)  # Give time for final updates
                self.polling_task.cancel()
                try:
                    await self.polling_task
                except asyncio.CancelledError:
                    pass

            # Save test run tracking data
            if self.test_run_tracker:
                self.test_run_tracker.save_tracking_data()

        # Calculate final statistics
        stats = self.metrics.calculate_statistics()
        logger.info(f"Test complete. Results: {json.dumps(stats, indent=2)}")

        # Generate enhanced metrics report
        if self.enhanced_metrics.workflows:
            logger.info("Generating enhanced metrics report...")
            report_path = self.enhanced_metrics.generate_report(profile_name, f"test_results/{self.environment.name}")
            logger.info(f"Enhanced report saved to: {report_path}")

        return self.metrics

    async def _run_steady_load(self, profile: TestProfile) -> None:
        """Run steady load test pattern"""
        end_time = datetime.now() + timedelta(minutes=profile.duration_minutes)
        jobs_per_minute = profile.jobs_per_minute or 1.0
        interval = 60 / jobs_per_minute  # Seconds between dispatches

        workflow_index = 0
        while datetime.now() < end_time and not self.abort_requested:
            # Select workflow
            workflow_name = profile.workflows[workflow_index % len(profile.workflows)]
            workflow_index += 1

            # Dispatch workflow
            await self._dispatch_workflow(workflow_name)

            # Wait for next dispatch
            await asyncio.sleep(interval)

            # Update metrics periodically
            if workflow_index % 10 == 0:
                await self._update_metrics()

    async def _run_burst_load(self, profile: TestProfile) -> None:
        """Run burst load test pattern"""
        end_time = datetime.now() + timedelta(minutes=profile.duration_minutes)
        burst_size = profile.burst_size or 4
        burst_interval = profile.burst_interval or 300  # Default 5 minutes

        while datetime.now() < end_time and not self.abort_requested:
            # Send burst of workflows
            logger.info(f"Sending burst of {burst_size} workflows")
            tasks = []
            for i in range(burst_size):
                workflow_name = profile.workflows[i % len(profile.workflows)]
                tasks.append(self._dispatch_workflow(workflow_name))

            # Dispatch all in parallel
            await asyncio.gather(*tasks)

            # Wait for next burst
            await asyncio.sleep(burst_interval)

            # Update metrics
            await self._update_metrics()

    async def _run_spike_load(self, profile: TestProfile) -> None:
        """Run spike load test pattern"""
        end_time = datetime.now() + timedelta(minutes=profile.duration_minutes)
        normal_rate = profile.normal_rate or 0.2
        spike_rate = profile.spike_rate or 2.0
        spike_start = profile.spike_start or 600  # Default 10 minutes
        spike_duration = profile.spike_duration or 300  # Default 5 minutes

        start_time = datetime.now()
        workflow_index = 0

        while datetime.now() < end_time and not self.abort_requested:
            # Determine if we're in spike period
            elapsed = (datetime.now() - start_time).total_seconds()
            in_spike = spike_start <= elapsed < (spike_start + spike_duration)

            # Set rate based on period
            current_rate = spike_rate if in_spike else normal_rate
            interval = 60 / current_rate

            if in_spike and workflow_index == 0:
                logger.info(f"SPIKE STARTED - Rate: {spike_rate} jobs/minute")

            # Dispatch workflow
            workflow_name = profile.workflows[workflow_index % len(profile.workflows)]
            await self._dispatch_workflow(workflow_name)
            workflow_index += 1

            # Wait for next dispatch
            await asyncio.sleep(interval)

            # Check if spike ended
            if not in_spike and elapsed > (spike_start + spike_duration) and workflow_index == 1:
                logger.info(f"SPIKE ENDED - Returning to normal rate: {normal_rate} jobs/minute")

    async def _dispatch_workflow(self, workflow_name: str) -> Optional[WorkflowRun]:
        """
        Dispatch a single workflow

        Args:
            workflow_name: Name of workflow to dispatch

        Returns:
            WorkflowRun object or None if failed
        """
        # Get workflow configuration
        workflow_config = None
        for wf in self.environment.workflows:
            if wf.name == workflow_name:
                workflow_config = wf
                break

        if not workflow_config:
            logger.error(f"Workflow '{workflow_name}' not found in environment")
            return None

        # Prepare inputs
        inputs = workflow_config.default_inputs.copy()

        # Create workflow run object
        run = WorkflowRun(
            workflow_name=workflow_name,
            queued_at=datetime.now(),
            inputs=inputs
        )

        try:
            # Trigger workflow
            logger.info(f"Dispatching workflow: {workflow_name}")

            # Prepare proxies dict if proxy is configured
            proxies = None
            if self.environment.network.get('proxy', {}).get('enabled'):
                proxy_url = self.environment.network['proxy'].get('http_proxy')
                if proxy_url:
                    proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }

            # Use the workflow file as configured
            workflow_path = workflow_config.file

            # Add job_name with test_run_id to inputs for tracking
            workflow_inputs = inputs.copy() if inputs else {}
            if self.test_run_tracker:
                workflow_inputs['job_name'] = self.test_run_tracker.get_job_name()

            trigger_workflow_dispatch(
                owner=self.environment.github_owner,
                repo=self.environment.github_repo,
                workflow_id_or_filename=workflow_path,
                ref="main",  # Or get from config
                inputs=workflow_inputs if workflow_inputs else None,  # Pass dict, not JSON string
                token=self.github_token,
                proxies=proxies,
                ca_bundle=self.environment.network.get('ssl', {}).get('ca_bundle')
            )

            # If we get here without exception, dispatch was successful
            run.status = "queued"
            self.active_workflows[f"{workflow_name}_{time.time()}"] = run
            self.metrics.total_workflows += 1
            logger.info(f"Workflow dispatched successfully: {workflow_name}")

            # Track the workflow for status updates
            tracking_id = await self.tracker.track_workflow(workflow_name, run.queued_at)
            run.tracking_id = tracking_id

            # Record workflow in test run tracker (we'll get the ID later from GitHub API)
            if self.test_run_tracker:
                # For now, record a placeholder - will update with actual ID when polling
                self.test_run_tracker.add_workflow(0, workflow_name)

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            self.metrics.failed_workflows += 1
            logger.error(f"Exception dispatching workflow: {e}")

        return run

    async def _poll_workflow_status(self) -> None:
        """Poll GitHub API for workflow status updates"""
        while self.test_running:
            try:
                # Update all tracked workflows
                summary = await self.tracker.update_all_workflows()

                # Get metrics from tracker
                tracker_metrics = self.tracker.get_metrics()

                # Update our metrics
                self.metrics.queue_times = tracker_metrics["queue_times"]
                self.metrics.execution_times = tracker_metrics["execution_times"]
                self.metrics.successful_workflows = tracker_metrics["successful"]
                self.metrics.failed_workflows = tracker_metrics["failed"]

                # Add completed workflows to enhanced metrics
                for workflow in self.tracker.tracked_workflows.values():
                    if (workflow.get("status") == "completed" and
                        workflow.get("run_id") and
                        workflow.get("run_id") not in [w.get("id") for w in self.enhanced_metrics.workflows]):
                        self.enhanced_metrics.add_workflow(workflow)

                # Get active jobs count
                active_count = await self.tracker.get_active_jobs_count()
                utilization = min(active_count / self.environment.runner_count, 1.0)
                self.metrics.runner_utilization.append(utilization)
                self.metrics.concurrent_jobs.append(active_count)

                # Log status with enhanced metrics
                if self.enhanced_metrics.workflows:
                    stats = self.enhanced_metrics.calculate_statistics()
                    avg_queue = stats["queue_time"].get("mean_minutes", 0)
                    avg_exec = stats["execution_time"].get("mean_minutes", 0)
                    avg_total = stats["total_time"].get("mean_minutes", 0)
                    logger.info(f"Status - Queued: {summary['queued']}, Running: {summary['in_progress']}, "
                              f"Completed: {summary['completed']}, Utilization: {utilization:.1%}")
                    logger.info(f"Avg Times - Queue: {avg_queue:.1f}min, Exec: {avg_exec:.1f}min, Total: {avg_total:.1f}min")
                else:
                    logger.info(f"Status - Queued: {summary['queued']}, Running: {summary['in_progress']}, "
                              f"Completed: {summary['completed']}, Utilization: {utilization:.1%}")

            except Exception as e:
                logger.error(f"Error polling workflow status: {e}")

            # Poll every 30 seconds
            await asyncio.sleep(30)

    async def _update_metrics(self) -> None:
        """Update metrics based on current state"""
        # This is now handled by _poll_workflow_status
        pass

    def abort_test(self) -> None:
        """Request test abortion"""
        logger.warning("Test abort requested")
        self.abort_requested = True

    async def run_performance_test(self) -> TestMetrics:
        """Run performance baseline test"""
        return await self.run_test_profile("performance")

    async def run_capacity_test(self) -> TestMetrics:
        """Run capacity test"""
        return await self.run_test_profile("capacity")

    async def run_stress_test(self) -> TestMetrics:
        """Run stress test"""
        return await self.run_test_profile("stress")

    async def run_load_test(self) -> TestMetrics:
        """Run load test"""
        return await self.run_test_profile("load")

    async def run_spike_test(self) -> TestMetrics:
        """Run spike test"""
        return await self.run_test_profile("spike")

    def generate_report(self, metrics: TestMetrics, output_dir: str = "test_results") -> str:
        """
        Generate test report

        Args:
            metrics: Test metrics to report
            output_dir: Directory to save report

        Returns:
            Path to report file
        """
        # Create output directory
        output_path = Path(output_dir) / self.environment.name
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate report filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_path / f"test_report_{timestamp}.json"

        # Prepare report data
        report = {
            "environment": {
                "name": self.environment.name,
                "type": self.environment.type,
                "runner_count": self.environment.runner_count,
                "runner_labels": self.environment.runner_labels
            },
            "test_execution": {
                "start_time": metrics.start_time.isoformat() if metrics.start_time else None,
                "end_time": metrics.end_time.isoformat() if metrics.end_time else None,
                "duration_minutes": (metrics.end_time - metrics.start_time).total_seconds() / 60
                                  if metrics.start_time and metrics.end_time else 0
            },
            "metrics": metrics.calculate_statistics(),
            "raw_data": {
                "queue_times": metrics.queue_times,
                "execution_times": metrics.execution_times,
                "runner_utilization": metrics.runner_utilization,
                "concurrent_jobs": metrics.concurrent_jobs
            }
        }

        # Save report
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Report saved to: {report_file}")
        return str(report_file)


# Example usage
async def main():
    """Example usage of ScenarioRunner"""
    from src.orchestrator.environment_switcher import EnvironmentSwitcher

    # Initialize environment
    switcher = EnvironmentSwitcher()
    environment = switcher.load_environment("aws_ecs")

    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable not set")
        return

    # Create runner
    runner = ScenarioRunner(environment, github_token)

    # Run a test
    try:
        metrics = await runner.run_performance_test()
        report_path = runner.generate_report(metrics)
        print(f"Test complete. Report: {report_path}")
    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())