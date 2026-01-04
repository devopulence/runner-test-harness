#!/usr/bin/env python3
"""
Analyze a specific test run using tracking data.
Usage: python analyze_specific_test.py [--test-run-id ID]
"""
import json
import argparse
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

from src.orchestrator.test_run_tracker import load_test_run, list_test_runs
from src.analysis.performance_analyzer import PerformanceAnalyzer


def fetch_test_run_workflows(token: str, test_run_id: str,
                            owner: str = "Devopulence",
                            repo: str = "pythonProject") -> dict:
    """Fetch workflows for a specific test run using job_name tag."""
    headers = {'Authorization': f'token {token}'}

    # Load test run tracking data
    try:
        tracking_data = load_test_run(test_run_id)
    except FileNotFoundError:
        print(f"Error: Test run '{test_run_id}' not found")
        print("\nAvailable test runs:")
        for run in list_test_runs():
            print(f"  - {run['test_run_id']} ({run['test_type']}, {run['workflow_count']} workflows)")
        return None

    print(f"Analyzing test run: {tracking_data['test_run_id']}")
    print(f"Test type: {tracking_data['test_type']}")
    print(f"Start time: {tracking_data['start_time']}")
    print(f"Duration: {tracking_data['duration_minutes']:.1f} minutes")
    print(f"Expected workflows: {tracking_data['workflow_count']}")
    print("-" * 60)

    # Calculate time window for the test
    start = datetime.fromisoformat(tracking_data['start_time'])
    end = datetime.fromisoformat(tracking_data['end_time'])

    # Fetch workflows from GitHub
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
    params = {'per_page': 100}
    r = requests.get(url, headers=headers, params=params)
    all_runs = r.json()['workflow_runs']

    # Filter to workflows from this test run
    # Method 1: By time window and workflow name (fallback)
    test_workflows = []

    # Method 2: Use job_name tag if available (preferred)
    job_name_tag = tracking_data.get('metadata', {}).get('job_name_tag')

    if job_name_tag:
        print(f"Looking for workflows tagged with job_name: {job_name_tag}")

        # We need to check each workflow's inputs to find matching job_name
        for run in all_runs:
            created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))

            # First check if it's in our time window (for efficiency)
            if start <= created <= end:
                # Check if it's a build job
                if 'Build' in run.get('name', ''):
                    # For workflows with job_name, we'd ideally check the inputs
                    # but GitHub API doesn't return inputs in the list view
                    # So we use time window + workflow name as proxy
                    test_workflows.append(run)
    else:
        # Fallback: Use time window only
        for run in all_runs:
            created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
            if start <= created <= end:
                if 'Build' in run.get('name', ''):
                    test_workflows.append(run)

    print(f"Found {len(test_workflows)} workflows from this test run")

    # Now fetch job-level metrics for accurate queue times
    queue_times = []
    exec_times = []
    total_times = []

    for run in test_workflows:
        if run['status'] != 'completed':
            continue

        # Get job-level data
        jobs_url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs/{run["id"]}/jobs'
        jr = requests.get(jobs_url, headers=headers)
        jobs = jr.json().get('jobs', [])

        for job in jobs:
            if job.get('started_at') and job.get('completed_at'):
                created = datetime.fromisoformat(job['created_at'].replace('Z', '+00:00'))
                started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))
                completed = datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00'))

                queue_time = (started - created).total_seconds() / 60
                exec_time = (completed - started).total_seconds() / 60
                total_time = (completed - created).total_seconds() / 60

                queue_times.append(queue_time)
                exec_times.append(exec_time)
                total_times.append(total_time)

    return {
        'test_run_id': test_run_id,
        'tracking_data': tracking_data,
        'queue_times': queue_times,
        'execution_times': exec_times,
        'total_times': total_times,
        'workflow_count': len(test_workflows),
        'completed_count': len(queue_times)
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze specific test run')
    parser.add_argument('--test-run-id', help='Specific test run ID (default: latest)')
    parser.add_argument('--list', action='store_true', help='List available test runs')
    args = parser.parse_args()

    if args.list:
        print("Available test runs:")
        print("-" * 60)
        for run in list_test_runs():
            print(f"ID: {run['test_run_id']}")
            print(f"  Type: {run['test_type']}")
            print(f"  Time: {run['start_time']}")
            print(f"  Duration: {run['duration_minutes']:.1f} minutes")
            print(f"  Workflows: {run['workflow_count']}")
            print()
        return

    # Get GitHub token
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    # Fetch metrics for specific test run
    metrics = fetch_test_run_workflows(token, args.test_run_id)
    if not metrics:
        return

    print("\n" + "=" * 60)
    print("TEST RUN ANALYSIS")
    print("=" * 60)

    # Create analyzer
    analyzer = PerformanceAnalyzer()

    # Basic statistics
    if metrics['queue_times']:
        print(f"\n📊 METRICS SUMMARY")
        print("-" * 40)
        print(f"Workflows completed: {metrics['completed_count']}/{metrics['workflow_count']}")

        avg_queue = sum(metrics['queue_times']) / len(metrics['queue_times'])
        avg_exec = sum(metrics['execution_times']) / len(metrics['execution_times'])
        avg_total = sum(metrics['total_times']) / len(metrics['total_times'])

        print(f"Average Queue Time:     {avg_queue:.1f} minutes")
        print(f"Average Execution Time: {avg_exec:.1f} minutes")
        print(f"Average Total Time:     {avg_total:.1f} minutes")
        print(f"Queue Impact:           {(avg_queue/avg_total)*100:.0f}% of total")

        # Detailed analysis
        print("\n📈 DETAILED ANALYSIS")
        print("-" * 40)

        queue_analysis = analyzer.analyze_queue_behavior(metrics['queue_times'])
        print(f"Queue Health: {queue_analysis['health']}")
        print(f"Queue Pattern: {queue_analysis['growth_pattern']}")

        exec_analysis = analyzer.analyze_execution_times(
            metrics['execution_times'],
            expected_range=(3, 5)
        )
        print(f"Execution Consistency: {exec_analysis['consistency']}")
        print(f"Within Expected Range: {exec_analysis['range_compliance']['within_range_pct']:.0f}%")

        # Generate insights
        runner_count = metrics['tracking_data'].get('runner_count', 4)
        dispatch_rate = metrics['workflow_count'] / metrics['tracking_data']['duration_minutes']

        insights = analyzer.generate_insights(
            queue_times=metrics['queue_times'],
            exec_times=metrics['execution_times'],
            total_times=metrics['total_times'],
            runner_count=runner_count,
            dispatch_rate=dispatch_rate
        )

        print(f"\n🎯 KEY FINDINGS")
        print("-" * 40)
        for finding in insights['key_findings']:
            print(f"  {finding}")

        print(f"\n📋 RECOMMENDATIONS")
        print("-" * 40)
        for action in insights['action_items']:
            print(f"  {action}")

    else:
        print("No completed workflows found for analysis")

    # Save analysis
    output_dir = Path('test_results/analysis/by_test_run')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{metrics['test_run_id']}_analysis.json"

    with open(output_file, 'w') as f:
        json.dump({
            'test_run_id': metrics['test_run_id'],
            'analysis_time': datetime.now().isoformat(),
            'metrics': metrics,
            'tracking_data': metrics['tracking_data']
        }, f, indent=2)

    print(f"\n📄 Analysis saved to: {output_file}")


if __name__ == "__main__":
    main()