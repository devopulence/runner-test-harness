#!/usr/bin/env python3
"""
Demonstrate how test run tracking would work.
"""
from src.orchestrator.test_run_tracker import TestRunTracker, list_test_runs, load_test_run
from datetime import datetime
import json


def demonstrate():
    """Show how test run tracking solves the workflow identification problem."""

    print("=" * 70)
    print("TEST RUN TRACKING DEMONSTRATION")
    print("=" * 70)

    print("\n📌 PROBLEM: Multiple test runs create confusion")
    print("-" * 40)
    print("Scenario: You run performance tests multiple times")
    print()
    print("8:00 AM - Run #1: python run_test.py -e aws_ecs -t performance")
    print("          → Dispatches 34 workflows")
    print("8:30 AM - Run #2: python run_test.py -e aws_ecs -t performance")
    print("          → Dispatches 34 more workflows")
    print("9:00 AM - Analysis: Which workflows belong to which test?")
    print("          → ❌ No way to tell them apart!")

    print("\n\n✅ SOLUTION: Unique Test Run IDs")
    print("-" * 40)

    # Simulate first test run
    print("\n1️⃣ First Test Run (8:00 AM)")
    tracker1 = TestRunTracker("performance", "aws-ecs")
    print(f"   Generated Test ID: {tracker1.test_run_id}")
    print(f"   Job Name Tag: {tracker1.get_job_name()}")

    # Simulate dispatching workflows
    print("\n   Dispatching workflows with tag...")
    for i in range(1, 4):
        tracker1.add_workflow(20693000 + i, f"build_job_{i}")
        print(f"   - Workflow #{i}: Tagged with '{tracker1.get_job_name()}'")

    # Save tracking
    tracker1.save_tracking_data()

    # Simulate second test run
    print("\n2️⃣ Second Test Run (8:30 AM)")
    tracker2 = TestRunTracker("performance", "aws-ecs")
    print(f"   Generated Test ID: {tracker2.test_run_id}")
    print(f"   Job Name Tag: {tracker2.get_job_name()}")

    print("\n   Dispatching workflows with tag...")
    for i in range(1, 4):
        tracker2.add_workflow(20694000 + i, f"build_job_{i}")
        print(f"   - Workflow #{i}: Tagged with '{tracker2.get_job_name()}'")

    tracker2.save_tracking_data()

    # Show how to identify workflows
    print("\n\n🔍 IDENTIFYING WORKFLOWS")
    print("-" * 40)

    print("\nAll test runs:")
    runs = list_test_runs("aws-ecs")
    for run in runs:
        print(f"  • {run['test_run_id']}")
        print(f"    Type: {run['test_type']}, Workflows: {run['workflow_count']}")

    print("\n\n📊 ANALYZING SPECIFIC TEST RUN")
    print("-" * 40)

    # Load specific test run
    test1_data = load_test_run(tracker1.test_run_id, "aws-ecs")
    print(f"\nTest Run: {test1_data['test_run_id']}")
    print(f"Workflow IDs: {test1_data['workflow_ids']}")
    print(f"Query: Look for workflows with job_name='{test1_data['metadata']['job_name_tag']}'")

    print("\n\n💡 HOW IT WORKS")
    print("-" * 40)
    print("""
1. Each test run gets a unique ID (e.g., 'performance_20260104_093000_abc123')

2. Every workflow dispatched includes this ID in the 'job_name' input:
   {
     "workload_type": "standard",
     "job_name": "performance_20260104_093000_abc123"
   }

3. The tracking file saves:
   - Test run ID
   - Start/end times
   - List of workflow IDs
   - The job_name tag used

4. Analysis can then:
   - Load the tracking file
   - Find ONLY workflows with that job_name
   - Or use the time window + workflow IDs
   - Produce accurate metrics for THAT specific test run

5. Benefits:
   ✅ Run multiple tests without confusion
   ✅ Analyze any past test run precisely
   ✅ Compare different test runs accurately
   ✅ No mixing of results from different runs
""")

    print("\n📝 USAGE")
    print("-" * 40)
    print("""
# List all test runs
python analyze_specific_test.py --list

# Analyze the latest test run
python analyze_specific_test.py

# Analyze a specific test run
python analyze_specific_test.py --test-run-id performance_20260104_093000_abc123
""")


if __name__ == "__main__":
    demonstrate()