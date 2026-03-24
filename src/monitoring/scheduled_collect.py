"""
Scheduled Collection Script (Task 5)

Runs the full collection pipeline: workflow runs + jobs for an org.
Designed to be called by a GitHub Actions scheduled workflow or cron job.

Usage:
    # Collect everything for an org
    python -m src.monitoring.scheduled_collect --org devopulence

    # With max runs per repo limit
    python -m src.monitoring.scheduled_collect --org pnc-sandbox --max-runs 50

    # Single repo mode
    python -m src.monitoring.scheduled_collect --owner devopulence --repo pythonProject

    # Specify collection date (for backfill)
    python -m src.monitoring.scheduled_collect --org pnc-sandbox --date 2026-03-20
"""

import argparse
import json
import logging
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

from .collect_workflow_runs import collect_workflow_runs, collect_org_workflow_runs
from .collect_jobs import collect_jobs, collect_org_jobs
from .storage import DailyStatsStore

logger = logging.getLogger(__name__)


def scheduled_collect(
    org: str = None,
    owner: str = None,
    repo: str = None,
    token: str = None,
    base_url: str = "https://api.github.com",
    store_dir: str = "monitoring_data",
    collection_date: str = None,
    max_pages: int = 10,
    max_runs_per_repo: int = None,
    skip_jobs: bool = False,
) -> dict:
    """
    Run the full collection pipeline.

    Step 1: Collect workflow runs (org-wide or single repo)
    Step 2: Collect jobs for those runs
    """
    start_time = time.time()
    col_date = collection_date or date.today().strftime("%Y-%m-%d")

    summary = {
        "collection_date": col_date,
        "mode": "org" if org else "repo",
        "target": org or f"{owner}/{repo}",
        "steps": {},
        "errors": [],
        "success": True,
    }

    # ── Step 1: Collect workflow runs ──────────────────────

    logger.info("=" * 60)
    logger.info("STEP 1: Collecting workflow runs")
    logger.info("=" * 60)

    try:
        if org:
            runs_summary = collect_org_workflow_runs(
                org=org,
                token=token,
                base_url=base_url,
                store_dir=store_dir,
                collection_date=collection_date,
                max_pages_per_repo=max_pages,
            )
        else:
            runs_summary = collect_workflow_runs(
                owner=owner,
                repo=repo,
                token=token,
                base_url=base_url,
                store_dir=store_dir,
                max_pages=max_pages,
                collection_date=collection_date,
            )

        summary["steps"]["workflow_runs"] = {
            "runs_fetched": runs_summary.get("runs_fetched", 0),
            "runs_new": runs_summary.get("runs_new", 0),
            "runs_skipped_duplicate": runs_summary.get("runs_skipped_duplicate", 0),
            "duration_seconds": runs_summary.get("duration_seconds", 0),
            "errors": runs_summary.get("errors", []),
        }

        if runs_summary.get("errors"):
            summary["errors"].extend(runs_summary["errors"])

        logger.info("Workflow runs: %d fetched, %d new",
                     runs_summary.get("runs_fetched", 0),
                     runs_summary.get("runs_new", 0))

    except Exception as e:
        logger.error("Failed to collect workflow runs: %s", e)
        summary["steps"]["workflow_runs"] = {"error": str(e)}
        summary["errors"].append(f"Workflow runs: {e}")
        summary["success"] = False

    # ── Step 2: Collect jobs ──────────────────────────────

    if not skip_jobs:
        logger.info("")
        logger.info("=" * 60)
        logger.info("STEP 2: Collecting job data")
        logger.info("=" * 60)

        try:
            if org:
                jobs_summary = collect_org_jobs(
                    org=org,
                    token=token,
                    base_url=base_url,
                    store_dir=store_dir,
                    collection_date=collection_date,
                    max_runs_per_repo=max_runs_per_repo,
                )
            else:
                jobs_summary = collect_jobs(
                    owner=owner,
                    repo=repo,
                    token=token,
                    base_url=base_url,
                    store_dir=store_dir,
                    collection_date=collection_date,
                    max_runs=max_runs_per_repo,
                )

            summary["steps"]["jobs"] = {
                "jobs_fetched": jobs_summary.get("jobs_fetched", jobs_summary.get("total_jobs_fetched", 0)),
                "jobs_new": jobs_summary.get("jobs_new", jobs_summary.get("total_jobs_new", 0)),
                "jobs_skipped_duplicate": jobs_summary.get("jobs_skipped_duplicate", jobs_summary.get("total_jobs_skipped_duplicate", 0)),
                "duration_seconds": jobs_summary.get("duration_seconds", 0),
                "errors": jobs_summary.get("errors", []),
            }

            if jobs_summary.get("errors"):
                summary["errors"].extend(jobs_summary["errors"])

            logger.info("Jobs: %d fetched, %d new",
                         summary["steps"]["jobs"]["jobs_fetched"],
                         summary["steps"]["jobs"]["jobs_new"])

        except Exception as e:
            logger.error("Failed to collect jobs: %s", e)
            summary["steps"]["jobs"] = {"error": str(e)}
            summary["errors"].append(f"Jobs: {e}")
            summary["success"] = False

    # ── Summary ───────────────────────────────────────────

    total_duration = round(time.time() - start_time, 2)
    summary["total_duration_seconds"] = total_duration

    store = DailyStatsStore(store_dir)
    store.log_collection(
        {
            "collector": "scheduled_collect",
            "summary": summary,
        },
        collection_date=collection_date,
    )

    date_summary = store.get_date_summary(collection_date=col_date)
    summary["storage"] = date_summary

    logger.info("")
    logger.info("=" * 60)
    logger.info("COLLECTION COMPLETE")
    logger.info("=" * 60)
    logger.info("  Duration:     %.2fs", total_duration)
    logger.info("  Date:         %s", col_date)
    logger.info("  Target:       %s", summary["target"])

    runs_step = summary["steps"].get("workflow_runs", {})
    logger.info("  Runs:         %d fetched, %d new",
                runs_step.get("runs_fetched", 0), runs_step.get("runs_new", 0))

    if not skip_jobs:
        jobs_step = summary["steps"].get("jobs", {})
        logger.info("  Jobs:         %d fetched, %d new",
                     jobs_step.get("jobs_fetched", 0), jobs_step.get("jobs_new", 0))

    if summary["errors"]:
        logger.warning("  Errors:       %d", len(summary["errors"]))
    else:
        logger.info("  Errors:       None")

    logger.info("=" * 60)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Scheduled collection - runs full pipeline (workflow runs + jobs)"
    )
    parser.add_argument("--org", help="Organization name (org-wide collection)")
    parser.add_argument("--owner", help="Repository owner (single-repo mode)")
    parser.add_argument("--repo", help="Repository name (single-repo mode)")
    parser.add_argument("--token", help="GitHub PAT (or set GITHUB_TOKEN env var)")
    parser.add_argument("--base-url", default="https://api.github.com",
                        help="GitHub API base URL")
    parser.add_argument("--store-dir", default="monitoring_data",
                        help="Path to monitoring data directory")
    parser.add_argument("--date", help="Collection date (default: today)")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="Max API pages for workflow run collection")
    parser.add_argument("--max-runs", type=int,
                        help="Max runs to fetch jobs for per repo")
    parser.add_argument("--skip-jobs", action="store_true",
                        help="Only collect workflow runs, skip job data")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    if not args.org and not (args.owner and args.repo):
        parser.error("Provide either --org OR both --owner and --repo")

    summary = scheduled_collect(
        org=args.org,
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        base_url=args.base_url,
        store_dir=args.store_dir,
        collection_date=args.date,
        max_pages=args.max_pages,
        max_runs_per_repo=args.max_runs,
        skip_jobs=args.skip_jobs,
    )

    if not summary["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
