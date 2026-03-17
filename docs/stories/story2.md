# Task 2: Build GitHub API Client Module with Pagination and Rate Limiting

**Status:** Complete
**Date Completed:** 2026-03-12
**JIRA Reference:** MONITORING_PLAN.md - Task #2

---

## Overview

A synchronous GitHub REST API client (`src/monitoring/github_client.py`) purpose-built for monitoring data collection. Handles automatic pagination, rate limit compliance, and retry with exponential backoff. This is the HTTP layer that Tasks 3-5 will use to collect workflow and job data.

## Files Created

1. **`src/monitoring/github_client.py`** - Core client implementation
2. **`src/monitoring/test_github_client.py`** - 18 tests covering all functionality

## Key Features

### Pagination
- Automatic multi-page traversal using GitHub's `Link` response headers
- Configurable `max_pages` safety limit (default 50) to prevent runaway fetches
- Works with all list endpoints (workflow runs, jobs, etc.)

### Rate Limiting (per GitHub docs)
- **Primary rate limit**: Tracks `X-RateLimit-Remaining/Reset/Used/Limit` headers on every response
- **Primary exhaustion**: When `remaining=0`, waits until `x-ratelimit-reset` epoch time
- **Secondary rate limit**: Detects `Retry-After` header, waits the specified seconds
- **Unknown rate limit**: Falls back to 60-second wait per GitHub recommendation
- `get_rate_limit_status()` exposes current state for monitoring

### Retry with Backoff
- Exponential backoff with jitter on transient errors (429, 500, 502, 503, 504)
- Configurable `max_retries` (default 5) and `backoff_factor` (default 1.0)
- Connection errors retried at transport level via urllib3
- Non-retryable errors (404, 401, etc.) raise `GitHubAPIError` immediately

### Enterprise / Corporate Support
- Configurable `base_url` for GitHub Enterprise (e.g. `https://github.example.com/api/v3`)
- Custom CA certificate bundle via `ca_bundle` param or `REQUESTS_CA_BUNDLE` env var
- Proxy support via `proxies` param or `HTTP_PROXY`/`HTTPS_PROXY` env vars

## API Reference

| Method | Description |
|---|---|
| `list_workflow_runs(**filters)` | List all workflow runs with optional filters (status, branch, event, actor, created) |
| `get_workflow_run(run_id)` | Get a single workflow run by ID |
| `list_jobs_for_run(run_id)` | List all jobs for a workflow run (with steps, runner info, timestamps) |
| `list_workflow_runs_for_workflow(workflow_id)` | List runs for a specific workflow file |
| `get_rate_limit()` | Query the /rate_limit endpoint |
| `get_rate_limit_status()` | Return cached rate limit state (no API call) |
| `close()` | Close the HTTP session |

## Usage Example

```python
from src.monitoring import GitHubClient

# Basic usage
client = GitHubClient(token="ghp_xxx", owner="myorg", repo="myrepo")

# List completed runs from today
runs = client.list_workflow_runs(status="completed", created=">=2026-03-12")

# Get jobs for each run (auto-paginates if >100 jobs)
for run in runs:
    jobs = client.list_jobs_for_run(run["id"])
    for job in jobs:
        print(f"  Job: {job['name']} on {job['runner_name']} - {job['conclusion']}")

# Check rate limit
print(client.get_rate_limit_status())
# {'remaining': 4850, 'limit': 5000, 'used': 150, 'reset': 1741..., 'reset_in_seconds': 3200}

# Context manager usage
with GitHubClient(owner="myorg", repo="myrepo") as client:
    runs = client.list_workflow_runs(per_page=10, max_pages=1)

# GitHub Enterprise
client = GitHubClient(
    base_url="https://github.example.com/api/v3",
    owner="myorg", repo="myrepo"
)
```

## Design Decisions

1. **Sync `requests` over async `aiohttp`**: The monitoring collector runs as a scheduled job (Task 5), not a real-time tracker. Sync is simpler and sufficient.
2. **Application-level retry over urllib3 retry**: We need to distinguish rate limits from server errors and handle them differently. urllib3's Retry can't inspect response bodies for secondary rate limit messages.
3. **Iterator-based pagination**: `_paginate()` yields items lazily, so callers can break early without fetching all pages.
4. **Separate from `workflow_tracker.py`**: The existing tracker is tightly coupled to the test harness (matching dispatched workflows). This client is a general-purpose API layer for monitoring collection.

## Test Results

All 18 tests pass. Run with:

```bash
cd src/monitoring && python test_github_client.py
```

| Test | What it verifies |
|---|---|
| `test_single_page` | Single-page response returns all items |
| `test_multi_page_pagination` | Link header pagination fetches across 3 pages (201 items) |
| `test_max_pages_limit` | Pagination stops at max_pages even if more pages exist |
| `test_rate_limit_tracking` | Rate limit state updated from X-RateLimit-* headers |
| `test_primary_rate_limit_retry` | Primary rate limit (remaining=0) waits then retries |
| `test_secondary_rate_limit_retry_after` | Secondary rate limit respects Retry-After header |
| `test_transient_error_retry` | 502 errors trigger exponential backoff retry |
| `test_non_retryable_error_raises` | 404 raises GitHubAPIError immediately |
| `test_max_retries_exhausted` | All retries fail raises GitHubAPIError |
| `test_list_jobs_for_run` | Jobs endpoint returns job data with steps and runner info |
| `test_get_workflow_run` | Single run fetch returns correct data |
| `test_list_workflow_runs_with_filters` | Filters (status, branch, created) passed as query params |
| `test_list_workflow_runs_for_workflow` | Workflow-specific runs endpoint uses correct URL |
| `test_enterprise_base_url` | GitHub Enterprise base URL builds correct repo URLs |
| `test_context_manager` | Client works with `with` statement |
| `test_request_counter` | Request counter increments per API call |
| `test_no_token_raises` | Missing token raises ValueError |
| `test_link_header_parsing` | Link header parsed into correct rel:url dict |

## Dependencies

- `requests` (already in project requirements.txt)
- `urllib3` (transitive dependency of requests)
- Python standard library: `time`, `random`, `re`, `os`, `logging`

## Downstream Tasks That Depend on This

- **Task 3**: Collect workflow run data - calls `list_workflow_runs()`
- **Task 4**: Collect job-level data - calls `list_jobs_for_run()`
- **Task 5**: Scheduled collection workflow - uses this client in the collection script
- **Task 6-14**: All metric computation tasks benefit from paginated data collection