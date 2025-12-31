#!/usr/bin/env python3
"""
Specific test suite for simulating 4-runner OpenShift environment
This tests your workflows as if you only had 4 runners available
"""

import asyncio
import time
from datetime import datetime
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest
from metrics_collector import MetricsCollector, MetricsStorage, MetricsAnalyzer
from config_manager import ConfigManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FourRunnerTestSuite:
    """Test suite specifically for 4-runner capacity scenarios"""

    def __init__(self):
        self.config = ConfigManager()
        self.metrics_storage = MetricsStorage()
        self.max_runners = 4  # OpenShift constraint

    async def test_exact_capacity(self):
        """Test with exactly 4 workflows (matching runner count)"""
        print("\n" + "="*60)
        print("TEST 1: Exact Capacity (4 workflows)")
        print("="*60)
        print("Expected: All 4 workflows run simultaneously")
        print("-"*60)

        test_id = f"4runner_exact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            max_concurrent=4  # Limit to 4 concurrent
        ) as dispatcher:
            # Create exactly 4 workflow requests
            requests = []
            for i in range(4):
                requests.append(WorkflowDispatchRequest(
                    owner=self.config.github.owner,
                    repo=self.config.github.repo,
                    workflow_id="simple_test.yml",
                    ref="main",
                    test_id=f"{test_id}_{i}",
                    inputs={"complexity": "simple"}
                ))

            print(f"Dispatching 4 workflows simultaneously...")
            start_time = time.time()

            # Dispatch all 4 at once
            dispatch_results = await dispatcher.dispatch_batch(requests)

            # Monitor results
            runs_to_monitor = [
                (req.owner, req.repo, run_id)
                for req, run_id in dispatch_results
                if run_id is not None
            ]

            if runs_to_monitor:
                print(f"Monitoring {len(runs_to_monitor)} workflows...")
                metrics = await dispatcher.monitor_batch(runs_to_monitor)

                # Analyze timing
                self._analyze_concurrent_execution(metrics, 4)

        print("-"*60)

    async def test_over_capacity(self):
        """Test with 8 workflows (2x runner capacity)"""
        print("\n" + "="*60)
        print("TEST 2: Over Capacity (8 workflows, 2x runners)")
        print("="*60)
        print("Expected: First 4 run, next 4 queue")
        print("-"*60)

        test_id = f"4runner_over_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            max_concurrent=4  # Simulate 4 runner limit
        ) as dispatcher:
            # Create 8 workflow requests
            requests = []
            for i in range(8):
                requests.append(WorkflowDispatchRequest(
                    owner=self.config.github.owner,
                    repo=self.config.github.repo,
                    workflow_id="simple_test.yml",
                    ref="main",
                    test_id=f"{test_id}_{i}",
                    inputs={"complexity": "simple"}
                ))

            print(f"Dispatching 8 workflows (2x capacity)...")
            start_time = time.time()

            # Dispatch all 8
            dispatch_results = await dispatcher.dispatch_batch(requests)

            # Monitor results
            runs_to_monitor = [
                (req.owner, req.repo, run_id)
                for req, run_id in dispatch_results
                if run_id is not None
            ]

            if runs_to_monitor:
                print(f"Monitoring {len(runs_to_monitor)} workflows...")
                metrics = await dispatcher.monitor_batch(runs_to_monitor)

                # Analyze queueing behavior
                self._analyze_queue_behavior(metrics, 4)

        print("-"*60)

    async def test_sustained_load(self, duration_minutes=10):
        """Test sustained load at exactly 4 workflows per minute"""
        print("\n" + "="*60)
        print(f"TEST 3: Sustained Load (4 wpm for {duration_minutes} minutes)")
        print("="*60)
        print("Expected: Steady throughput without queue growth")
        print("-"*60)

        test_id = f"4runner_sustained_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            max_concurrent=4
        ) as dispatcher:
            all_runs = []
            workflow_counter = 0

            end_time = time.time() + (duration_minutes * 60)

            while time.time() < end_time:
                minute_start = time.time()

                # Dispatch exactly 4 workflows
                batch_requests = []
                for i in range(4):
                    batch_requests.append(WorkflowDispatchRequest(
                        owner=self.config.github.owner,
                        repo=self.config.github.repo,
                        workflow_id="simple_test.yml",
                        ref="main",
                        test_id=f"{test_id}_{workflow_counter}",
                        inputs={"complexity": "simple"}
                    ))
                    workflow_counter += 1

                print(f"Minute {int((time.time() - (end_time - duration_minutes * 60)) / 60) + 1}: "
                      f"Dispatching 4 workflows...")

                # Dispatch this minute's batch
                dispatch_results = await dispatcher.dispatch_batch(batch_requests)

                for req, run_id in dispatch_results:
                    if run_id:
                        all_runs.append((req.owner, req.repo, run_id))

                # Wait for the rest of the minute
                elapsed = time.time() - minute_start
                if elapsed < 60:
                    await asyncio.sleep(60 - elapsed)

            # Monitor all runs
            print(f"\nMonitoring {len(all_runs)} total workflows...")
            metrics = await dispatcher.monitor_batch(all_runs)

            # Analyze sustained performance
            self._analyze_sustained_performance(metrics, duration_minutes)

        print("-"*60)

    async def test_queue_stress(self):
        """Test queue behavior with increasing load"""
        print("\n" + "="*60)
        print("TEST 4: Queue Stress (Progressive overload)")
        print("="*60)
        print("Testing: 4, 6, 8, 10, 12 concurrent workflows")
        print("-"*60)

        test_id = f"4runner_stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for batch_size in [4, 6, 8, 10, 12]:
            print(f"\n>>> Testing {batch_size} concurrent workflows...")

            async with GitHubWorkflowDispatcher(
                token=self.config.github.token,
                max_concurrent=4
            ) as dispatcher:
                requests = []
                for i in range(batch_size):
                    requests.append(WorkflowDispatchRequest(
                        owner=self.config.github.owner,
                        repo=self.config.github.repo,
                        workflow_id="simple_test.yml",
                        ref="main",
                        test_id=f"{test_id}_batch{batch_size}_{i}",
                        inputs={"complexity": "simple"}
                    ))

                # Dispatch batch
                dispatch_results = await dispatcher.dispatch_batch(requests)

                runs_to_monitor = [
                    (req.owner, req.repo, run_id)
                    for req, run_id in dispatch_results
                    if run_id is not None
                ]

                if runs_to_monitor:
                    metrics = await dispatcher.monitor_batch(runs_to_monitor)
                    self._analyze_batch_metrics(metrics, batch_size, 4)

                # Cool down between tests
                await asyncio.sleep(30)

        print("-"*60)

    def _analyze_concurrent_execution(self, metrics, expected_concurrent):
        """Analyze if workflows ran concurrently"""
        if not metrics:
            return

        # Extract start times
        start_times = []
        for m in metrics:
            if m.started_at:
                start_times.append(m.started_at.timestamp())

        if start_times:
            start_times.sort()
            spread = start_times[-1] - start_times[0]

            print(f"\n📊 Concurrency Analysis:")
            print(f"   Workflows: {len(metrics)}")
            print(f"   Start time spread: {spread:.1f} seconds")

            if spread < 10:
                print(f"   ✅ High concurrency: All started within {spread:.1f}s")
            elif spread < 30:
                print(f"   ⚠️  Moderate concurrency: Spread over {spread:.1f}s")
            else:
                print(f"   ❌ Low concurrency: Spread over {spread:.1f}s")

    def _analyze_queue_behavior(self, metrics, runner_limit):
        """Analyze queueing when over capacity"""
        if not metrics:
            return

        # Sort by start time
        sorted_metrics = sorted(metrics, key=lambda m: m.started_at.timestamp() if m.started_at else 0)

        print(f"\n📊 Queue Behavior Analysis:")
        print(f"   Total workflows: {len(metrics)}")
        print(f"   Runner limit: {runner_limit}")

        # Analyze queue times
        queue_times = [m.queue_time_seconds for m in metrics if m.queue_time_seconds]
        if queue_times:
            avg_queue = sum(queue_times) / len(queue_times)
            max_queue = max(queue_times)

            print(f"   Average queue time: {avg_queue:.1f}s")
            print(f"   Max queue time: {max_queue:.1f}s")

            # Identify which workflows had to queue
            immediate = [m for m in metrics if m.queue_time_seconds and m.queue_time_seconds < 10]
            queued = [m for m in metrics if m.queue_time_seconds and m.queue_time_seconds >= 10]

            print(f"   Immediate execution: {len(immediate)}")
            print(f"   Had to queue: {len(queued)}")

    def _analyze_sustained_performance(self, metrics, duration_minutes):
        """Analyze sustained load performance"""
        if not metrics:
            return

        print(f"\n📊 Sustained Load Analysis:")
        print(f"   Duration: {duration_minutes} minutes")
        print(f"   Total workflows: {len(metrics)}")
        print(f"   Target: {4 * duration_minutes} workflows")

        # Calculate actual throughput
        actual_throughput = len(metrics) / duration_minutes

        print(f"   Actual throughput: {actual_throughput:.1f} workflows/minute")
        print(f"   Target throughput: 4.0 workflows/minute")

        # Analyze queue times over time
        queue_times = [m.queue_time_seconds for m in metrics if m.queue_time_seconds]
        if queue_times:
            avg_queue = sum(queue_times) / len(queue_times)
            print(f"   Average queue time: {avg_queue:.1f}s")

            # Check if queue is growing
            first_half = queue_times[:len(queue_times)//2]
            second_half = queue_times[len(queue_times)//2:]

            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)

                if second_avg > first_avg * 1.5:
                    print(f"   ⚠️  Queue growing: {first_avg:.1f}s → {second_avg:.1f}s")
                else:
                    print(f"   ✅ Queue stable: {first_avg:.1f}s → {second_avg:.1f}s")

    def _analyze_batch_metrics(self, metrics, batch_size, runner_limit):
        """Analyze metrics for a specific batch size"""
        if not metrics:
            return

        queue_times = [m.queue_time_seconds for m in metrics if m.queue_time_seconds]
        avg_queue = sum(queue_times) / len(queue_times) if queue_times else 0

        print(f"   Batch {batch_size}: Avg queue time: {avg_queue:.1f}s")

        if batch_size <= runner_limit:
            if avg_queue < 10:
                print(f"   ✅ Within capacity")
        else:
            overflow = batch_size - runner_limit
            print(f"   ⚠️  {overflow} workflows over capacity")


async def main():
    """Run 4-runner test suite"""
    print("\n" + "="*70)
    print("4-RUNNER CAPACITY TEST SUITE")
    print("Simulating OpenShift environment with exactly 4 runners")
    print("="*70)

    # Check token
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN not set")
        sys.exit(1)

    suite = FourRunnerTestSuite()

    # Run tests
    try:
        # Test 1: Exact capacity
        await suite.test_exact_capacity()

        # Test 2: Over capacity
        await suite.test_over_capacity()

        # Test 3: Sustained load (shorter duration for demo)
        await suite.test_sustained_load(duration_minutes=5)

        # Test 4: Queue stress
        await suite.test_queue_stress()

        print("\n" + "="*70)
        print("✅ 4-RUNNER TEST SUITE COMPLETE")
        print("="*70)
        print("\nKey Insights:")
        print("- With 4 runners, you can handle 4 concurrent workflows")
        print("- Additional workflows will queue")
        print("- Sustained load should not exceed 4 workflows/minute")
        print("- Monitor queue depth to prevent overload")
        print("="*70)

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())