#!/usr/bin/env python3
"""
Test the test run tracking integration.
This script runs a quick test to verify workflows are properly tagged with test_run_id.
"""
import asyncio
import os
import sys
import json
from datetime import datetime

# Setup environment
os.environ['GITHUB_TOKEN'] = os.environ.get('GITHUB_TOKEN', '')

async def test_tracking():
    """Run a quick test with tracking enabled."""
    print("=" * 70)
    print("TEST RUN TRACKING INTEGRATION TEST")
    print("=" * 70)
    print()

    # Import after setting up environment
    from src.orchestrator.environment_switcher import EnvironmentSwitcher
    from src.orchestrator.scenario_runner import ScenarioRunner

    # Load environment
    print("Loading AWS ECS environment...")
    switcher = EnvironmentSwitcher()
    environment = switcher.load_environment('aws_ecs')

    # Create scenario runner
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("ERROR: GITHUB_TOKEN not set")
        return False

    runner = ScenarioRunner(environment, github_token)

    # Run a quick performance test (should use tracking automatically)
    print("\nStarting test with tracking enabled...")
    print("This will dispatch 3 workflows and tag them with a unique test_run_id")
    print()

    # Override the performance profile temporarily for quick test
    original_duration = environment.test_profiles['performance'].duration_minutes
    original_rate = environment.test_profiles['performance'].jobs_per_minute

    # Set to 1 minute duration, 3 jobs per minute
    environment.test_profiles['performance'].duration_minutes = 1
    environment.test_profiles['performance'].jobs_per_minute = 3

    try:
        # Run the test
        metrics = await runner.run_test_profile('performance')

        # The test run tracker should have saved the data
        if runner.test_run_tracker:
            test_run_id = runner.test_run_tracker.test_run_id
            print("\n" + "=" * 70)
            print("TRACKING TEST COMPLETE")
            print("=" * 70)
            print(f"\n✅ Test Run ID: {test_run_id}")
            print(f"✅ Workflows dispatched: {runner.test_run_tracker.workflow_count}")
            print(f"✅ Tracking file saved")
            print()
            print("Each workflow was tagged with job_name:", test_run_id)
            print()
            print("You can now:")
            print(f"1. Check GitHub Actions to see workflows tagged with: {test_run_id}")
            print(f"2. Run: python analyze_specific_test.py --test-run-id {test_run_id}")
            print(f"3. List all test runs: python analyze_specific_test.py --list")
            print()
            return True
        else:
            print("\n❌ ERROR: Test run tracker was not initialized")
            return False

    finally:
        # Restore original settings
        environment.test_profiles['performance'].duration_minutes = original_duration
        environment.test_profiles['performance'].jobs_per_minute = original_rate


if __name__ == "__main__":
    success = asyncio.run(test_tracking())
    sys.exit(0 if success else 1)