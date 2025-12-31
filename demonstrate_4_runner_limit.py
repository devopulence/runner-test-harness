#!/usr/bin/env python3
"""
Demonstration script showing the difference between unlimited and 4-runner limited scenarios
This clearly shows how the simulation works
"""

import asyncio
import time
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest
from config_manager import ConfigManager


async def test_without_limit():
    """Test with no concurrency limit (public runner capacity)"""
    print("\n" + "="*60)
    print("TEST 1: WITHOUT 4-RUNNER LIMIT (Public Runner Capacity)")
    print("="*60)
    print("Dispatching 8 workflows with NO limit...")
    print("Expected: All 8 start immediately")
    print("-"*40)

    config = ConfigManager()

    async with GitHubWorkflowDispatcher(
        token=config.github.token,
        max_concurrent=20  # HIGH LIMIT - simulates public runners
    ) as dispatcher:
        requests = []
        for i in range(8):
            requests.append(WorkflowDispatchRequest(
                owner=config.github.owner,
                repo=config.github.repo,
                workflow_id="simple_test.yml",
                ref="main",
                test_id=f"no_limit_{i}",
                inputs={"complexity": "simple"}
            ))

        start_time = time.time()
        print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")

        # Track dispatch times
        dispatch_times = []
        for i, req in enumerate(requests):
            dispatch_start = time.time()
            run_id = await dispatcher.dispatch_workflow(req)
            dispatch_end = time.time()
            dispatch_times.append(dispatch_end - dispatch_start)
            print(f"  Workflow {i+1}: Dispatched in {dispatch_end - dispatch_start:.1f}s")

        total_dispatch_time = time.time() - start_time
        print(f"\nTotal time to dispatch 8 workflows: {total_dispatch_time:.1f}s")
        print(f"Average dispatch time: {sum(dispatch_times)/len(dispatch_times):.1f}s")

        if total_dispatch_time < 30:
            print("✅ Fast dispatch: All workflows dispatched quickly (no queuing)")
        else:
            print("⚠️ Slow dispatch: Some artificial queuing occurred")


async def test_with_4_limit():
    """Test with 4-runner concurrency limit (OpenShift simulation)"""
    print("\n" + "="*60)
    print("TEST 2: WITH 4-RUNNER LIMIT (OpenShift Simulation)")
    print("="*60)
    print("Dispatching 8 workflows with 4-RUNNER LIMIT...")
    print("Expected: First 4 start, next 4 must wait")
    print("-"*40)

    config = ConfigManager()

    async with GitHubWorkflowDispatcher(
        token=config.github.token,
        max_concurrent=4  # LIMITED TO 4 - simulates OpenShift
    ) as dispatcher:
        requests = []
        for i in range(8):
            requests.append(WorkflowDispatchRequest(
                owner=config.github.owner,
                repo=config.github.repo,
                workflow_id="simple_test.yml",
                ref="main",
                test_id=f"limit_4_{i}",
                inputs={"complexity": "simple"}
            ))

        start_time = time.time()
        print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")

        # Track dispatch times
        dispatch_times = []
        dispatch_tasks = []

        # Create tasks for parallel dispatch (but limited by semaphore)
        for i, req in enumerate(requests):
            task = asyncio.create_task(dispatch_with_timing(dispatcher, req, i))
            dispatch_tasks.append(task)

        # Wait for all dispatches
        results = await asyncio.gather(*dispatch_tasks)

        total_dispatch_time = time.time() - start_time
        print(f"\nTotal time to dispatch 8 workflows: {total_dispatch_time:.1f}s")

        # Analyze the pattern
        first_four_times = [r[1] for r in results[:4]]
        second_four_times = [r[1] for r in results[4:]]

        if max(first_four_times) < 20:
            print("✅ First 4 workflows: Dispatched quickly")

        if min(second_four_times) > max(first_four_times):
            print("✅ Second 4 workflows: Had to wait (simulated queue)")
            avg_wait = sum(second_four_times) / len(second_four_times) - sum(first_four_times) / len(first_four_times)
            print(f"   Average additional wait time: {avg_wait:.1f}s")


async def dispatch_with_timing(dispatcher, request, index):
    """Helper function to dispatch and track timing"""
    start = time.time()
    run_id = await dispatcher.dispatch_workflow(request)
    elapsed = time.time() - start
    print(f"  Workflow {index+1}: Dispatched in {elapsed:.1f}s")
    return (run_id, elapsed)


async def visual_demonstration():
    """Visual demonstration of the queue behavior"""
    print("\n" + "="*60)
    print("VISUAL DEMONSTRATION OF 4-RUNNER LIMIT")
    print("="*60)

    print("\n🚫 WITHOUT LIMIT (Public Runners):")
    print("   Time 0s: [W1] [W2] [W3] [W4] [W5] [W6] [W7] [W8] ← All dispatch immediately")
    print("   Time 1s: 🏃🏃🏃🏃🏃🏃🏃🏃 ← All running on different runners")

    print("\n✅ WITH 4-RUNNER LIMIT (OpenShift Simulation):")
    print("   Time 0s: [W1] [W2] [W3] [W4] ← Dispatch")
    print("            [W5] [W6] [W7] [W8] ← Waiting in our queue")
    print("   Time 1s: 🏃🏃🏃🏃 ← Only 4 running")
    print("            ⏳⏳⏳⏳ ← 4 waiting")
    print("   Time 30s: [W1]✓ → [W5] starts")
    print("            🏃🏃🏃🏃 ← Still only 4 running")


async def main():
    """Run demonstration"""
    print("\n" + "="*70)
    print("4-RUNNER LIMIT DEMONSTRATION")
    print("Showing the difference between unlimited and 4-runner scenarios")
    print("="*70)

    # Check token
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN not set")
        print("Set it with: export GITHUB_TOKEN='your_token'")
        sys.exit(1)

    # Visual explanation first
    await visual_demonstration()

    print("\n" + "="*70)
    print("RUNNING ACTUAL TESTS")
    print("="*70)

    # User choice
    print("\nWhich test would you like to run?")
    print("1. Test WITHOUT limit (public runner capacity)")
    print("2. Test WITH 4-runner limit (OpenShift simulation)")
    print("3. Run BOTH to see the difference")

    try:
        choice = input("\nEnter choice (1/2/3): ").strip()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(0)

    if choice == "1":
        await test_without_limit()
    elif choice == "2":
        await test_with_4_limit()
    elif choice == "3":
        await test_without_limit()
        await test_with_4_limit()

        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)
        print("Without Limit: All 8 workflows dispatch immediately")
        print("With 4-Limit:  First 4 dispatch, next 4 wait")
        print("\nThis simulates what will happen on your 4-runner OpenShift!")
    else:
        print("Invalid choice")

    print("\n" + "="*70)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nKey Takeaway:")
    print("The max_concurrent setting artificially limits our dispatcher")
    print("to simulate having only 4 runners, even on public GitHub.")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())