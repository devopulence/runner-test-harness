#!/usr/bin/env python3
"""
Simple ECS Fargate Runner Testing with Sleep Workflows
Tests your 4 ECS runners using configurable sleep durations
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest
from config_manager import ConfigManager

class ECSRunnerTester:
    """Simple tester for ECS Fargate runners using sleep workflows"""

    def __init__(self):
        self.config = ConfigManager()
        self.results = []

    async def run_sleep_test(self, sleep_duration: int, job_count: int, test_name: str) -> Dict:
        """
        Run a single test with sleep workflow

        Args:
            sleep_duration: How long each job sleeps (seconds)
            job_count: Number of parallel jobs to run
            test_name: Unique name for this test
        """
        print(f"\n{'='*60}")
        print(f"Test: {test_name}")
        print(f"Jobs: {job_count} | Sleep: {sleep_duration}s")
        print('='*60)

        # Calculate expected behavior with 4 runners
        if job_count <= 4:
            expected_time = sleep_duration
            expected_queue = "No queuing expected"
        else:
            waves = (job_count + 3) // 4  # Ceiling division
            expected_time = sleep_duration * waves
            expected_queue = f"{job_count - 4} jobs will queue"

        print(f"Expected: {expected_time}s total | {expected_queue}")
        print("-"*60)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            max_concurrent=100  # No artificial limit - let ECS handle it
        ) as dispatcher:

            # Create workflow request
            request = WorkflowDispatchRequest(
                owner=self.config.github.owner,
                repo=self.config.github.repo,
                workflow_id="runner_test.yml",
                ref="main",
                test_id=test_name,
                inputs={
                    "test_id": test_name,
                    "sleep_duration": str(sleep_duration),
                    "job_count": str(job_count),
                    "job_type": "parallel"
                }
            )

            # Dispatch workflow
            start_time = time.time()
            print(f"Dispatching workflow at {datetime.now().strftime('%H:%M:%S')}...")

            run_id = await dispatcher.dispatch_workflow(request)

            if not run_id:
                print("❌ Failed to dispatch workflow")
                return None

            print(f"✅ Workflow dispatched: Run ID {run_id}")
            print(f"📍 View at: https://github.com/{self.config.github.owner}/{self.config.github.repo}/actions/runs/{run_id}")

            # Monitor execution
            print(f"⏳ Monitoring execution (timeout: {expected_time + 60}s)...")

            workflow_run = await dispatcher.monitor_run(
                self.config.github.owner,
                self.config.github.repo,
                run_id,
                timeout_seconds=expected_time + 60
            )

            # Calculate results
            actual_time = time.time() - start_time

            result = {
                "test_name": test_name,
                "sleep_duration": sleep_duration,
                "job_count": job_count,
                "expected_time": expected_time,
                "actual_time": actual_time,
                "difference": actual_time - expected_time,
                "queue_time": workflow_run.queue_time_seconds if workflow_run else None,
                "status": workflow_run.conclusion if workflow_run else "unknown"
            }

            # Print results
            print(f"\n📊 Results:")
            print(f"  Expected time: {expected_time}s")
            print(f"  Actual time: {actual_time:.1f}s")
            print(f"  Difference: {result['difference']:.1f}s")

            if workflow_run and workflow_run.queue_time_seconds:
                print(f"  Queue time: {workflow_run.queue_time_seconds:.1f}s")

            print(f"  Status: {result['status']}")

            self.results.append(result)
            return result

    async def run_test_suite(self):
        """Run complete test suite for 4 ECS runners"""
        print("\n" + "="*70)
        print("ECS FARGATE RUNNER TEST SUITE (4 Runners)")
        print("="*70)

        # Test scenarios
        tests = [
            # (sleep_seconds, job_count, test_name)
            (60, 1, "single_job"),        # Under-utilization
            (60, 4, "perfect_fit"),       # Exactly 4 runners
            (60, 6, "slight_overload"),   # 2 jobs queue
            (60, 8, "double_capacity"),   # 4 jobs queue
            (30, 4, "quick_jobs"),        # Quick execution
            (30, 8, "quick_overload"),    # Quick with queue
            (10, 12, "rapid_burst"),      # Many quick jobs
            (120, 4, "long_running"),     # Slow jobs
        ]

        for sleep, jobs, name in tests:
            await self.run_sleep_test(sleep, jobs, name)

            # Wait between tests to let runners clear
            wait_time = 30
            print(f"\n⏳ Waiting {wait_time}s before next test...")
            await asyncio.sleep(wait_time)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)

        print("\n| Test Name | Jobs | Sleep | Expected | Actual | Diff | Status |")
        print("|-----------|------|-------|----------|--------|------|--------|")

        for r in self.results:
            print(f"| {r['test_name']:<13} | {r['job_count']:>4} | {r['sleep_duration']:>5}s | "
                  f"{r['expected_time']:>8}s | {r['actual_time']:>6.1f}s | "
                  f"{r['difference']:>+5.1f}s | {r['status']:<7} |")

        # Calculate throughput
        print("\n📈 Throughput Analysis (4 Runners):")
        print("-"*40)

        for r in self.results:
            if r['actual_time'] > 0:
                throughput = (r['job_count'] / r['actual_time']) * 60
                theoretical = min(4, r['job_count']) * (60 / r['sleep_duration'])
                efficiency = (throughput / theoretical) * 100 if theoretical > 0 else 0

                print(f"{r['test_name']}:")
                print(f"  Actual: {throughput:.1f} jobs/min")
                print(f"  Theoretical: {theoretical:.1f} jobs/min")
                print(f"  Efficiency: {efficiency:.1f}%")


async def quick_capacity_check():
    """Quick check to verify 4 runners are available"""
    print("\n🔍 Quick Capacity Check")
    print("-"*40)

    tester = ECSRunnerTester()

    # Test exactly 4 parallel jobs for 10 seconds
    result = await tester.run_sleep_test(
        sleep_duration=10,
        job_count=4,
        test_name="capacity_check"
    )

    if result and result['actual_time'] < 20:
        print("\n✅ All 4 runners are working correctly!")
        print("   4 jobs completed in parallel as expected")
    else:
        print("\n⚠️  Runner capacity issue detected")
        print("   Check if all 4 ECS tasks are running")


async def main():
    """Main entry point"""

    # Check token
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN not set")
        print("Set it with: export GITHUB_TOKEN='your_token'")
        sys.exit(1)

    print("\n" + "="*70)
    print("ECS FARGATE RUNNER TESTING")
    print("Simple Sleep-Based Workflow Tests")
    print("="*70)

    print("\nTest Options:")
    print("1. Quick capacity check (4 jobs, 10s)")
    print("2. Full test suite (8 different scenarios)")
    print("3. Custom test")

    try:
        choice = input("\nSelect option (1/2/3): ").strip()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(0)

    if choice == "1":
        await quick_capacity_check()

    elif choice == "2":
        tester = ECSRunnerTester()
        await tester.run_test_suite()

    elif choice == "3":
        try:
            sleep = int(input("Sleep duration (seconds): "))
            jobs = int(input("Number of jobs: "))
            name = input("Test name: ") or f"custom_{sleep}s_{jobs}j"

            tester = ECSRunnerTester()
            await tester.run_sleep_test(sleep, jobs, name)

        except (ValueError, KeyboardInterrupt):
            print("\nInvalid input or cancelled")
            sys.exit(1)

    else:
        print("Invalid choice")
        sys.exit(1)

    print("\n✅ Testing complete!")
    print("\n💡 Key Insights:")
    print("- 4 runners = 4 concurrent jobs maximum")
    print("- Jobs beyond 4 must queue")
    print("- Shorter jobs = higher throughput")
    print("- Queue time adds to total execution time")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)