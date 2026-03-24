"""
Tests for Scheduled Collection Script (Task 5)

Tests the combined pipeline: workflow runs + jobs in one pass.
Uses mocked collectors to avoid real API calls.

Run: python -m pytest src/monitoring/test_scheduled_collect.py -v
"""

import shutil
import tempfile
import unittest
from unittest.mock import patch

from .scheduled_collect import scheduled_collect
from .storage import DailyStatsStore


def make_runs_summary(fetched=100, new=80, dupes=20, errors=None):
    return {
        "runs_fetched": fetched,
        "runs_new": new,
        "runs_skipped_duplicate": dupes,
        "duration_seconds": 5.0,
        "errors": errors or [],
    }


def make_jobs_summary(fetched=200, new=150, dupes=50, errors=None):
    return {
        "total_jobs_fetched": fetched,
        "total_jobs_new": new,
        "total_jobs_skipped_duplicate": dupes,
        "duration_seconds": 10.0,
        "errors": errors or [],
    }


class TestScheduledCollect(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_org_full_pipeline(self, mock_runs, mock_jobs):
        """Full org pipeline runs both steps."""
        mock_runs.return_value = make_runs_summary()
        mock_jobs.return_value = make_jobs_summary()

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertTrue(summary["success"])
        self.assertEqual(summary["mode"], "org")
        self.assertEqual(summary["target"], "test-org")
        self.assertEqual(summary["steps"]["workflow_runs"]["runs_fetched"], 100)
        self.assertEqual(summary["steps"]["workflow_runs"]["runs_new"], 80)
        self.assertEqual(summary["steps"]["jobs"]["jobs_fetched"], 200)
        self.assertEqual(summary["steps"]["jobs"]["jobs_new"], 150)
        self.assertFalse(summary["errors"])
        mock_runs.assert_called_once()
        mock_jobs.assert_called_once()

    @patch("src.monitoring.scheduled_collect.collect_jobs")
    @patch("src.monitoring.scheduled_collect.collect_workflow_runs")
    def test_single_repo_pipeline(self, mock_runs, mock_jobs):
        """Single repo mode uses repo-specific collectors."""
        mock_runs.return_value = make_runs_summary(fetched=50, new=50, dupes=0)
        mock_jobs.return_value = {"jobs_fetched": 80, "jobs_new": 80, "jobs_skipped_duplicate": 0, "duration_seconds": 3.0, "errors": []}

        summary = scheduled_collect(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertTrue(summary["success"])
        self.assertEqual(summary["mode"], "repo")
        self.assertEqual(summary["target"], "devopulence/pythonProject")
        mock_runs.assert_called_once()
        mock_jobs.assert_called_once()

    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_skip_jobs(self, mock_runs):
        """skip_jobs=True only collects workflow runs."""
        mock_runs.return_value = make_runs_summary()

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
            skip_jobs=True,
        )

        self.assertTrue(summary["success"])
        self.assertIn("workflow_runs", summary["steps"])
        self.assertNotIn("jobs", summary["steps"])

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_runs_error_continues_to_jobs(self, mock_runs, mock_jobs):
        """If workflow run collection fails, job collection still runs."""
        mock_runs.side_effect = Exception("API down")
        mock_jobs.return_value = make_jobs_summary()

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertFalse(summary["success"])
        self.assertTrue(len(summary["errors"]) > 0)
        # Jobs still ran
        mock_jobs.assert_called_once()

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_jobs_error_captured(self, mock_runs, mock_jobs):
        """Job collection error is captured in summary."""
        mock_runs.return_value = make_runs_summary()
        mock_jobs.side_effect = Exception("Timeout")

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertFalse(summary["success"])
        self.assertIn("Jobs: Timeout", summary["errors"][0])

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_collection_logged_to_store(self, mock_runs, mock_jobs):
        """Collection summary is logged to the store."""
        mock_runs.return_value = make_runs_summary()
        mock_jobs.return_value = make_jobs_summary()

        scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        store = DailyStatsStore(self.tmpdir)
        log = store.get_collection_log(collection_date="2026-03-24")
        scheduled_entries = [e for e in log if e.get("collector") == "scheduled_collect"]
        self.assertTrue(len(scheduled_entries) > 0)

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_has_duration(self, mock_runs, mock_jobs):
        """Summary includes total duration."""
        mock_runs.return_value = make_runs_summary()
        mock_jobs.return_value = make_jobs_summary()

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertIn("total_duration_seconds", summary)
        self.assertGreaterEqual(summary["total_duration_seconds"], 0)

    @patch("src.monitoring.scheduled_collect.collect_org_jobs")
    @patch("src.monitoring.scheduled_collect.collect_org_workflow_runs")
    def test_partial_errors_in_steps(self, mock_runs, mock_jobs):
        """Non-fatal errors from collectors are captured."""
        mock_runs.return_value = make_runs_summary(errors=["Rate limit warning"])
        mock_jobs.return_value = make_jobs_summary()

        summary = scheduled_collect(
            org="test-org",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-24",
        )

        self.assertTrue(summary["success"])
        self.assertIn("Rate limit warning", summary["errors"])


if __name__ == "__main__":
    unittest.main()
