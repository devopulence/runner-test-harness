# Task 1: Create JSON Storage Structure for Daily Stats Collection

**Status:** Complete
**Date Completed:** 2026-03-11
**JIRA Reference:** MONITORING_PLAN.md - Task #1

---

## Overview

A JSON file storage system (`src/monitoring/storage.py`) that organizes GitHub Actions monitoring data into daily directories. It's the data layer that all future tasks will write to and read from.

## New Directory: `src/monitoring/`

### Files Created

1. **`__init__.py`** - Module init, exports `DailyStatsStore` and `StatsRecord`
2. **`storage.py`** - Core storage implementation with:
   - `DailyStatsStore` class - file-based JSON storage organized by date
   - `StatsRecord` dataclass - timestamped record with source metadata
3. **`test_storage.py`** - 7 tests covering all operations

## Storage Design

```
monitoring_data/
├── 2026-03-11/
│   ├── workflow_runs.json      # Raw workflow run data (GitHub API)
│   ├── jobs.json               # Raw job-level data (GitHub API)
│   ├── runner_status.json      # Runner pool snapshots (ARC/OpenShift)
│   ├── computed_metrics.json   # Derived metrics
│   └── collection_log.json    # Collection run metadata
├── 2026-03-12/
│   └── ...
└── index.json                  # Index of all collection days
```

## Key Capabilities

- **Append-based writes** - multiple collection runs accumulate within a day
- **Date-based organization** - easy to query by date range
- **Separate files per data type** - workflow runs, jobs, runner status, computed metrics
- **Data retention** - `purge_before()` for cleanup of old data
- **Index generation** - `get_index()` builds a summary across all dates
- **Empty-safe reads** - returns sensible defaults for missing data

## API Reference

The `DailyStatsStore` class provides:

| Method | Description |
|---|---|
| `append_workflow_runs()` | Accumulate raw workflow run data from GitHub API |
| `append_jobs()` | Accumulate raw job-level data from GitHub API |
| `append_runner_status()` | Accumulate runner pool snapshots from ARC/OpenShift |
| `save_computed_metrics()` | Store derived metrics (queue time, throughput, etc.) |
| `log_collection()` | Track when collections happened |
| `get_workflow_runs()` | Read workflow runs for a date |
| `get_jobs()` | Read jobs for a date |
| `get_runner_status()` | Read runner status for a date |
| `get_computed_metrics()` | Read computed metrics for a date |
| `get_collection_log()` | Read collection log for a date |
| `list_dates()` | List all dates with data (sorted ascending) |
| `get_index()` | Build summary index across all dates |
| `get_date_summary()` | Get file counts and sizes for a specific date |
| `purge_before()` | Remove daily directories older than a cutoff date |

Each record gets wrapped in a `StatsRecord` with a timestamp and source tag (`github_api`, `arc_api`, or `computed`).

## Usage Example

```python
from src.monitoring import DailyStatsStore

store = DailyStatsStore("monitoring_data")

# Write data
store.append_workflow_runs([{"id": 1001, "status": "completed", "conclusion": "success"}])
store.append_jobs([{"id": 5001, "run_id": 1001, "runner_name": "runner-1"}])
store.save_computed_metrics({"success_rate": 0.95, "avg_queue_time_seconds": 30.5})

# Read data
runs = store.get_workflow_runs()                          # Today's runs
runs = store.get_workflow_runs(collection_date="2026-03-10")  # Specific date
dates = store.list_dates()                                # All available dates

# Housekeeping
store.purge_before("2026-02-01")  # Remove old data
```

## Test Results

All 7 tests pass. Run with:

```bash
cd src/monitoring && python test_storage.py
```

| Test | What it verifies |
|---|---|
| `test_basic_workflow` | Full round-trip: write runs, jobs, runner status, metrics, log then read them all back with correct values |
| `test_append_accumulates` | Two separate `append_workflow_runs()` calls combine into one file (3 total records) |
| `test_list_dates_and_index` | Writing to 3 different dates, `list_dates()` returns them sorted, `get_index()` has all 3 |
| `test_date_summary` | Summary shows file counts/sizes; non-existent date returns `exists: False` |
| `test_purge_before` | Purging before a cutoff date removes old directories, keeps newer ones |
| `test_directory_structure` | Verifies actual files exist on disk with expected names and valid pretty-printed JSON |
| `test_empty_reads` | Reading from a date with no data returns empty lists/None (no crashes) |

## Dependencies

- Python standard library only (`json`, `pathlib`, `dataclasses`, `datetime`, `logging`)
- No external packages required

## Downstream Tasks That Depend on This

- **Task 2**: GitHub API client module - will write collected data into this storage
- **Task 3**: Workflow run collection - uses `append_workflow_runs()`
- **Task 4**: Job-level collection - uses `append_jobs()`
- **Task 5**: Scheduled collection workflow - triggers writes to this store
- **Task 6-14**: All metric computation tasks - read from and write computed metrics to this store
- **Task 15-19**: ARC/runner tasks - use `append_runner_status()`
- **Task 20-21**: Combined analysis - reads across all file types
