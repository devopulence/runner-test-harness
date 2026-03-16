# Task 3: Collect Workflow Run Data via GitHub API

**Status:** Complete
**Date Completed:** 2026-03-16
**JIRA Reference:** MONITORING_PLAN.md - Task #3

---

## Overview

A workflow run collector (`src/monitoring/collect_workflow_runs.py`) that fetches workflow run data from the GitHub API and persists it to daily storage. Supports single-repo and org-wide collection with deduplication, filtering, and collection logging. This is the first data pipeline that connects Task 2 (GitHub API client) to Task 1 (JSON storage).

## Files Created

1. **`src/monitoring/collect_workflow_runs.py`** - Collector implementation with CLI
2. **`src/monitoring/test_collect_workflow_runs.py`** - 18 unit tests covering all functionality

## Key Features

### Field Extraction
Each raw GitHub API workflow run response is reduced to the essential monitoring fields:

| Extracted Field | Source |
|---|---|
| `id`, `name`, `workflow_id` | Direct from run |
| `status`, `conclusion` | Pipeline health |
| `event`, `head_branch`, `head_sha` | Trigger context |
| `created_at`, `updated_at`, `run_started_at` | Timing data |
| `run_attempt`, `run_number` | Retry/sequence tracking |
| `actor_login`, `actor_id` | Flattened from nested `actor` object |
| `repository_full_name`, `repository_name` | Flattened from nested `repository` object |
| `html_url` | Link back to GitHub UI |

Extra API fields (jobs_url, logs_url, check_suite_id, etc.) are excluded to keep storage lean.

### Deduplication
- Tracks stored run IDs per collection date
- Second collection of the same data skips already-stored runs
- Can be disabled with `deduplicate=False` or `--no-dedup` CLI flag

### Filtering
All GitHub API filters are supported:

| Filter | Example | Description |
|---|---|---|
| `--status` | `completed` | queued, in_progress, completed |
| `--branch` | `main` | Filter by branch name |
| `--event` | `workflow_dispatch` | push, pull_request, workflow_dispatch, etc. |
| `--created` | `>=2026-03-15` | Date range filter |
| `--actor` | `johndesp` | Filter by GitHub username |
| `--workflow-id` | `runner_test.yml` | Collect for a specific workflow only |

### Org-Wide Collection
- Scans all repositories in a GitHub organization
- Collects workflow runs from each repo with runs
- Deduplicates across the full org collection

### Collection Logging
Every collection run is logged to the store with:
- Collector name, timestamp
- Filters used, runs fetched/new/skipped
- Duration, API request count, rate limit status
- Any errors encountered

## API Reference

| Function | Description |
|---|---|
| `collect_workflow_runs()` | Collect runs for a single repo |
| `collect_org_workflow_runs()` | Collect runs across all repos in an org |
| `extract_run_data()` | Extract key fields from a raw API response |
| `get_existing_run_ids()` | Get stored run IDs for dedup |

## Usage

### Python API

```python
from src.monitoring import collect_workflow_runs, collect_org_workflow_runs

# Single repo collection
summary = collect_workflow_runs(
    owner="devopulence",
    repo="pythonProject",
    store_dir="monitoring_data",
    status="completed",
    max_pages=5,
)

# Org-wide collection
summary = collect_org_workflow_runs(
    org="devopulence",
    store_dir="monitoring_data",
    max_pages_per_repo=2,
)

print(f"Fetched: {summary['runs_fetched']}, New: {summary['runs_new']}")
```

### CLI

```bash
# Single repo
python -m src.monitoring.collect_workflow_runs \
    --owner devopulence --repo pythonProject --max-pages 3

# Org-wide
python -m src.monitoring.collect_workflow_runs --org devopulence

# With filters
python -m src.monitoring.collect_workflow_runs \
    --owner devopulence --repo pythonProject \
    --status completed --created ">=2026-03-01" -v

# Specific workflow
python -m src.monitoring.collect_workflow_runs \
    --owner devopulence --repo pythonProject \
    --workflow-id runner_test.yml
```

## Live Test Results (2026-03-16)

### Single Repo Test — `devopulence/pythonProject`

| Metric | Value |
|---|---|
| Runs fetched | 300 |
| New runs stored | 300 |
| Duplicates skipped | 0 |
| API requests | 3 |
| Duration | 9.16s |

### Deduplication Test — Second Run

| Metric | Value |
|---|---|
| Runs fetched | 300 |
| New runs stored | 0 |
| Duplicates skipped | 300 |
| Duration | 8.36s |

### Org-Wide Test — `devopulence`

| Metric | Value |
|---|---|
| Repos with runs | 8 |
| Runs fetched | 392 |
| New runs stored | 192 |
| Duplicates skipped | 200 (from prior single-repo test) |
| API requests | 183 |
| Duration | 43.82s |
| Rate limit remaining | 4,805 / 5,000 |

**Repos collected:**

| Repository | Runs |
|---|---|
| devopulence/pythonProject | 300 |
| devopulence/demo-terraform-modules-releases | 94 |
| devopulence/njt-kong | 34 |
| devopulence/terraform-modules-demo | 25 |
| devopulence/git-tfs | 15 |
| devopulence/releast-terraform-modules | 12 |
| devopulence/actions | 7 |
| devopulence/runner-builder | 5 |

**Total runs in storage after all tests: 492**

## Unit Test Results

All 18 tests pass. Run with:

```bash
python -m pytest src/monitoring/test_collect_workflow_runs.py -v
```

| Test | What it verifies |
|---|---|
| `test_extracts_core_fields` | Key fields (id, name, status, conclusion, branch) extracted correctly |
| `test_flattens_actor` | Nested actor object flattened to actor_login and actor_id |
| `test_flattens_repository` | Nested repository object flattened to repository_full_name and repository_name |
| `test_preserves_timestamps` | created_at, updated_at, run_started_at preserved exactly |
| `test_excludes_extra_fields` | jobs_url, logs_url, check_suite_id excluded from output |
| `test_handles_missing_fields` | Minimal run with only id/name doesn't crash |
| `test_empty_store_returns_empty_set` | Dedup returns empty set for new storage |
| `test_extracts_ids_from_stored_runs` | Dedup correctly reads existing run IDs from storage |
| `test_basic_collection` | Full pipeline: API fetch → extract → store → verify stored data |
| `test_deduplication` | Second collection skips already-stored runs |
| `test_no_dedup_flag` | deduplicate=False stores all runs regardless |
| `test_filters_passed_to_client` | status, branch, event, created filters forwarded to API client |
| `test_workflow_specific_collection` | workflow_id routes to list_workflow_runs_for_workflow() |
| `test_api_error_handled` | GitHubAPIError captured in summary, not raised |
| `test_collection_logged` | Collection metadata written to collection_log.json |
| `test_empty_result` | Zero runs returned handled gracefully |
| `test_org_collection` | Org-wide collection stores runs from multiple repos |
| `test_org_api_error_handled` | Org-level API errors captured in summary |

## Dependencies

- `src/monitoring/github_client.py` (Task 2) — API client with pagination and rate limiting
- `src/monitoring/storage.py` (Task 1) — Daily JSON storage
- `python-dotenv` — Loads `.env` for GITHUB_TOKEN
- Python standard library: `time`, `argparse`, `logging`, `datetime`

## Downstream Tasks That Depend on This

- **Task 4**: Job-level collection — similar pattern, calls `list_jobs_for_run()` for each collected run
- **Task 5**: Scheduled collection workflow — triggers `collect_workflow_runs()` on a cron
- **Task 6-14**: All metric computation tasks — read workflow_runs.json written by this collector