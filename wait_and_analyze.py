#!/usr/bin/env python3
"""
Wait for workflows to complete and then run analysis.
This is useful when the test ends before all workflows finish.
"""
import os
import sys
import time
import json
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path

from src.orchestrator.test_run_tracker import load_test_run, list_test_runs
from src.analysis.test_specific_analyzer import TestAnalyzerFactory


def check_workflows_status(token: str, test_run_id: str = None,
                          owner: str = "Devopulence",
                          repo: str = "pythonProject"):
    """Check if workflows from a test run are complete."""
    headers = {'Authorization': f'token {token}'}

    # Load test run tracking data
    try:
        tracking_data = load_test_run(test_run_id, "aws-ecs")
    except FileNotFoundError:
        print(f"Error: Test run '{test_run_id}' not found")
        return None

    print(f"Checking test run: {tracking_data['test_run_id']}")
    print(f"Expected workflows: {tracking_data['workflow_count']}")

    # Calculate time window for the test
    start = datetime.fromisoformat(tracking_data['start_time'])
    end = datetime.fromisoformat(tracking_data['end_time'])

    # Add buffer time for workflows still running
    end_buffer = end + timedelta(minutes=30)

    # Fetch workflows from GitHub
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
    params = {'per_page': 100}
    r = requests.get(url, headers=headers, params=params)
    all_runs = r.json()['workflow_runs']

    # Filter to workflows from this test run
    test_workflows = []
    for run in all_runs:
        created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        if start <= created <= end_buffer:
            if 'Build' in run.get('name', ''):
                test_workflows.append(run)

    # Count statuses
    completed = sum(1 for w in test_workflows if w['status'] == 'completed')
    in_progress = sum(1 for w in test_workflows if w['status'] in ['in_progress', 'queued'])

    return {
        'total': len(test_workflows),
        'completed': completed,
        'in_progress': in_progress,
        'all_done': in_progress == 0 and completed > 0,
        'workflows': test_workflows,
        'tracking_data': tracking_data
    }


def analyze_completed_workflows(status_data: dict, token: str,
                               owner: str = "Devopulence",
                               repo: str = "pythonProject"):
    """Analyze completed workflows."""
    headers = {'Authorization': f'token {token}'}

    # Collect metrics from completed workflows
    queue_times = []
    exec_times = []
    total_times = []
    failed = 0

    print("\nCollecting metrics from completed workflows...")

    for run in status_data['workflows']:
        if run['status'] != 'completed':
            continue

        # Get job-level data for accurate metrics
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

            if job.get('conclusion') == 'failure':
                failed += 1

    if not queue_times:
        print("No completed workflows with metrics found")
        return None

    # Get test type from tracking data
    test_type = status_data['tracking_data'].get('test_type', 'performance')

    # Run test-specific analysis
    print(f"\n🔬 Running {test_type} test analysis...")
    print("=" * 60)

    analyzer = TestAnalyzerFactory.get_analyzer(test_type)

    # Prepare metrics
    metrics = {
        'queue_times': queue_times,
        'execution_times': exec_times,
        'total_times': total_times,
        'job_count': len(queue_times),
        'total_workflows': status_data['total'],
        'failed_workflows': failed,
        'duration_minutes': status_data['tracking_data']['duration_minutes'],
        'runner_count': 4,  # From environment
        'runner_utilization': []  # Not available in post-analysis
    }

    # Run analysis
    analysis = analyzer.analyze(metrics)

    # Display results
    display_analysis(test_type, analysis)

    # Generate recommendations
    recommendations = analyzer.generate_recommendations(analysis)
    if recommendations:
        print("\n📋 Recommendations:")
        print("-" * 40)
        for rec in recommendations:
            print(f"  {rec}")

    return analysis


def display_analysis(test_type: str, analysis: dict):
    """Display test analysis results."""
    if test_type == "performance":
        print("\n🎯 Performance Analysis:")
        print("-" * 40)
        if "overall_rating" in analysis:
            print(f"Overall Rating: {analysis['overall_rating']}")
        if "queue_analysis" in analysis:
            print(f"Queue Health: {analysis['queue_analysis']['health']}")
        if "execution_analysis" in analysis:
            print(f"Execution Consistency: {analysis['execution_analysis']['consistency']}")
        if "predictability" in analysis:
            print(f"Predictability: {analysis['predictability']['score']}")
            print(f"  {analysis['predictability']['interpretation']}")
        if "baseline_metrics" in analysis:
            sla = analysis['baseline_metrics']['recommended_sla']
            print(f"\nRecommended SLAs:")
            print(f"  P50: {sla['p50']:.1f} minutes")
            print(f"  P95: {sla['p95']:.1f} minutes")
            print(f"  P99: {sla['p99']:.1f} minutes")


def main():
    parser = argparse.ArgumentParser(description='Wait for workflows and analyze')
    parser.add_argument('--test-run-id', help='Test run ID (default: latest)')
    parser.add_argument('--wait', action='store_true',
                       help='Wait for workflows to complete')
    parser.add_argument('--max-wait', type=int, default=30,
                       help='Maximum minutes to wait (default: 30)')
    args = parser.parse_args()

    # Get GitHub token
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    # Use latest test run if not specified
    test_run_id = args.test_run_id
    if not test_run_id:
        runs = list_test_runs("aws-ecs")
        if runs:
            test_run_id = runs[-1]['test_run_id']
            print(f"Using latest test run: {test_run_id}")
        else:
            print("No test runs found")
            return

    # Check workflow status
    status = check_workflows_status(token, test_run_id)
    if not status:
        return

    print(f"\nWorkflow Status:")
    print(f"  Total: {status['total']}")
    print(f"  Completed: {status['completed']}")
    print(f"  In Progress: {status['in_progress']}")

    # Wait for completion if requested
    if args.wait and not status['all_done']:
        print(f"\n⏳ Waiting for workflows to complete (max {args.max_wait} minutes)...")
        start_wait = time.time()
        max_wait_seconds = args.max_wait * 60

        while time.time() - start_wait < max_wait_seconds:
            time.sleep(30)  # Check every 30 seconds

            status = check_workflows_status(token, test_run_id)
            print(f"  Status: {status['completed']} completed, {status['in_progress']} in progress")

            if status['all_done']:
                print("\n✅ All workflows completed!")
                break
        else:
            print(f"\n⚠️ Timeout: Still {status['in_progress']} workflows in progress after {args.max_wait} minutes")

    # Analyze if we have completed workflows
    if status['completed'] > 0:
        analyze_completed_workflows(status, token)
    else:
        print("\nNo completed workflows to analyze yet")


if __name__ == "__main__":
    main()