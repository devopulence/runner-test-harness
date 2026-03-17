"""
Demo Analysis Script - Quick insights from collected monitoring data.

Run from project root:
    python -m src.monitoring.demo_analysis
    python -m src.monitoring.demo_analysis --date 2026-03-17
"""

import argparse
import json
import logging
from collections import Counter
from datetime import datetime, date
from pathlib import Path

from .storage import DailyStatsStore


def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def percentile(sorted_list, pct):
    """Get percentile value from a sorted list."""
    if not sorted_list:
        return 0
    idx = int(len(sorted_list) * pct / 100)
    idx = min(idx, len(sorted_list) - 1)
    return sorted_list[idx]


def format_duration(seconds):
    """Format seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f} min"
    else:
        return f"{seconds/3600:.1f} hrs"


def run_analysis(store_dir="monitoring_data", collection_date=None):
    store = DailyStatsStore(store_dir)
    col_date = collection_date or date.today().strftime("%Y-%m-%d")

    # Check available dates
    available = store.list_dates()
    if not available:
        print("No data found in monitoring_data/. Run the collectors first.")
        return

    if col_date not in available:
        print(f"No data for {col_date}. Available dates: {', '.join(available)}")
        col_date = available[-1]
        print(f"Using most recent: {col_date}\n")

    runs = store.get_workflow_runs(collection_date=col_date)
    jobs = store.get_jobs(collection_date=col_date)

    run_data = [r.get("data", {}) for r in runs]
    job_data = [j.get("data", {}) for j in jobs]

    W = 60  # output width

    # =========================================================
    # HEADER
    # =========================================================
    print()
    print("=" * W)
    print("  GITHUB ACTIONS MONITORING - ORG ANALYSIS")
    print(f"  Collection Date: {col_date}")
    print(f"  Workflow Runs: {len(run_data)}  |  Jobs: {len(job_data)}")
    print("=" * W)

    # =========================================================
    # 1. REPOS
    # =========================================================
    repos = Counter(r.get("repository_full_name", "unknown") for r in run_data)
    print(f"\n{'─'*W}")
    print(f"  REPOSITORIES ({len(repos)} with workflow activity)")
    print(f"{'─'*W}")
    for repo, count in repos.most_common():
        bar = "█" * min(count // 5, 30)
        print(f"  {repo:<45} {count:>4} runs  {bar}")

    # =========================================================
    # 2. PIPELINE HEALTH
    # =========================================================
    conclusions = Counter(r.get("conclusion", "unknown") for r in run_data)
    total = len(run_data)
    success = conclusions.get("success", 0)
    failure = conclusions.get("failure", 0)
    cancelled = conclusions.get("cancelled", 0)
    success_rate = (success / total * 100) if total else 0

    print(f"\n{'─'*W}")
    print(f"  PIPELINE HEALTH")
    print(f"{'─'*W}")
    print(f"  Success Rate:  {success_rate:.1f}%  ({success}/{total})")
    print()
    for conc, count in conclusions.most_common():
        pct = count / total * 100 if total else 0
        bar = "█" * int(pct / 2)
        print(f"    {conc:<20} {count:>5}  ({pct:>5.1f}%)  {bar}")

    # Per-repo failure rates
    repo_failures = {}
    for r in run_data:
        repo = r.get("repository_full_name", "unknown")
        if repo not in repo_failures:
            repo_failures[repo] = {"total": 0, "failure": 0}
        repo_failures[repo]["total"] += 1
        if r.get("conclusion") == "failure":
            repo_failures[repo]["failure"] += 1

    failing_repos = {k: v for k, v in repo_failures.items() if v["failure"] > 0}
    if failing_repos:
        print(f"\n  Repos with failures:")
        for repo, counts in sorted(failing_repos.items(), key=lambda x: x[1]["failure"], reverse=True):
            rate = counts["failure"] / counts["total"] * 100
            print(f"    {repo:<45} {counts['failure']:>3}/{counts['total']:<3} ({rate:.0f}% failure)")

    # =========================================================
    # 3. TRIGGER EVENTS
    # =========================================================
    events = Counter(r.get("event", "unknown") for r in run_data)
    print(f"\n{'─'*W}")
    print(f"  TRIGGER EVENTS")
    print(f"{'─'*W}")
    for event, count in events.most_common():
        pct = count / total * 100 if total else 0
        print(f"    {event:<25} {count:>5}  ({pct:.1f}%)")

    # =========================================================
    # 4. QUEUE TIME (Developer Wait Time)
    # =========================================================
    queue_times = []
    exec_times = []
    total_times = []
    jobs_by_runner = Counter()
    for j in job_data:
        created = parse_ts(j.get("created_at"))
        started = parse_ts(j.get("started_at"))
        completed = parse_ts(j.get("completed_at"))

        runner = j.get("runner_name") or "unassigned"
        if runner:
            jobs_by_runner[runner] += 1

        if created and started and completed:
            qt = (started - created).total_seconds()
            et = (completed - started).total_seconds()
            tt = (completed - created).total_seconds()
            # Filter out unreasonable values (negative or > 24hrs)
            if 0 <= qt <= 86400 and 0 <= et <= 86400:
                queue_times.append(qt)
                exec_times.append(et)
                total_times.append(tt)

    if queue_times:
        queue_times.sort()
        exec_times.sort()
        total_times.sort()
        n = len(queue_times)

        print(f"\n{'─'*W}")
        print(f"  QUEUE TIME - Developer Wait ({n} jobs analyzed)")
        print(f"{'─'*W}")
        print(f"    Average:  {format_duration(sum(queue_times)/n)}")
        print(f"    P50:      {format_duration(percentile(queue_times, 50))}")
        print(f"    P95:      {format_duration(percentile(queue_times, 95))}")
        print(f"    P99:      {format_duration(percentile(queue_times, 99))}")
        print(f"    Max:      {format_duration(max(queue_times))}")

        # Queue time health assessment
        p95_qt = percentile(queue_times, 95)
        if p95_qt < 30:
            print(f"\n    Assessment: EXCELLENT - P95 under 30s")
        elif p95_qt < 120:
            print(f"\n    Assessment: GOOD - P95 under 2 min")
        elif p95_qt < 300:
            print(f"\n    Assessment: MODERATE - P95 under 5 min, consider adding runners")
        else:
            print(f"\n    Assessment: NEEDS ATTENTION - P95 is {format_duration(p95_qt)}, runners are saturated")

        print(f"\n{'─'*W}")
        print(f"  EXECUTION TIME - Build Duration ({n} jobs)")
        print(f"{'─'*W}")
        print(f"    Average:  {format_duration(sum(exec_times)/n)}")
        print(f"    P50:      {format_duration(percentile(exec_times, 50))}")
        print(f"    P95:      {format_duration(percentile(exec_times, 95))}")
        print(f"    Max:      {format_duration(max(exec_times))}")

        print(f"\n{'─'*W}")
        print(f"  TOTAL TIME - End to End ({n} jobs)")
        print(f"{'─'*W}")
        print(f"    Average:  {format_duration(sum(total_times)/n)}")
        print(f"    P50:      {format_duration(percentile(total_times, 50))}")
        print(f"    P95:      {format_duration(percentile(total_times, 95))}")
        print(f"    Max:      {format_duration(max(total_times))}")

    # =========================================================
    # 5. RUNNER ANALYSIS
    # =========================================================
    print(f"\n{'─'*W}")
    print(f"  RUNNER ANALYSIS ({len(jobs_by_runner)} unique runners)")
    print(f"{'─'*W}")

    # Runner labels
    label_counts = Counter()
    for j in job_data:
        for label in j.get("labels", []):
            label_counts[label] += 1

    if label_counts:
        print(f"\n  Runner Types (by label):")
        for label, count in label_counts.most_common():
            print(f"    {label:<25} {count:>4} jobs")

    # Top runners by workload
    real_runners = {k: v for k, v in jobs_by_runner.items()
                    if k and k != "unassigned" and k != "None"}
    if real_runners:
        print(f"\n  Top Runners by Workload:")
        for runner, count in Counter(real_runners).most_common(15):
            bar = "█" * min(count, 30)
            print(f"    {runner:<40} {count:>3} jobs  {bar}")

    # =========================================================
    # 6. JOB OUTCOMES
    # =========================================================
    job_conclusions = Counter(j.get("conclusion", "unknown") for j in job_data)
    job_total = len(job_data)
    job_success = job_conclusions.get("success", 0)
    job_success_rate = (job_success / job_total * 100) if job_total else 0

    print(f"\n{'─'*W}")
    print(f"  JOB OUTCOMES ({job_total} total)")
    print(f"{'─'*W}")
    print(f"  Job Success Rate: {job_success_rate:.1f}%")
    print()
    for conc, count in job_conclusions.most_common():
        pct = count / job_total * 100 if job_total else 0
        print(f"    {conc:<20} {count:>5}  ({pct:.1f}%)")

    # =========================================================
    # 7. ACTORS (who is triggering builds)
    # =========================================================
    actors = Counter(r.get("actor_login", "unknown") for r in run_data)
    print(f"\n{'─'*W}")
    print(f"  ACTIVE USERS ({len(actors)} unique)")
    print(f"{'─'*W}")
    for actor, count in actors.most_common(15):
        bar = "█" * min(count // 3, 30)
        print(f"    {actor:<30} {count:>5} runs  {bar}")

    # =========================================================
    # 8. WORKFLOW NAMES
    # =========================================================
    workflows = Counter(r.get("name", "unknown") for r in run_data)
    print(f"\n{'─'*W}")
    print(f"  WORKFLOWS ({len(workflows)} unique)")
    print(f"{'─'*W}")
    for wf, count in workflows.most_common(15):
        print(f"    {wf:<45} {count:>4} runs")
    if len(workflows) > 15:
        print(f"    ... and {len(workflows) - 15} more")

    # =========================================================
    # SUMMARY
    # =========================================================
    print(f"\n{'='*W}")
    print(f"  SUMMARY")
    print(f"{'='*W}")
    print(f"  Repos:           {len(repos)}")
    print(f"  Workflow Runs:    {len(run_data)}")
    print(f"  Jobs:            {len(job_data)}")
    print(f"  Success Rate:    {success_rate:.1f}% (runs) / {job_success_rate:.1f}% (jobs)")
    print(f"  Unique Runners:  {len(real_runners)}")
    print(f"  Active Users:    {len(actors)}")
    print(f"  Unique Workflows: {len(workflows)}")
    if queue_times:
        print(f"  Avg Queue Time:  {format_duration(sum(queue_times)/len(queue_times))}")
        print(f"  Avg Build Time:  {format_duration(sum(exec_times)/len(exec_times))}")
    print(f"{'='*W}\n")


def main():
    parser = argparse.ArgumentParser(description="Demo analysis of collected GitHub Actions data")
    parser.add_argument("--store-dir", default="monitoring_data", help="Path to monitoring data")
    parser.add_argument("--date", help="Collection date (default: today or most recent)")
    args = parser.parse_args()

    run_analysis(store_dir=args.store_dir, collection_date=args.date)


if __name__ == "__main__":
    main()
