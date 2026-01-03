#!/usr/bin/env python3
"""
Capture Current GitHub Workflow Metrics
Captures the current state of running workflows and calculates metrics
"""

import os
import json
import requests
from datetime import datetime, timezone
from pathlib import Path
import time

def capture_current_metrics():
    """Capture metrics from currently running workflows"""

    # Configuration
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN not set")
        return

    owner = "devopulence"
    repo = "pythonProject"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    print("=" * 60)
    print("GitHub Workflow Metrics Capture")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Get all workflow runs
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    params = {"per_page": 30}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        return

    data = response.json()
    runs = data.get("workflow_runs", [])

    # Categorize runs
    queued_runs = []
    in_progress_runs = []
    completed_runs = []
    recent_runs = []  # Last 10 runs for analysis

    for run in runs:
        status = run["status"]
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))

        # Only consider runs from the last 2 hours
        time_since_created = (datetime.now(timezone.utc) - created).total_seconds()
        if time_since_created < 7200:  # 2 hours
            recent_runs.append(run)

            if status == "queued":
                queued_runs.append(run)
            elif status == "in_progress":
                in_progress_runs.append(run)
            elif status == "completed":
                completed_runs.append(run)

    # Calculate metrics
    metrics = {
        "capture_time": datetime.now(timezone.utc).isoformat(),
        "repository": f"{owner}/{repo}",
        "summary": {
            "total_recent_runs": len(recent_runs),
            "queued": len(queued_runs),
            "in_progress": len(in_progress_runs),
            "completed": len(completed_runs),
            "runner_utilization": min(len(in_progress_runs) / 4 * 100, 100)  # 4 runners
        },
        "runs": {
            "queued": [],
            "in_progress": [],
            "completed": []
        }
    }

    # Process queued runs
    print("\n📋 QUEUED WORKFLOWS:")
    print("-" * 40)
    if queued_runs:
        for run in queued_runs:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            queue_time = (datetime.now(timezone.utc) - created).total_seconds()

            run_data = {
                "id": run["id"],
                "name": run["name"],
                "workflow": run["path"],
                "created_at": run["created_at"],
                "queue_time_seconds": queue_time,
                "queue_time_minutes": round(queue_time / 60, 2)
            }
            metrics["runs"]["queued"].append(run_data)

            print(f"  • {run['name']}")
            print(f"    Queue Time: {run_data['queue_time_minutes']:.1f} minutes")
            print(f"    Created: {created.strftime('%H:%M:%S UTC')}")
    else:
        print("  None")

    # Process in-progress runs
    print("\n🏃 IN-PROGRESS WORKFLOWS:")
    print("-" * 40)
    if in_progress_runs:
        for run in in_progress_runs:
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            started = None
            if run.get("run_started_at"):
                started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                queue_time = (started - created).total_seconds()
                execution_time = (datetime.now(timezone.utc) - started).total_seconds()
            else:
                queue_time = 0
                execution_time = (datetime.now(timezone.utc) - created).total_seconds()

            # Get job details to find runner
            jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run['id']}/jobs"
            jobs_response = requests.get(jobs_url, headers=headers)
            runner_name = "unknown"
            if jobs_response.status_code == 200:
                jobs = jobs_response.json().get("jobs", [])
                for job in jobs:
                    if job.get("runner_name"):
                        runner_name = job["runner_name"]
                        break

            run_data = {
                "id": run["id"],
                "name": run["name"],
                "workflow": run["path"],
                "created_at": run["created_at"],
                "started_at": run.get("run_started_at"),
                "queue_time_seconds": queue_time,
                "queue_time_minutes": round(queue_time / 60, 2),
                "execution_time_seconds": execution_time,
                "execution_time_minutes": round(execution_time / 60, 2),
                "runner": runner_name
            }
            metrics["runs"]["in_progress"].append(run_data)

            print(f"  • {run['name']} (Runner: {runner_name})")
            print(f"    Queue Time: {run_data['queue_time_minutes']:.1f} min")
            print(f"    Running For: {run_data['execution_time_minutes']:.1f} min")
            print(f"    Started: {started.strftime('%H:%M:%S UTC') if started else 'N/A'}")
    else:
        print("  None")

    # Process completed runs
    print("\n✅ RECENTLY COMPLETED:")
    print("-" * 40)
    completed_in_last_hour = [r for r in completed_runs
                              if (datetime.now(timezone.utc) -
                                  datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00"))).total_seconds() < 3600]

    if completed_in_last_hour:
        for run in completed_in_last_hour[:5]:  # Show last 5
            created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))

            queue_time = 0
            execution_time = (updated - created).total_seconds()

            if run.get("run_started_at"):
                started = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                queue_time = (started - created).total_seconds()
                execution_time = (updated - started).total_seconds()

            run_data = {
                "id": run["id"],
                "name": run["name"],
                "workflow": run["path"],
                "conclusion": run["conclusion"],
                "created_at": run["created_at"],
                "completed_at": run["updated_at"],
                "queue_time_seconds": queue_time,
                "queue_time_minutes": round(queue_time / 60, 2),
                "execution_time_seconds": execution_time,
                "execution_time_minutes": round(execution_time / 60, 2),
                "total_time_minutes": round((updated - created).total_seconds() / 60, 2)
            }
            metrics["runs"]["completed"].append(run_data)

            print(f"  • {run['name']} - {run['conclusion'].upper()}")
            print(f"    Queue: {run_data['queue_time_minutes']:.1f} min | "
                  f"Execution: {run_data['execution_time_minutes']:.1f} min | "
                  f"Total: {run_data['total_time_minutes']:.1f} min")
    else:
        print("  None in the last hour")

    # Calculate aggregate metrics
    print("\n📊 METRICS SUMMARY:")
    print("-" * 40)

    # Queue time statistics
    all_queue_times = []
    for run in metrics["runs"]["completed"]:
        all_queue_times.append(run["queue_time_seconds"])
    for run in metrics["runs"]["in_progress"]:
        all_queue_times.append(run["queue_time_seconds"])

    if all_queue_times:
        avg_queue = sum(all_queue_times) / len(all_queue_times)
        max_queue = max(all_queue_times)
        min_queue = min(all_queue_times)

        metrics["summary"]["queue_metrics"] = {
            "avg_seconds": avg_queue,
            "avg_minutes": round(avg_queue / 60, 2),
            "max_seconds": max_queue,
            "max_minutes": round(max_queue / 60, 2),
            "min_seconds": min_queue,
            "min_minutes": round(min_queue / 60, 2)
        }

        print(f"Queue Times:")
        print(f"  Average: {metrics['summary']['queue_metrics']['avg_minutes']:.1f} minutes")
        print(f"  Max: {metrics['summary']['queue_metrics']['max_minutes']:.1f} minutes")
        print(f"  Min: {metrics['summary']['queue_metrics']['min_minutes']:.1f} minutes")

    # Execution time statistics
    all_execution_times = []
    for run in metrics["runs"]["completed"]:
        all_execution_times.append(run["execution_time_seconds"])

    if all_execution_times:
        avg_exec = sum(all_execution_times) / len(all_execution_times)
        max_exec = max(all_execution_times)
        min_exec = min(all_execution_times)

        metrics["summary"]["execution_metrics"] = {
            "avg_seconds": avg_exec,
            "avg_minutes": round(avg_exec / 60, 2),
            "max_seconds": max_exec,
            "max_minutes": round(max_exec / 60, 2),
            "min_seconds": min_exec,
            "min_minutes": round(min_exec / 60, 2)
        }

        print(f"\nExecution Times:")
        print(f"  Average: {metrics['summary']['execution_metrics']['avg_minutes']:.1f} minutes")
        print(f"  Max: {metrics['summary']['execution_metrics']['max_minutes']:.1f} minutes")
        print(f"  Min: {metrics['summary']['execution_metrics']['min_minutes']:.1f} minutes")

    print(f"\nRunner Utilization: {metrics['summary']['runner_utilization']:.1f}%")
    print(f"  ({len(in_progress_runs)} of 4 runners active)")

    # Save metrics
    output_dir = Path("test_results/captured_metrics")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"metrics_snapshot_{timestamp}.json"

    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print("\n💾 SAVED TO:")
    print(f"  {output_file}")

    # Also create a current.json that always has the latest
    current_file = output_dir / "current.json"
    with open(current_file, 'w') as f:
        json.dump(metrics, f, indent=2)

    print(f"  {current_file} (latest snapshot)")

    print("\n" + "=" * 60)
    print("Capture complete!")

    return metrics


if __name__ == "__main__":
    # Run continuous capture every 30 seconds if --watch flag is provided
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("Watching mode - capturing every 30 seconds (Ctrl+C to stop)")
        try:
            while True:
                os.system('clear')  # Clear screen
                capture_current_metrics()
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n\nStopped watching.")
    else:
        capture_current_metrics()
        print("\nTip: Run with --watch flag to continuously monitor:")
        print("  python capture_current_metrics.py --watch")