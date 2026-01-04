#!/usr/bin/env python3
"""
Debug script to isolate the workflow tracking issue.
Uses the last test run to verify what's happening.
"""

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import aiohttp

# Configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = "devopulence"
REPO = "pythonProject"
BASE_URL = f"https://api.github.com/repos/{OWNER}/{REPO}"

async def main():
    # Load last test run tracking data
    tracking_file = Path("test_results/aws-ecs/tracking/latest.json")
    if not tracking_file.exists():
        print("❌ No tracking data found. Run a test first.")
        return

    with open(tracking_file) as f:
        tracking = json.load(f)

    test_run_id = tracking["test_run_id"]
    start_time = datetime.fromisoformat(tracking["start_time"])
    workflow_count = tracking["workflow_count"]

    print("=" * 60)
    print("DEBUG: Workflow Tracking Issue")
    print("=" * 60)
    print(f"\nTest Run ID: {test_run_id}")
    print(f"Start Time: {start_time}")
    print(f"Workflows Dispatched: {workflow_count}")
    print(f"Workflow Names: {tracking['workflow_names'][:5]}...")  # First 5

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Get recent runs from GitHub
        print("\n" + "-" * 60)
        print("STEP 1: Checking GitHub API for recent runs")
        print("-" * 60)

        url = f"{BASE_URL}/actions/runs"
        params = {"per_page": 50}

        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                print(f"❌ API Error: {resp.status}")
                print(await resp.text())
                return

            data = await resp.json()
            all_runs = data.get("workflow_runs", [])
            print(f"✓ Got {len(all_runs)} runs from API (total: {data.get('total_count')})")

        # Convert start_time to UTC for comparison
        if start_time.tzinfo is None:
            # Assume local time, convert to UTC (EST = UTC-5)
            start_time_utc = start_time.replace(tzinfo=timezone.utc)
            # Actually we need to ADD 5 hours if we're in EST
            # Let's just use a wide window

        print(f"\nTest start time (local): {tracking['start_time']}")

        # Find runs that could be from our test
        # Use created_at timestamp comparison
        test_start_str = tracking['start_time']

        # Find runs created around our test time
        print("\n" + "-" * 60)
        print("STEP 2: Finding runs created during test window")
        print("-" * 60)

        # The test ran for ~10 minutes, so look for runs in that window
        # Runs are in UTC, our tracking is in local time
        # Let's just look at the most recent runs and count build_job.yml ones

        build_job_runs = [r for r in all_runs if "build_job" in r.get("path", "")]
        print(f"\nFound {len(build_job_runs)} build_job.yml runs in last 50")

        # Show the runs
        print("\nRecent build_job runs:")
        for run in build_job_runs[:15]:
            print(f"  {run['id']}: {run['status']:12} {run['created_at']} {run.get('conclusion', 'N/A')}")

        # Check timing
        print("\n" + "-" * 60)
        print("STEP 3: Checking run inputs (the suspected issue)")
        print("-" * 60)

        # Get details of first few runs to check inputs
        for run in build_job_runs[:3]:
            run_id = run['id']
            url = f"{BASE_URL}/actions/runs/{run_id}"

            async with session.get(url) as resp:
                if resp.status == 200:
                    run_detail = await resp.json()
                    print(f"\nRun {run_id}:")
                    print(f"  inputs field: {run_detail.get('inputs')}")
                    print(f"  event: {run_detail.get('event')}")

        # The real issue: let's check if baseline tracking would work
        print("\n" + "-" * 60)
        print("STEP 4: Testing baseline run_id approach")
        print("-" * 60)

        # If we started with baseline_run_id = X, any run with id > X is "new"
        # Let's simulate what should have happened

        # Get the oldest run in our window (this would be baseline)
        if len(build_job_runs) >= workflow_count:
            # The runs are sorted newest first
            # So if we dispatched 12 workflows, runs [0:12] should be ours
            our_runs = build_job_runs[:workflow_count]
            baseline_would_be = build_job_runs[workflow_count]["id"] if len(build_job_runs) > workflow_count else 0

            print(f"\nIf baseline was: {baseline_would_be}")
            print(f"Our {workflow_count} runs would be IDs: {[r['id'] for r in our_runs]}")
            print(f"\nThese runs all completed: {all(r['status'] == 'completed' for r in our_runs)}")
            print(f"All succeeded: {all(r.get('conclusion') == 'success' for r in our_runs)}")

            # Calculate times
            print("\n" + "-" * 60)
            print("STEP 5: What the metrics SHOULD show")
            print("-" * 60)

            for i, run in enumerate(reversed(our_runs)):  # oldest first
                created = run['created_at']
                started = run.get('run_started_at', 'N/A')

                if run.get('run_started_at'):
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    started_dt = datetime.fromisoformat(run['run_started_at'].replace('Z', '+00:00'))
                    queue_time = (started_dt - created_dt).total_seconds()
                else:
                    queue_time = 'N/A'

                print(f"  Run {i+1}: queue_time={queue_time}s, status={run['status']}, conclusion={run.get('conclusion')}")

        # THE FIX
        print("\n" + "=" * 60)
        print("DIAGNOSIS")
        print("=" * 60)
        print("""
The baseline run_id approach SHOULD work. The runs exist and completed.

Possible issues:
1. Baseline not being set correctly before dispatch
2. Matching logic filtering out valid runs
3. Timezone comparison issues
4. API session issues

Let me check what the tracker baseline was set to...
""")

        # Check if there's any debug output we can find
        print("\nChecking test report for clues...")
        report_dir = Path("test_results/aws-ecs")
        reports = sorted(report_dir.glob("test_report_*.json"), reverse=True)
        if reports:
            with open(reports[0]) as f:
                report = json.load(f)
            print(f"\nLatest report: {reports[0].name}")
            print(f"  total_workflows: {report['metrics']['total_workflows']}")
            print(f"  successful_workflows: {report['metrics']['successful_workflows']}")
            print(f"  queue_times collected: {len(report['raw_data']['queue_times'])}")
            print(f"  execution_times collected: {len(report['raw_data']['execution_times'])}")

if __name__ == "__main__":
    asyncio.run(main())
