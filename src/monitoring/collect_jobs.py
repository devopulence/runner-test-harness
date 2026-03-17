"""
Job-Level Data Collector (Task 4)

Collects job-level data from GitHub API for workflow runs already stored
by the workflow run collector (Task 3). Captures timestamps, runner
assignment, step-level details, and conclusions.

Supports single-repo and org-wide collection by reading stored workflow
runs and fetching jobs for each run.

Usage:
    # Collect jobs for today's stored runs
    python -m src.monitoring.collect_jobs --owner devopulence --repo pythonProject

    # Collect jobs org-wide (reads all stored runs, fetches jobs per repo)
    python -m src.monitoring.collect_jobs --org devopulence

    # Collect jobs for a specific date's runs
    python -m src.monitoring.collect_jobs --org devopulence --date 2026-03-16
"""

import argparse
import logging
import os
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

from .github_client import GitHubClient, GitHubAPIError
from .storage import DailyStatsStore

logger = logging.getLogger(__name__)

# Fields we extract from each job
JOB_FIELDS = [
    "id",
    "run_id",
    "workflow_name",
    "name",
    "status",
    "conclusion",
    "created_at",
    "started_at",
    "completed_at",
    "head_branch",
    "head_sha",
    "run_attempt",
    "html_url",
    "labels",
    "runner_id",
    "runner_name",
    "runner_group_id",
    "runner_group_name",
    "steps",
]


def extract_job_data(job: dict) -> dict:
    """Extract key fields from a raw GitHub job response."""
    extracted = {}
    for field in JOB_FIELDS:
        value = job.get(field)
        if field == "steps" and isinstance(value, list):
            # Keep steps but strip to essential fields only
            extracted["steps"] = [
                {
                    "name": s.get("name"),
                    "number": s.get("number"),
                    "status": s.get("status"),
                    "conclusion": s.get("conclusion"),
                    "started_at": s.get("started_at"),
                    "completed_at": s.get("completed_at"),
                }
                for s in value
            ]
        else:
            extracted[field] = value
    return extracted


def get_existing_job_ids(store: DailyStatsStore, collection_date: Optional[str] = None) -> set:
    """Get the set of job IDs already stored for a given date."""
    existing = store.get_jobs(collection_date=collection_date)
    ids = set()
    for record in existing:
        data = record.get("data", {})
        job_id = data.get("id")
        if job_id:
            ids.add(job_id)
    return ids


def _get_stored_run_ids_by_repo(
    store: DailyStatsStore, collection_date: Optional[str] = None
) -> dict[str, list[int]]:
    """
    Read stored workflow runs and group run IDs by owner/repo.

    Returns:
        Dict mapping "owner/repo" to list of run IDs.
    """
    runs = store.get_workflow_runs(collection_date=collection_date)
    by_repo = defaultdict(list)
    for record in runs:
        data = record.get("data", {})
        run_id = data.get("id")
        repo_full = data.get("repository_full_name", "")
        if run_id and repo_full:
            by_repo[repo_full].append(run_id)
    return dict(by_repo)


def collect_jobs(
    owner: str,
    repo: str,
    token: Optional[str] = None,
    base_url: str = "https://api.github.com",
    store_dir: str = "monitoring_data",
    collection_date: Optional[str] = None,
    run_ids: Optional[list[int]] = None,
    deduplicate: bool = True,
    max_runs: Optional[int] = None,
) -> dict:
    """
    Collect job data for workflow runs in a single repo.

    If run_ids is provided, fetches jobs for those specific runs.
    Otherwise, reads stored workflow runs for the collection date.

    Args:
        owner: Repository owner.
        repo: Repository name.
        token: GitHub PAT.
        base_url: GitHub API base URL.
        store_dir: Path to monitoring data directory.
        collection_date: Date to read runs from and store jobs to.
        run_ids: Specific run IDs to fetch jobs for. If None, reads from storage.
        deduplicate: Skip jobs already in storage.
        max_runs: Limit number of runs to process (useful for large repos).

    Returns:
        Summary dict with collection results.
    """
    start_time = time.time()
    store = DailyStatsStore(store_dir)
    col_date = collection_date or date.today().strftime("%Y-%m-%d")

    summary = {
        "owner": owner,
        "repo": repo,
        "collection_date": col_date,
        "runs_processed": 0,
        "jobs_fetched": 0,
        "jobs_new": 0,
        "jobs_skipped_duplicate": 0,
        "runs_with_errors": 0,
        "errors": [],
    }

    # Determine which runs to fetch jobs for
    if run_ids is None:
        runs_by_repo = _get_stored_run_ids_by_repo(store, collection_date)
        repo_full = f"{owner}/{repo}"
        run_ids = runs_by_repo.get(repo_full, [])
        if not run_ids:
            logger.info("No stored workflow runs found for %s on %s", repo_full, col_date)
            _log_collection(store, summary, start_time, collection_date)
            return summary

    if max_runs:
        run_ids = run_ids[:max_runs]

    # Get existing job IDs for dedup
    existing_ids = set()
    if deduplicate:
        existing_ids = get_existing_job_ids(store, collection_date)
        if existing_ids:
            logger.info("Found %d existing jobs in storage for dedup", len(existing_ids))

    # Fetch jobs from GitHub API
    try:
        client = GitHubClient(token=token, owner=owner, repo=repo, base_url=base_url)
    except Exception as e:
        summary["errors"].append(f"Client init failed: {e}")
        _log_collection(store, summary, start_time, collection_date)
        return summary

    all_new_jobs = []
    try:
        for i, run_id in enumerate(run_ids):
            try:
                jobs = client.list_jobs_for_run(run_id)
                summary["runs_processed"] += 1
                summary["jobs_fetched"] += len(jobs)

                for job in jobs:
                    extracted = extract_job_data(job)
                    job_id = extracted.get("id")

                    if deduplicate and job_id in existing_ids:
                        summary["jobs_skipped_duplicate"] += 1
                        continue

                    # Tag with repo info for org-wide queries
                    extracted["repository_full_name"] = f"{owner}/{repo}"
                    all_new_jobs.append(extracted)

                if (i + 1) % 50 == 0:
                    logger.info("Progress: %d/%d runs processed, %d jobs fetched",
                                i + 1, len(run_ids), summary["jobs_fetched"])

            except GitHubAPIError as e:
                summary["runs_with_errors"] += 1
                if e.status_code == 404:
                    logger.debug("Run %d not found (may have been deleted)", run_id)
                else:
                    logger.warning("Error fetching jobs for run %d: %s", run_id, e)
                    summary["errors"].append(f"Run {run_id}: {e}")

        summary["rate_limit"] = client.get_rate_limit_status()
        summary["api_requests"] = client.request_count

    except Exception as e:
        logger.error("Unexpected error during job collection: %s", e)
        summary["errors"].append(str(e))
    finally:
        client.close()

    summary["jobs_new"] = len(all_new_jobs)

    if all_new_jobs:
        store.append_jobs(all_new_jobs, collection_date=collection_date)
        logger.info("Stored %d new jobs", len(all_new_jobs))
    else:
        logger.info("No new jobs to store")

    _log_collection(store, summary, start_time, collection_date)
    return summary


def collect_org_jobs(
    org: str,
    token: Optional[str] = None,
    base_url: str = "https://api.github.com",
    store_dir: str = "monitoring_data",
    collection_date: Optional[str] = None,
    deduplicate: bool = True,
    max_runs_per_repo: Optional[int] = None,
) -> dict:
    """
    Collect job data across all repos in an org.

    Reads stored workflow runs (from Task 3), groups them by repo,
    then fetches jobs for each repo's runs.

    Args:
        org: GitHub organization name.
        token: GitHub PAT.
        base_url: GitHub API base URL.
        store_dir: Path to monitoring data directory.
        collection_date: Date to read runs from and store jobs to.
        deduplicate: Skip jobs already in storage.
        max_runs_per_repo: Limit runs processed per repo.

    Returns:
        Summary dict with collection results.
    """
    start_time = time.time()
    store = DailyStatsStore(store_dir)
    col_date = collection_date or date.today().strftime("%Y-%m-%d")

    summary = {
        "org": org,
        "collection_date": col_date,
        "repos_processed": 0,
        "total_runs_processed": 0,
        "total_jobs_fetched": 0,
        "total_jobs_new": 0,
        "total_jobs_skipped_duplicate": 0,
        "repo_summaries": {},
        "errors": [],
    }

    # Read all stored workflow runs grouped by repo
    runs_by_repo = _get_stored_run_ids_by_repo(store, collection_date)
    if not runs_by_repo:
        logger.info("No stored workflow runs found for date %s", col_date)
        _log_collection(store, summary, start_time, collection_date)
        return summary

    logger.info("Found stored runs in %d repos for %s", len(runs_by_repo), col_date)

    for repo_full, run_ids in sorted(runs_by_repo.items()):
        parts = repo_full.split("/", 1)
        if len(parts) != 2:
            logger.warning("Skipping malformed repo name: %s", repo_full)
            continue

        repo_owner, repo_name = parts
        logger.info("Collecting jobs for %s (%d runs)", repo_full, len(run_ids))

        repo_summary = collect_jobs(
            owner=repo_owner,
            repo=repo_name,
            token=token,
            base_url=base_url,
            store_dir=store_dir,
            collection_date=collection_date,
            run_ids=run_ids,
            deduplicate=deduplicate,
            max_runs=max_runs_per_repo,
        )

        summary["repos_processed"] += 1
        summary["total_runs_processed"] += repo_summary["runs_processed"]
        summary["total_jobs_fetched"] += repo_summary["jobs_fetched"]
        summary["total_jobs_new"] += repo_summary["jobs_new"]
        summary["total_jobs_skipped_duplicate"] += repo_summary["jobs_skipped_duplicate"]
        summary["repo_summaries"][repo_full] = {
            "runs_processed": repo_summary["runs_processed"],
            "jobs_fetched": repo_summary["jobs_fetched"],
            "jobs_new": repo_summary["jobs_new"],
        }
        if repo_summary["errors"]:
            summary["errors"].extend(repo_summary["errors"])

    summary["duration_seconds"] = round(time.time() - start_time, 2)

    # Log at the org level too
    store.log_collection(
        {
            "collector": "collect_org_jobs",
            "summary": {
                "org": org,
                "repos_processed": summary["repos_processed"],
                "total_jobs_fetched": summary["total_jobs_fetched"],
                "total_jobs_new": summary["total_jobs_new"],
                "duration_seconds": summary["duration_seconds"],
            },
        },
        collection_date=collection_date,
    )

    logger.info(
        "Org collection complete: %d repos, %d runs, %d jobs fetched, %d new in %.2fs",
        summary["repos_processed"],
        summary["total_runs_processed"],
        summary["total_jobs_fetched"],
        summary["total_jobs_new"],
        summary["duration_seconds"],
    )

    return summary


def _log_collection(store: DailyStatsStore, summary: dict, start_time: float,
                    collection_date: Optional[str] = None) -> None:
    """Log collection metadata to the store."""
    duration = round(time.time() - start_time, 2)
    summary["duration_seconds"] = duration
    store.log_collection(
        {
            "collector": "collect_jobs",
            "summary": summary,
        },
        collection_date=collection_date,
    )
    logger.info("Job collection complete in %.2fs: %d runs, %d jobs fetched, %d new, %d dupes",
                duration, summary.get("runs_processed", summary.get("total_runs_processed", 0)),
                summary.get("jobs_fetched", summary.get("total_jobs_fetched", 0)),
                summary.get("jobs_new", summary.get("total_jobs_new", 0)),
                summary.get("jobs_skipped_duplicate", summary.get("total_jobs_skipped_duplicate", 0)))


def main():
    parser = argparse.ArgumentParser(description="Collect GitHub Actions job-level data")
    parser.add_argument("--owner", help="Repository owner (org or user)")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument("--org", help="Organization name (collects across all repos)")
    parser.add_argument("--token", help="GitHub PAT (or set GITHUB_TOKEN env var)")
    parser.add_argument("--base-url", default="https://api.github.com",
                        help="GitHub API base URL")
    parser.add_argument("--store-dir", default="monitoring_data",
                        help="Path to monitoring data directory")
    parser.add_argument("--date", help="Collection date (default: today)")
    parser.add_argument("--max-runs", type=int, help="Max runs to process per repo")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if args.org:
        summary = collect_org_jobs(
            org=args.org,
            token=args.token,
            base_url=args.base_url,
            store_dir=args.store_dir,
            collection_date=args.date,
            deduplicate=not args.no_dedup,
            max_runs_per_repo=args.max_runs,
        )
        # Print summary
        print(f"\n{'='*60}")
        print("Org Job Collection Summary")
        print(f"{'='*60}")
        print(f"  Org:                {summary['org']}")
        print(f"  Repos processed:    {summary['repos_processed']}")
        print(f"  Runs processed:     {summary['total_runs_processed']}")
        print(f"  Jobs fetched:       {summary['total_jobs_fetched']}")
        print(f"  New jobs stored:    {summary['total_jobs_new']}")
        print(f"  Duplicates:         {summary['total_jobs_skipped_duplicate']}")
        print(f"  Duration:           {summary.get('duration_seconds', 0):.2f}s")
        print()
        for repo, rs in summary["repo_summaries"].items():
            print(f"  {repo}: {rs['runs_processed']} runs, {rs['jobs_fetched']} jobs fetched, {rs['jobs_new']} new")

    elif args.owner and args.repo:
        summary = collect_jobs(
            owner=args.owner,
            repo=args.repo,
            token=args.token,
            base_url=args.base_url,
            store_dir=args.store_dir,
            collection_date=args.date,
            deduplicate=not args.no_dedup,
            max_runs=args.max_runs,
        )
        # Print summary
        print(f"\n{'='*60}")
        print("Job Collection Summary")
        print(f"{'='*60}")
        print(f"  Runs processed:  {summary['runs_processed']}")
        print(f"  Jobs fetched:    {summary['jobs_fetched']}")
        print(f"  New jobs stored: {summary['jobs_new']}")
        print(f"  Duplicates:      {summary['jobs_skipped_duplicate']}")
        print(f"  Duration:        {summary.get('duration_seconds', 0):.2f}s")
        print(f"  API requests:    {summary.get('api_requests', 'N/A')}")

        rate = summary.get("rate_limit", {})
        if rate:
            print(f"  Rate limit:      {rate.get('remaining', '?')}/{rate.get('limit', '?')} remaining")
    else:
        parser.error("Provide either --org OR both --owner and --repo")
        return

    if summary.get("errors"):
        print(f"\n  Errors ({len(summary['errors'])}):")
        for err in summary["errors"][:10]:
            print(f"    - {err}")
        if len(summary["errors"]) > 10:
            print(f"    ... and {len(summary['errors']) - 10} more")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
