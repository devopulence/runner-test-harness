"""Tests for the daily stats JSON storage structure (Story 1)."""

import json
import shutil
import tempfile
from pathlib import Path

from storage import DailyStatsStore


def test_basic_workflow():
    """End-to-end test: write and read workflow runs, jobs, runner status, and metrics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)
        test_date = "2026-03-11"

        # Append workflow runs
        runs = [
            {"id": 1001, "name": "CI Build", "status": "completed", "conclusion": "success"},
            {"id": 1002, "name": "CI Build", "status": "completed", "conclusion": "failure"},
        ]
        count = store.append_workflow_runs(runs, collection_date=test_date)
        assert count == 2

        # Append jobs
        jobs = [
            {"id": 5001, "run_id": 1001, "name": "build", "status": "completed",
             "runner_name": "runner-1", "started_at": "2026-03-11T10:00:00Z",
             "completed_at": "2026-03-11T10:05:00Z"},
        ]
        store.append_jobs(jobs, collection_date=test_date)

        # Append runner status
        runner_snapshots = [
            {"total": 4, "busy": 3, "idle": 1, "runners": [
                {"name": "runner-1", "busy": True},
                {"name": "runner-2", "busy": True},
                {"name": "runner-3", "busy": True},
                {"name": "runner-4", "busy": False},
            ]},
        ]
        store.append_runner_status(runner_snapshots, collection_date=test_date)

        # Save computed metrics
        metrics = {
            "success_rate": 0.50,
            "avg_queue_time_seconds": 45.2,
            "throughput_per_hour": 12.5,
            "p50_execution_time": 300,
            "p95_execution_time": 480,
        }
        store.save_computed_metrics(metrics, collection_date=test_date)

        # Log a collection event
        store.log_collection({"event": "hourly_collection", "records_collected": 3},
                             collection_date=test_date)

        # --- Read back and verify ---
        retrieved_runs = store.get_workflow_runs(collection_date=test_date)
        assert len(retrieved_runs) == 2
        assert retrieved_runs[0]["data"]["id"] == 1001
        assert retrieved_runs[1]["data"]["conclusion"] == "failure"

        retrieved_jobs = store.get_jobs(collection_date=test_date)
        assert len(retrieved_jobs) == 1
        assert retrieved_jobs[0]["data"]["runner_name"] == "runner-1"

        retrieved_runners = store.get_runner_status(collection_date=test_date)
        assert len(retrieved_runners) == 1
        assert retrieved_runners[0]["data"]["busy"] == 3

        retrieved_metrics = store.get_computed_metrics(collection_date=test_date)
        assert retrieved_metrics["data"]["success_rate"] == 0.50

        log = store.get_collection_log(collection_date=test_date)
        assert len(log) == 1
        assert log[0]["event"] == "hourly_collection"

        print("PASS: test_basic_workflow")


def test_append_accumulates():
    """Verify that multiple appends accumulate records in the same file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)
        test_date = "2026-03-10"

        store.append_workflow_runs([{"id": 1}], collection_date=test_date)
        store.append_workflow_runs([{"id": 2}, {"id": 3}], collection_date=test_date)

        runs = store.get_workflow_runs(collection_date=test_date)
        assert len(runs) == 3
        assert [r["data"]["id"] for r in runs] == [1, 2, 3]

        print("PASS: test_append_accumulates")


def test_list_dates_and_index():
    """Verify date listing and index generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)

        store.append_workflow_runs([{"id": 1}], collection_date="2026-03-09")
        store.append_workflow_runs([{"id": 2}], collection_date="2026-03-11")
        store.append_workflow_runs([{"id": 3}], collection_date="2026-03-10")

        dates = store.list_dates()
        assert dates == ["2026-03-09", "2026-03-10", "2026-03-11"]

        index = store.get_index()
        assert len(index["dates"]) == 3
        assert "2026-03-10" in index["dates"]

        print("PASS: test_list_dates_and_index")


def test_date_summary():
    """Verify date summary returns file info."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)
        test_date = "2026-03-11"

        store.append_workflow_runs([{"id": 1}, {"id": 2}], collection_date=test_date)
        store.append_jobs([{"id": 10}], collection_date=test_date)

        summary = store.get_date_summary(collection_date=test_date)
        assert summary["exists"] is True
        assert summary["files"]["workflow_runs.json"]["record_count"] == 2
        assert summary["files"]["jobs.json"]["record_count"] == 1

        # Non-existent date
        missing = store.get_date_summary(collection_date="2020-01-01")
        assert missing["exists"] is False

        print("PASS: test_date_summary")


def test_purge_before():
    """Verify old data can be purged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)

        store.append_workflow_runs([{"id": 1}], collection_date="2026-02-01")
        store.append_workflow_runs([{"id": 2}], collection_date="2026-02-15")
        store.append_workflow_runs([{"id": 3}], collection_date="2026-03-01")

        removed = store.purge_before("2026-03-01")
        assert sorted(removed) == ["2026-02-01", "2026-02-15"]
        assert store.list_dates() == ["2026-03-01"]

        print("PASS: test_purge_before")


def test_directory_structure():
    """Verify the on-disk directory structure matches the design."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)
        test_date = "2026-03-11"

        store.append_workflow_runs([{"id": 1}], collection_date=test_date)
        store.append_jobs([{"id": 10}], collection_date=test_date)
        store.append_runner_status([{"total": 4}], collection_date=test_date)
        store.save_computed_metrics({"success_rate": 1.0}, collection_date=test_date)
        store.log_collection({"event": "test"}, collection_date=test_date)

        base = Path(tmpdir)
        day_dir = base / test_date
        assert day_dir.exists()
        assert (day_dir / "workflow_runs.json").exists()
        assert (day_dir / "jobs.json").exists()
        assert (day_dir / "runner_status.json").exists()
        assert (day_dir / "computed_metrics.json").exists()
        assert (day_dir / "collection_log.json").exists()

        # Verify JSON is valid and pretty-printed
        with open(day_dir / "workflow_runs.json") as f:
            content = f.read()
            assert "\n" in content  # Pretty-printed
            data = json.loads(content)
            assert isinstance(data, list)

        print("PASS: test_directory_structure")


def test_empty_reads():
    """Verify reads on non-existent data return empty defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = DailyStatsStore(base_dir=tmpdir)

        assert store.get_workflow_runs(collection_date="2026-01-01") == []
        assert store.get_jobs(collection_date="2026-01-01") == []
        assert store.get_runner_status(collection_date="2026-01-01") == []
        assert store.get_computed_metrics(collection_date="2026-01-01") is None
        assert store.get_collection_log(collection_date="2026-01-01") == []

        print("PASS: test_empty_reads")


if __name__ == "__main__":
    test_basic_workflow()
    test_append_accumulates()
    test_list_dates_and_index()
    test_date_summary()
    test_purge_before()
    test_directory_structure()
    test_empty_reads()
    print("\nAll Story 1 tests passed!")