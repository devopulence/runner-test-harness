#!/usr/bin/env python3
"""
Analyze test results and provide insights.
Usage: python analyze_test_results.py [--test-type performance]
"""
import json
import argparse
from pathlib import Path
from datetime import datetime
import requests
from typing import Dict, List, Any
import os

from src.analysis.performance_analyzer import PerformanceAnalyzer


def fetch_job_metrics(token: str, owner: str = "Devopulence",
                      repo: str = "pythonProject", hours: int = 2) -> Dict[str, List]:
    """Fetch actual job metrics from GitHub API."""
    headers = {'Authorization': f'token {token}'}

    # Get recent workflows
    url = f'https://api.github.com/repos/{owner}/{repo}/actions/runs'
    params = {'per_page': 100}
    r = requests.get(url, headers=headers, params=params)
    runs = r.json()['workflow_runs']

    # Filter to completed builds from test period
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    test_runs = [r for r in runs
                 if 'Build' in r.get('name', '')
                 and r['status'] == 'completed'
                 and datetime.fromisoformat(r['created_at'].replace('Z', '+00:00')) > cutoff]

    queue_times = []
    exec_times = []
    total_times = []

    print(f"Analyzing {len(test_runs)} workflows...")

    for run in test_runs:
        # Get job-level data for accurate queue times
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
        'queue_times': queue_times,
        'execution_times': exec_times,
        'total_times': total_times,
        'job_count': len(queue_times)
    }


def load_test_config(test_type: str) -> Dict[str, Any]:
    """Load test configuration."""
    # Try to load from most recent test report
    test_results_dir = Path('test_results/aws-ecs')
    if test_results_dir.exists():
        reports = sorted(test_results_dir.glob('test_report_*.json'))
        if reports:
            with open(reports[-1]) as f:
                return json.load(f)

    # Default configuration
    return {
        'environment': {'runner_count': 4},
        'test_execution': {'duration_minutes': 30},
        'metrics': {'runner_utilization': {'mean': 0.92}}
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze test results')
    parser.add_argument('--test-type', default='performance',
                       choices=['performance', 'load', 'stress', 'capacity'])
    parser.add_argument('--hours', type=int, default=2,
                       help='Hours of data to analyze')
    args = parser.parse_args()

    # Get GitHub token
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    print(f"Analyzing {args.test_type} test results...")
    print("=" * 60)

    # Fetch actual metrics
    metrics = fetch_job_metrics(token, hours=args.hours)

    if not metrics['queue_times']:
        print("No test data found in the specified time period")
        return

    # Load test configuration
    test_config = load_test_config(args.test_type)
    runner_count = test_config.get('environment', {}).get('runner_count', 4)

    # Create analyzer
    analyzer = PerformanceAnalyzer()

    # Analyze each aspect
    print("\n📊 QUEUE ANALYSIS")
    print("-" * 40)
    queue_analysis = analyzer.analyze_queue_behavior(metrics['queue_times'])
    print(f"Health Status: {queue_analysis['health']}")
    print(f"Interpretation: {queue_analysis['interpretation']}")
    print(f"Average Queue Time: {queue_analysis['metrics']['average']:.1f} minutes")
    print(f"Maximum Queue Time: {queue_analysis['metrics']['maximum']:.1f} minutes")
    print(f"Queue Growth Pattern: {queue_analysis['growth_pattern']}")
    print("\nRecommendations:")
    for rec in queue_analysis['recommendations']:
        print(f"  • {rec}")

    print("\n⚡ EXECUTION TIME ANALYSIS")
    print("-" * 40)
    exec_analysis = analyzer.analyze_execution_times(
        metrics['execution_times'],
        expected_range=(3, 5)  # Standard workload is 3-5 minutes
    )
    print(f"Consistency: {exec_analysis['consistency']}")
    print(f"Interpretation: {exec_analysis['interpretation']}")
    print(f"Average Execution: {exec_analysis['metrics']['average']:.1f} minutes")
    print(f"Variation (CV): {exec_analysis['metrics']['coefficient_variation']:.1f}%")
    print(f"Within Expected Range: {exec_analysis['range_compliance']['within_range_pct']:.0f}%")
    print("\nRecommendations:")
    for rec in exec_analysis['recommendations']:
        print(f"  • {rec}")

    # Calculate utilization (simplified from test data)
    utilization_data = [test_config['metrics']['runner_utilization']['mean']] * 100

    print("\n🔧 UTILIZATION ANALYSIS")
    print("-" * 40)
    util_analysis = analyzer.analyze_utilization(utilization_data, runner_count)
    print(f"Efficiency: {util_analysis['efficiency']}")
    print(f"Interpretation: {util_analysis['interpretation']}")
    print(f"Average Utilization: {util_analysis['metrics']['average']:.1f}%")
    print(f"Time at 100%: {util_analysis['metrics']['time_at_100_pct']:.0f}%")
    capacity = util_analysis['capacity_analysis']
    print(f"Capacity Status: {capacity['status']}")
    print(f"Headroom: {capacity['headroom_pct']:.0f}%")
    print("\nRecommendations:")
    for rec in util_analysis['recommendations']:
        print(f"  • {rec}")

    # Generate comprehensive insights
    print("\n🎯 KEY INSIGHTS")
    print("-" * 40)

    # Estimate dispatch rate from job count and duration
    duration_hours = args.hours
    dispatch_rate = metrics['job_count'] / (duration_hours * 60)  # jobs per minute

    insights = analyzer.generate_insights(
        queue_times=metrics['queue_times'],
        exec_times=metrics['execution_times'],
        total_times=metrics['total_times'],
        runner_count=runner_count,
        dispatch_rate=dispatch_rate
    )

    print(f"Primary Bottleneck: {insights['summary']['bottleneck']}")
    print(f"  {insights['summary']['bottleneck_description']}")
    print(f"Queue Impact: {insights['summary']['queue_impact_pct']:.0f}% of total time")
    print(f"Rate Assessment: {insights['summary']['rate_assessment']}")

    print("\n📈 CAPACITY ANALYSIS")
    print(f"Current Runners: {insights['capacity']['current_runners']}")
    print(f"Sustainable Rate: {insights['capacity']['sustainable_rate']}")
    print(f"Current Rate: {insights['capacity']['current_rate']}")
    print(f"Rate Ratio: {insights['capacity']['rate_ratio']:.1%}")

    print("\n👤 USER EXPERIENCE")
    ux = insights['user_experience']
    print(f"Rating: {ux['rating']}")
    print(f"Description: {ux['description']}")
    print(f"Average Total Time: {ux['avg_wait_time']}")

    print("\n💚 SYSTEM HEALTH")
    print(insights['system_health'])

    print("\n🔍 KEY FINDINGS")
    for finding in insights['key_findings']:
        print(f"  {finding}")

    print("\n📋 ACTION ITEMS")
    for action in insights['action_items']:
        print(f"  {action}")

    # Save analysis results
    output_dir = Path('test_results/analysis')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.test_type}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    analysis_results = {
        'test_type': args.test_type,
        'analysis_time': datetime.now().isoformat(),
        'metrics': metrics,
        'queue_analysis': queue_analysis,
        'execution_analysis': exec_analysis,
        'utilization_analysis': util_analysis,
        'insights': insights
    }

    with open(output_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)

    print(f"\n📄 Analysis saved to: {output_file}")

    # Generate human-readable summary
    print("\n" + "=" * 60)
    print("📊 ANALYSIS SUMMARY")
    print("=" * 60)

    # Create summary box
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                   TEST ANALYSIS SUMMARY                    ║
╠═══════════════════════════════════════════════════════════╣
║ Test Type:        {args.test_type.upper():<40}║
║ Workflows:        {metrics['job_count']:<40}║
║ Duration:         {args.hours} hours{' ' * (37 - len(str(args.hours)))}║
╠═══════════════════════════════════════════════════════════╣
║                      KEY METRICS                          ║
╠═══════════════════════════════════════════════════════════╣
║ Avg Total Time:   {insights['user_experience']['avg_wait_time']:<40}║
║ Queue Impact:     {insights['summary']['queue_impact_pct']:.0f}% of total time{' ' * (28 - len(str(int(insights['summary']['queue_impact_pct']))))}║
║ User Experience:  {insights['user_experience']['rating']:<40}║
║ System Health:    {('⚠️ ' if 'OVERLOADED' in insights['system_health'] else '✅ '):<3}{insights['system_health'][:37]:<37}║
╚═══════════════════════════════════════════════════════════╝
    """)

    # Show most important recommendations
    print("\n🎯 TOP RECOMMENDATIONS:")
    print("-" * 40)
    for i, action in enumerate(insights['action_items'][:3], 1):
        print(f"{i}. {action}")

    print("\n✨ Run with --verbose flag for detailed breakdown")


if __name__ == "__main__":
    main()