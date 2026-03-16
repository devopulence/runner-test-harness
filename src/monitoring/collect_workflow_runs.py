"""
Workflow Run Collector (Story 3)

Collects workflow run data from GitHub API and stores it in the daily
stats store. Captures status, timestamps, actors, branches, and event types.

Usage:
    # Collect today's runs for a repo
    python -m src.monitoring.collect_workflow_runs --owner Devopulence --repo test-workflows

    # Collect with date filter
    python -m src.monitoring.collect_workflow_runs --owner Devopulence --repo test-workflows --created ">=2026-03-15"

    # Collect for a specific status
    python -m src.monitoring.collect_workflow_runs --owner Devopulence --repo test-workflows --status completed

    # Org-wide collection
    python -m src.monitoring.collect_workflow_runs --org Devopulence
"""

import argparse
import logging
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

from .github_client import GitHubClient, GitHubAPIError
from .storage import DailyStatsStore

logger = logging.getLogger(__name__)

# Fields we extract from each workflow run for storage
RUN_FIELDS = [
    "id",
    "name",
    "workflow_id",
    "status",
    "conclusion",
    "event",
    "head_branch",
    "head_sha",
    "actor",
    "created_at",
    "updated_at",
    "run_started_at",
    "run_attempt",
    "run_number",
    "html_url",
    "repository",
]


def extract_run_data(run: dict) -> dict:
    """Extract the key fields from a raw GitHub workflow run response."""
    extracted = {}
    for field in RUN_FIELDS:
        value = run.get(field)
        # Flatten nested objects to just their key identifiers
        if field == "actor" and isinstance(value, dict):
            extracted["actor_login"] = value.get("login", "")
            extracted["actor_id"] = value.get("id")
        elif field == "repository" and isinstance(value, dict):
            extracted["repository_full_name"] = value.get("full_name", "")
            extracted["repository_name"] = value.get("name", "")
        else:
            extracted[field] = value
    return extracted


def get_existing_run_ids(store: DailyStatsStore, collection_date: Optional[str] = None) -> set:
    """Get the set of run IDs already stored for a given date."""
    existing = store.get_workflow_runs(collection_date=collection_date)
    ids = set()
    for record in existing:
        data = record.get("data", {})
        run_id = data.get("id")
        if run_id:
            ids.add(run_id)
    return ids


def collect_workflow_runs(
    owner: str,
    repo: str,
    token: Optional[str] = None,
    base_url: str = "https://api.github.com",
    store_dir: str = "monitoring_data",
    status: Optional[str] = None,
    branch: Optional[str] = None,
    event: Optional[str] = None,
    created: Optional[str] = None,
    actor: Optional[str] = None,
    workflow_id: Optional[str] = None,
    max_pages: int = 10,
    collection_date: Optional[str] = None,
    deduplicate: bool = True,
) -> dict:
    """
    Collect workflow runs from GitHub API and store them.

    Args:
        owner: Repository owner (org or user).
        repo: Repository name.
        token: GitHub PAT. Falls back to GITHUB_TOKEN env var.
        base_url: GitHub API base URL.
        store_dir: Path to monitoring data directory.
        status: Filter by status (queued, in_progress, completed).
        branch: Filter by branch name.
        event: Filter by event type (push, pull_request, workflow_dispatch).
        created: Filter by creation date (e.g. ">=2026-03-15").
        actor: Filter by actor username.
        workflow_id: Collect runs for a specific workflow file only.
        max_pages: Max API pages to fetch.
        collection_date: Date to store data under (default: today).
        deduplicate: Skip runs already in storage (by run ID).

    Returns:
        Summary dict with collection results.
    """
    start_time = time.time()
    store = DailyStatsStore(store_dir)
    summary = {
        "owner": owner,
        "repo": repo,
        "collection_date": collection_date or date.today().strftime("%Y-%m-%d"),
        "filters": {
            "status": status,
            "branch": branch,
            "event": event,
            "created": created,
            "actor": actor,
            "workflow_id": workflow_id,
        },
        "runs_fetched": 0,
        "runs_new": 0,
        "runs_skipped_duplicate": 0,
        "errors": [],
    }

    # Get existing run IDs for dedup
    existing_ids = set()
    if deduplicate:
        existing_ids = get_existing_run_ids(store, collection_date)
        if existing_ids:
            logger.info("Found %d existing runs in storage for dedup", len(existing_ids))

    # Fetch runs from GitHub API
    try:
        client = GitHubClient(
            token=token,
            owner=owner,
            repo=repo,
            base_url=base_url,
        )

        filters = {}
        if status:
            filters["status"] = status
        if branch:
            filters["branch"] = branch
        if event:
            filters["event"] = event
        if created:
            filters["created"] = created
        if actor:
            filters["actor"] = actor

        if workflow_id:
            raw_runs = client.list_workflow_runs_for_workflow(
                workflow_id, max_pages=max_pages, **filters
            )
        else:
            raw_runs = client.list_workflow_runs(max_pages=max_pages, **filters)

        summary["runs_fetched"] = len(raw_runs)
        summary["rate_limit"] = client.get_rate_limit_status()
        summary["api_requests"] = client.request_count

        logger.info("Fetched %d workflow runs from %s/%s", len(raw_runs), owner, repo)

    except GitHubAPIError as e:
        logger.error("GitHub API error collecting runs: %s", e)
        summary["errors"].append(str(e))
        _log_collection(store, summary, start_time, collection_date)
        return summary
    except Exception as e:
        logger.error("Unexpected error collecting runs: %s", e)
        summary["errors"].append(str(e))
        _log_collection(store, summary, start_time, collection_date)
        return summary
    finally:
        try:
            client.close()
        except Exception:
            pass

    # Extract and deduplicate
    new_runs = []
    for run in raw_runs:
        extracted = extract_run_data(run)
        run_id = extracted.get("id")

        if deduplicate and run_id in existing_ids:
            summary["runs_skipped_duplicate"] += 1
            continue

        new_runs.append(extracted)

    summary["runs_new"] = len(new_runs)

    # Store
    if new_runs:
        store.append_workflow_runs(new_runs, collection_date=collection_date)
        logger.info("Stored %d new workflow runs", len(new_runs))
    else:
        logger.info("No new workflow runs to store")

    _log_collection(store, summary, start_time, collection_date)
    return summary


def collect_org_workflow_runs(
    org: str,
    token: Optional[str] = None,
    base_url: str = "https://api.github.com",
    store_dir: str = "monitoring_data",
    status: Optional[str] = None,
    created: Optional[str] = None,
    max_pages_per_repo: int = 5,
    collection_date: Optional[str] = None,
    deduplicate: bool = True,
) -> dict:
    """
    Collect workflow runs across all repos in an organization.

    Args:
        org: GitHub organization name.
        token: GitHub PAT.
        base_url: GitHub API base URL.
        store_dir: Path to monitoring data directory.
        status: Filter by status.
        created: Filter by creation date.
        max_pages_per_repo: Max pages per repo.
        collection_date: Date to store data under.
        deduplicate: Skip duplicate runs.

    Returns:
        Summary dict with collection results.
    """
    start_time = time.time()
    store = DailyStatsStore(store_dir)
    summary = {
        "org": org,
        "collection_date": collection_date or date.today().strftime("%Y-%m-%d"),
        "filters": {"status": status, "created": created},
        "runs_fetched": 0,
        "runs_new": 0,
        "runs_skipped_duplicate": 0,
        "repos_scanned": 0,
        "errors": [],
    }

    existing_ids = set()
    if deduplicate:
        existing_ids = get_existing_run_ids(store, collection_date)

    try:
        client = GitHubClient(token=token, owner=org, repo="", base_url=base_url)

        filters = {}
        if status:
            filters["status"] = status
        if created:
            filters["created"] = created

        raw_runs = client.list_org_workflow_runs(
            org, max_pages_per_repo=max_pages_per_repo, **filters
        )

        summary["runs_fetched"] = len(raw_runs)
        summary["rate_limit"] = client.get_rate_limit_status()
        summary["api_requests"] = client.request_count

        # Count repos from the runs
        repos_seen = set()
        for run in raw_runs:
            repo_info = run.get("repository", {})
            if isinstance(repo_info, dict):
                repos_seen.add(repo_info.get("full_name", ""))
        summary["repos_scanned"] = len(repos_seen)

        logger.info("Fetched %d runs across %d repos in org '%s'",
                     len(raw_runs), len(repos_seen), org)

    except GitHubAPIError as e:
        logger.error("GitHub API error: %s", e)
        summary["errors"].append(str(e))
        _log_collection(store, summary, start_time, collection_date)
        return summary
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        summary["errors"].append(str(e))
        _log_collection(store, summary, start_time, collection_date)
        return summary
    finally:
        try:
            client.close()
        except Exception:
            pass

    new_runs = []
    for run in raw_runs:
        extracted = extract_run_data(run)
        run_id = extracted.get("id")
        if deduplicate and run_id in existing_ids:
            summary["runs_skipped_duplicate"] += 1
            continue
        new_runs.append(extracted)

    summary["runs_new"] = len(new_runs)

    if new_runs:
        store.append_workflow_runs(new_runs, collection_date=collection_date)
        logger.info("Stored %d new workflow runs", len(new_runs))

    _log_collection(store, summary, start_time, collection_date)
    return summary


def _log_collection(store: DailyStatsStore, summary: dict, start_time: float,
                    collection_date: Optional[str] = None) -> None:
    """Log collection metadata to the store."""
    duration = round(time.time() - start_time, 2)
    summary["duration_seconds"] = duration
    store.log_collection(
        {
            "collector": "collect_workflow_runs",
            "summary": summary,
        },
        collection_date=collection_date,
    )
    logger.info("Collection complete in %.2fs: %d fetched, %d new, %d dupes",
                duration, summary["runs_fetched"], summary["runs_new"],
                summary["runs_skipped_duplicate"])


def main():
    parser = argparse.ArgumentParser(description="Collect GitHub Actions workflow runs")
    parser.add_argument("--owner", help="Repository owner (org or user)")
    parser.add_argument("--repo", help="Repository name")
    parser.add_argument("--org", help="Organization name (collects across all repos)")
    parser.add_argument("--token", help="GitHub PAT (or set GITHUB_TOKEN env var)")
    parser.add_argument("--base-url", default="https://api.github.com",
                        help="GitHub API base URL")
    parser.add_argument("--store-dir", default="monitoring_data",
                        help="Path to monitoring data directory")
    parser.add_argument("--status", help="Filter: queued, in_progress, completed")
    parser.add_argument("--branch", help="Filter by branch name")
    parser.add_argument("--event", help="Filter by event type")
    parser.add_argument("--created", help="Filter by creation date (e.g. >=2026-03-15)")
    parser.add_argument("--actor", help="Filter by actor username")
    parser.add_argument("--workflow-id", help="Collect runs for a specific workflow file")
    parser.add_argument("--max-pages", type=int, default=10, help="Max API pages to fetch")
    parser.add_argument("--date", help="Collection date (default: today)")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if args.org:
        summary = collect_org_workflow_runs(
            org=args.org,
            token=args.token,
            base_url=args.base_url,
            store_dir=args.store_dir,
            status=args.status,
            created=args.created,
            collection_date=args.date,
            deduplicate=not args.no_dedup,
        )
    elif args.owner and args.repo:
        summary = collect_workflow_runs(
            owner=args.owner,
            repo=args.repo,
            token=args.token,
            base_url=args.base_url,
            store_dir=args.store_dir,
            status=args.status,
            branch=args.branch,
            event=args.event,
            created=args.created,
            actor=args.actor,
            workflow_id=args.workflow_id,
            max_pages=args.max_pages,
            collection_date=args.date,
            deduplicate=not args.no_dedup,
        )
    else:
        parser.error("Provide either --org OR both --owner and --repo")
        return

    # Print summary
    print(f"\n{'='*60}")
    print("Collection Summary")
    print(f"{'='*60}")
    print(f"  Runs fetched:    {summary['runs_fetched']}")
    print(f"  New runs stored: {summary['runs_new']}")
    print(f"  Duplicates:      {summary['runs_skipped_duplicate']}")
    print(f"  Duration:        {summary.get('duration_seconds', 0):.2f}s")
    print(f"  API requests:    {summary.get('api_requests', 'N/A')}")

    rate = summary.get("rate_limit", {})
    if rate:
        print(f"  Rate limit:      {rate.get('remaining', '?')}/{rate.get('limit', '?')} remaining")

    if summary["errors"]:
        print(f"\n  Errors:")
        for err in summary["errors"]:
            print(f"    - {err}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
