# Task 4: Collect Job-Level Data via GitHub API

**Status:** Complete
**Date Completed:** 2026-03-17
**JIRA Reference:** MONITORING_PLAN.md - Task #4

---

## Overview

A job-level data collector (`src/monitoring/collect_jobs.py`) that fetches job details from the GitHub API for workflow runs already stored by Task 3. Captures timestamps, runner assignment, step-level breakdowns, and conclusions. Supports single-repo and org-wide collection by reading stored workflow runs and fetching jobs for each repo.

## Files Created

1. **`src/monitoring/collect_jobs.py`** - Job collector implementation with CLI
2. **`src/monitoring/test_collect_jobs.py`** - 20 unit tests covering all functionality

## Key Features

### Field Extraction
Each raw GitHub API job response is reduced to essential monitoring fields:

| Extracted Field | Source |
|---|---|
| `id`, `run_id`, `workflow_name`, `name` | Job identity |
| `status`, `conclusion` | Job outcome |
| `created_at`, `started_at`, `completed_at` | Timing data (queue time = started - created) |
| `head_branch`, `head_sha`, `run_attempt` | Context |
| `runner_id`, `runner_name` | Runner assignment |
| `runner_group_id`, `runner_group_name` | Runner group |
| `labels` | Runner labels (self-hosted, ecs-fargate, linux, etc.) |
| `steps[]` | Step-level breakdown (name, number, status, conclusion, started_at, completed_at) |
| `html_url` | Link back to GitHub UI |
| `repository_full_name` | Added during collection for org-wide queries |

Extra API fields (node_id, run_url, url, check_run_url) are excluded to keep storage lean.

### Org-Wide Collection
- Reads stored workflow runs from Task 3, grouped by repository
- Fetches jobs for each repo's runs using separate API client instances
- Per-repo summaries in the collection output
- Configurable `max_runs_per_repo` to control API usage

### Deduplication
- Tracks stored job IDs per collection date
- Second collection skips already-stored jobs
- Can be disabled with `deduplicate=False` or `--no-dedup` CLI flag

### Error Resilience
- Deleted runs (404) are skipped without failing the whole collection
- Per-run errors tracked in summary
- Collection continues through individual run failures

### Collection Logging
Every collection run is logged to the store with:
- Collector name, timestamp
- Runs processed, jobs fetched/new/skipped
- Duration, API request count, rate limit status
- Per-repo breakdowns (org-wide mode)

## API Reference

| Function | Description |
|---|---|
| `collect_jobs()` | Collect jobs for a single repo (from stored runs or explicit run IDs) |
| `collect_org_jobs()` | Collect jobs across all repos in an org |
| `extract_job_data()` | Extract key fields from a raw API job response |
| `get_existing_job_ids()` | Get stored job IDs for dedup |

## Usage

### Python API

```python
from src.monitoring import collect_jobs, collect_org_jobs

# Single repo - reads stored runs automatically
summary = collect_jobs(
    owner="devopulence",
    repo="pythonProject",
    store_dir="monitoring_data",
    collection_date="2026-03-16",
)

# Single repo - explicit run IDs
summary = collect_jobs(
    owner="devopulence",
    repo="pythonProject",
    store_dir="monitoring_data",
    run_ids=[21945738937, 21945738938],
)

# Org-wide collection
summary = collect_org_jobs(
    org="devopulence",
    store_dir="monitoring_data",
    collection_date="2026-03-16",
    max_runs_per_repo=10,
)

print(f"Jobs fetched: {summary['total_jobs_fetched']}, New: {summary['total_jobs_new']}")
```

### CLI

```bash
# Single repo
python -m src.monitoring.collect_jobs \
    --owner devopulence --repo pythonProject --date 2026-03-16

# Org-wide
python -m src.monitoring.collect_jobs --org devopulence --date 2026-03-16

# Limit runs per repo
python -m src.monitoring.collect_jobs --org devopulence --max-runs 10

# Verbose output
python -m src.monitoring.collect_jobs --org devopulence -v
```

## Live Test Results (2026-03-17)

### Org-Wide Test — `devopulence` (max 10 runs per repo)

| Metric | Value |
|---|---|
| Repos processed | 8 |
| Runs processed | 72 |
| Jobs fetched | 126 |
| New jobs stored | 126 |
| Duration | 17.68s |
| Errors | 0 |

**Per-repo breakdown:**

| Repository | Runs | Jobs Fetched | Jobs New |
|---|---|---|---|
| devopulence/pythonProject | 10 | 40 | 40 |
| devopulence/terraform-modules-demo | 10 | 26 | 26 |
| devopulence/demo-terraform-modules-releases | 10 | 15 | 15 |
| devopulence/releast-terraform-modules | 10 | 13 | 13 |
| devopulence/njt-kong | 10 | 10 | 10 |
| devopulence/git-tfs | 10 | 9 | 9 |
| devopulence/runner-builder | 5 | 7 | 7 |
| devopulence/actions | 7 | 6 | 6 |

### Deduplication Test — Second Run

| Metric | Value |
|---|---|
| Jobs fetched | 126 |
| New jobs stored | 0 |
| Duplicates skipped | 126 |

### Sample Stored Job Record

```json
{
  "id": 50046776412,
  "run_id": 17615320012,
  "workflow_name": "Run Nexus",
  "name": "run-nexus",
  "status": "completed",
  "conclusion": "success",
  "created_at": "2025-09-10T13:27:09Z",
  "started_at": "2025-09-10T13:27:12Z",
  "completed_at": "2025-09-10T13:27:17Z",
  "runner_name": "GitHub Actions 1000000005",
  "runner_id": 1000000005,
  "labels": ["ubuntu-latest"],
  "steps": [...],
  "repository_full_name": "devopulence/actions"
}
```

## Unit Test Results

All 20 tests pass. Run with:

```bash
python -m pytest src/monitoring/test_collect_jobs.py -v
```

| Test | What it verifies |
|---|---|
| `test_extracts_core_fields` | Key fields (id, run_id, name, conclusion, runner_name) extracted correctly |
| `test_extracts_timestamps` | created_at, started_at, completed_at preserved exactly |
| `test_extracts_labels` | Runner labels array preserved |
| `test_extracts_steps_with_essential_fields` | Steps reduced to name, number, status, conclusion, started_at, completed_at |
| `test_excludes_extra_fields` | node_id, run_url, url, check_run_url excluded |
| `test_handles_missing_steps` | Minimal job with no steps doesn't crash |
| `test_empty_store` | Dedup returns empty set for new storage |
| `test_extracts_ids` | Dedup correctly reads existing job IDs from storage |
| `test_groups_by_repo` | Stored runs correctly grouped by repository for org-wide collection |
| `test_basic_collection_with_run_ids` | Full pipeline with explicit run IDs: API fetch → extract → store |
| `test_reads_runs_from_storage` | When no run_ids given, reads stored workflow runs automatically |
| `test_deduplication` | Second collection skips already-stored jobs |
| `test_max_runs_limit` | max_runs limits how many runs are processed |
| `test_404_run_skipped` | Deleted runs (404) skipped, collection continues |
| `test_no_stored_runs_returns_early` | No stored runs returns summary with zeros, no API calls made |
| `test_adds_repo_tag_to_jobs` | Each job gets repository_full_name tagged |
| `test_collection_logged` | Collection metadata written to collection_log.json |
| `test_org_collection_across_repos` | Org-wide collection stores jobs from multiple repos |
| `test_org_no_stored_runs` | Org collection with no stored runs returns early |
| `test_empty_store` (GetStoredRunIdsByRepo) | Empty storage returns empty dict |

## Dependencies

- `src/monitoring/github_client.py` (Task 2) — API client with pagination and rate limiting
- `src/monitoring/storage.py` (Task 1) — Daily JSON storage
- `src/monitoring/collect_workflow_runs.py` (Task 3) — Provides stored workflow runs to read from
- `python-dotenv` — Loads `.env` for GITHUB_TOKEN
- Python standard library: `time`, `argparse`, `logging`, `datetime`, `collections`

## Downstream Tasks That Depend on This

- **Task 5**: Scheduled collection workflow — triggers `collect_jobs()` after workflow run collection
- **Task 6**: Pipeline health metrics — reads job conclusions for success/failure rates
- **Task 7**: Failure pattern analysis — reads job data to identify flaky runners/steps
- **Task 9**: Queue time metrics — uses `created_at` vs `started_at` to compute developer wait time
- **Task 11**: Step-level timing breakdown — reads step arrays for per-step duration analysis
- **Task 13**: Execution time distributions — reads job durations for p50/p95/p99 calculations
- **Task 14**: Retry tracking — uses `run_attempt` to identify re-runs
