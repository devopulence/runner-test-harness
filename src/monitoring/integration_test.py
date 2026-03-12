"""
Integration Test for Stories 1 & 2
Tests GitHubClient (real API) + DailyStatsStore (real disk) together.
Collects workflow runs across ALL repos in an org.

Usage:
    python integration_test.py
    python integration_test.py --org Devopulence
    python integration_test.py --org Devopulence --created ">=2026-03-01"
"""

import argparse
import sys
import tempfile
from pathlib import Path

# Ensure project root is on path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_client import GitHubClient, GitHubAPIError
from storage import DailyStatsStore


def run_integration_test(org: str, created: str = None):
    print(f"\n{'='*60}")
    print(f"Integration Test: Stories 1 & 2")
    print(f"Organization: {org}")
    if created:
        print(f"Date filter: {created}")
    print(f"{'='*60}\n")

    # --- Step 1: Connect to GitHub API ---
    print("[1/7] Connecting to GitHub API...")
    try:
        client = GitHubClient(owner=org, repo="")
    except ValueError as e:
        print(f"FAIL: {e}")
        print("Set GITHUB_TOKEN in .env or environment")
        return False
    print(f"  OK - Token loaded, base_url={client.base_url}")

    # --- Step 2: List all org repos ---
    print(f"\n[2/7] Listing repos in '{org}'...")
    try:
        repos = client.list_org_repos(org)
    except GitHubAPIError as e:
        print(f"FAIL: {e}")
        return False

    print(f"  OK - Found {len(repos)} repositories:")
    for r in repos:
        print(f"    - {r['full_name']} ({'private' if r.get('private') else 'public'})")

    # --- Step 3: Fetch workflow runs across all repos ---
    filters = {}
    if created:
        filters["created"] = created

    print(f"\n[3/7] Fetching workflow runs across all repos...")
    try:
        all_runs = client.list_org_workflow_runs(org, max_pages_per_repo=2, **filters)
    except GitHubAPIError as e:
        print(f"FAIL: {e}")
        return False

    print(f"  OK - Got {len(all_runs)} total workflow runs")

    # Group by repo for summary
    runs_by_repo = {}
    for run in all_runs:
        repo_name = run.get("repository", {}).get("full_name", "unknown")
        runs_by_repo.setdefault(repo_name, []).append(run)

    print(f"\n  Runs per repo:")
    for repo_name, repo_runs in sorted(runs_by_repo.items()):
        success = sum(1 for r in repo_runs if r.get("conclusion") == "success")
        failed = sum(1 for r in repo_runs if r.get("conclusion") == "failure")
        other = len(repo_runs) - success - failed
        print(f"    {repo_name}: {len(repo_runs)} runs "
              f"(success={success}, failed={failed}, other={other})")

    # --- Step 4: Fetch jobs for first run ---
    jobs = []
    if all_runs:
        run = all_runs[0]
        run_id = run["id"]
        run_repo = run.get("repository", {}).get("name", "")
        print(f"\n[4/7] Fetching jobs for latest run #{run_id} ({run.get('repository', {}).get('full_name', '')})...")

        # Point client at the right repo for this call
        client.owner = org
        client.repo = run_repo
        try:
            jobs = client.list_jobs_for_run(run_id)
        except GitHubAPIError as e:
            print(f"  WARN: {e}")

        print(f"  OK - Got {len(jobs)} jobs")
        for job in jobs[:5]:
            print(f"    Job: '{job.get('name')}' runner={job.get('runner_name', 'N/A')} "
                  f"status={job.get('status')} conclusion={job.get('conclusion')}")
    else:
        print(f"\n[4/7] Skipping job fetch (no runs found)")

    # --- Step 5: Check rate limit ---
    print(f"\n[5/7] Rate limit status...")
    rl = client.get_rate_limit_status()
    print(f"  Remaining: {rl['remaining']}/{rl['limit']} "
          f"(used {rl['used']}, resets in {rl['reset_in_seconds']}s)")
    print(f"  API requests made: {client.request_count}")

    # --- Step 6: Store in DailyStatsStore ---
    print(f"\n[6/7] Storing data in DailyStatsStore...")
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)

        if all_runs:
            count = store.append_workflow_runs(all_runs)
            print(f"  Stored {count} workflow runs")

        if jobs:
            count = store.append_jobs(jobs)
            print(f"  Stored {count} jobs")

        store.log_collection({
            "event": "integration_test",
            "org": org,
            "repos_found": len(repos),
            "runs_collected": len(all_runs),
            "jobs_collected": len(jobs),
        })

        # --- Step 7: Read back and verify ---
        print(f"\n[7/7] Reading back from storage and verifying...")
        stored_runs = store.get_workflow_runs()
        stored_jobs = store.get_jobs()
        log = store.get_collection_log()
        summary = store.get_date_summary()

        print(f"  Workflow runs: {len(stored_runs)} records")
        print(f"  Jobs: {len(stored_jobs)} records")
        print(f"  Collection log: {len(log)} entries")

        # Verify round-trip
        assert len(stored_runs) == len(all_runs), \
            f"Run count mismatch: {len(stored_runs)} != {len(all_runs)}"
        assert len(stored_jobs) == len(jobs), \
            f"Job count mismatch: {len(stored_jobs)} != {len(jobs)}"
        assert len(log) == 1

        if all_runs:
            assert stored_runs[0]["data"]["id"] == all_runs[0]["id"], "First run ID mismatch"

        # Show file sizes
        for filename, info in summary.get("files", {}).items():
            print(f"  {filename}: {info['record_count']} records, "
                  f"{info['size_bytes'] / 1024:.1f} KB")

    client.close()

    print(f"\n{'='*60}")
    print(f"ALL INTEGRATION TESTS PASSED")
    print(f"  Repos: {len(repos)}")
    print(f"  Workflow runs: {len(all_runs)}")
    print(f"  Jobs sampled: {len(jobs)}")
    print(f"  API calls: {client.request_count}")
    print(f"{'='*60}\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Integration test for Stories 1 & 2")
    parser.add_argument("--org", default="Devopulence", help="GitHub organization name")
    parser.add_argument("--created", default=None,
                        help="Filter runs by date (e.g. '>=2026-03-01')")
    args = parser.parse_args()

    success = run_integration_test(args.org, args.created)
    sys.exit(0 if success else 1)