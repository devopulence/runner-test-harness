"""
JSON Storage Structure for Daily Stats Collection (Story 1)

Provides file-based JSON storage organized by date for GitHub Actions metrics.
Each day gets its own directory with separate files for workflow runs, jobs,
runner status, and computed metrics.

Directory structure:
    monitoring_data/
    ├── 2026-03-11/
    │   ├── workflow_runs.json      # Raw workflow run data from GitHub API
    │   ├── jobs.json               # Raw job-level data from GitHub API
    │   ├── runner_status.json      # Runner pool snapshots (ARC/OpenShift)
    │   ├── computed_metrics.json   # Derived metrics (queue time, throughput, etc.)
    │   └── collection_log.json    # Metadata about collection runs
    ├── 2026-03-12/
    │   └── ...
    └── index.json                  # Index of all collection days
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# File names within each daily directory
WORKFLOW_RUNS_FILE = "workflow_runs.json"
JOBS_FILE = "jobs.json"
RUNNER_STATUS_FILE = "runner_status.json"
COMPUTED_METRICS_FILE = "computed_metrics.json"
COLLECTION_LOG_FILE = "collection_log.json"
INDEX_FILE = "index.json"


@dataclass
class StatsRecord:
    """A single data record with timestamp and source metadata."""
    timestamp: str
    source: str  # "github_api", "arc_api", "computed"
    data: dict = field(default_factory=dict)

    @classmethod
    def now(cls, source: str, data: dict) -> "StatsRecord":
        return cls(
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            source=source,
            data=data,
        )


class DailyStatsStore:
    """
    File-based JSON storage organized by date.

    Each day gets its own directory. Data is appended as new records
    within each file type. Files are created on first write.

    Usage:
        store = DailyStatsStore("/path/to/monitoring_data")
        store.append_workflow_runs([{...}, {...}])
        store.append_jobs([{...}])
        runs = store.get_workflow_runs()
        runs_for_date = store.get_workflow_runs(date="2026-03-11")
    """

    def __init__(self, base_dir: str = "monitoring_data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # --- Write operations ---

    def append_workflow_runs(self, runs: list[dict], collection_date: Optional[str] = None) -> int:
        """Append workflow run records for a given date. Returns count of records added."""
        return self._append_records(WORKFLOW_RUNS_FILE, "github_api", runs, collection_date)

    def append_jobs(self, jobs: list[dict], collection_date: Optional[str] = None) -> int:
        """Append job records for a given date. Returns count of records added."""
        return self._append_records(JOBS_FILE, "github_api", jobs, collection_date)

    def append_runner_status(self, snapshots: list[dict], collection_date: Optional[str] = None) -> int:
        """Append runner status snapshots for a given date. Returns count of records added."""
        return self._append_records(RUNNER_STATUS_FILE, "arc_api", snapshots, collection_date)

    def save_computed_metrics(self, metrics: dict, collection_date: Optional[str] = None) -> None:
        """Save computed metrics for a given date. Overwrites previous computation."""
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / COMPUTED_METRICS_FILE
        record = StatsRecord.now(source="computed", data=metrics)
        self._write_json(filepath, asdict(record))
        logger.info("Saved computed metrics to %s", filepath)

    def log_collection(self, entry: dict, collection_date: Optional[str] = None) -> None:
        """Append an entry to the collection log for a given date."""
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / COLLECTION_LOG_FILE
        existing = self._read_json(filepath, default=[])
        entry["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        existing.append(entry)
        self._write_json(filepath, existing)

    # --- Read operations ---

    def get_workflow_runs(self, collection_date: Optional[str] = None) -> list[dict]:
        """Get all workflow run records for a given date."""
        return self._read_records(WORKFLOW_RUNS_FILE, collection_date)

    def get_jobs(self, collection_date: Optional[str] = None) -> list[dict]:
        """Get all job records for a given date."""
        return self._read_records(JOBS_FILE, collection_date)

    def get_runner_status(self, collection_date: Optional[str] = None) -> list[dict]:
        """Get all runner status snapshots for a given date."""
        return self._read_records(RUNNER_STATUS_FILE, collection_date)

    def get_computed_metrics(self, collection_date: Optional[str] = None) -> Optional[dict]:
        """Get computed metrics for a given date."""
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / COMPUTED_METRICS_FILE
        if not filepath.exists():
            return None
        return self._read_json(filepath)

    def get_collection_log(self, collection_date: Optional[str] = None) -> list[dict]:
        """Get collection log entries for a given date."""
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / COLLECTION_LOG_FILE
        return self._read_json(filepath, default=[])

    def list_dates(self) -> list[str]:
        """List all dates that have collected data, sorted ascending."""
        dates = []
        for child in self.base_dir.iterdir():
            if child.is_dir() and self._is_date_dir(child.name):
                dates.append(child.name)
        return sorted(dates)

    def get_date_summary(self, collection_date: Optional[str] = None) -> dict:
        """Get a summary of data available for a given date."""
        day = collection_date or self._today()
        day_dir = self.base_dir / day
        if not day_dir.exists():
            return {"date": collection_date or self._today(), "exists": False}

        summary = {
            "date": collection_date or self._today(),
            "exists": True,
            "files": {},
        }
        for filename in [WORKFLOW_RUNS_FILE, JOBS_FILE, RUNNER_STATUS_FILE,
                         COMPUTED_METRICS_FILE, COLLECTION_LOG_FILE]:
            filepath = day_dir / filename
            if filepath.exists():
                data = self._read_json(filepath)
                count = len(data) if isinstance(data, list) else 1
                summary["files"][filename] = {
                    "record_count": count,
                    "size_bytes": filepath.stat().st_size,
                }
        return summary

    def get_index(self) -> dict:
        """Get or build the index of all collection dates with summaries."""
        index = {"last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "dates": {}}
        for d in self.list_dates():
            index["dates"][d] = self.get_date_summary(d)
        index_path = self.base_dir / INDEX_FILE
        self._write_json(index_path, index)
        return index

    # --- Cleanup ---

    def purge_before(self, cutoff_date: str) -> list[str]:
        """Remove daily directories older than cutoff_date. Returns list of removed dates."""
        import shutil
        removed = []
        for d in self.list_dates():
            if d < cutoff_date:
                shutil.rmtree(self.base_dir / d)
                removed.append(d)
                logger.info("Purged monitoring data for %s", d)
        return removed

    # --- Internal helpers ---

    def _today(self) -> str:
        return date.today().strftime("%Y-%m-%d")

    def _day_dir(self, collection_date: Optional[str] = None) -> Path:
        day = collection_date or self._today()
        day_dir = self.base_dir / day
        day_dir.mkdir(parents=True, exist_ok=True)
        return day_dir

    def _is_date_dir(self, name: str) -> bool:
        try:
            datetime.strptime(name, "%Y-%m-%d")
            return True
        except ValueError:
            return False

    def _append_records(self, filename: str, source: str, items: list[dict],
                        collection_date: Optional[str] = None) -> int:
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / filename
        existing = self._read_json(filepath, default=[])
        for item in items:
            record = StatsRecord.now(source=source, data=item)
            existing.append(asdict(record))
        self._write_json(filepath, existing)
        logger.info("Appended %d records to %s", len(items), filepath)
        return len(items)

    def _read_records(self, filename: str, collection_date: Optional[str] = None) -> list[dict]:
        day_dir = self._day_dir(collection_date)
        filepath = day_dir / filename
        return self._read_json(filepath, default=[])

    def _read_json(self, filepath: Path, default: Any = None) -> Any:
        if not filepath.exists():
            return default if default is not None else {}
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read %s: %s", filepath, e)
            return default if default is not None else {}

    def _write_json(self, filepath: Path, data: Any) -> None:
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except OSError as e:
            logger.error("Failed to write %s: %s", filepath, e)
            raise
