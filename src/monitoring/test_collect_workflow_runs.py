"""
Tests for Workflow Run Collector (Story 3)

Tests the collection pipeline: GitHub API → extract → deduplicate → storage.
Uses mocked GitHubClient to avoid real API calls.

Run: cd src/monitoring && python test_collect_workflow_runs.py
"""

import json
import shutil
import tempfile
import unittest
from datetime import date
from unittest.mock import patch, MagicMock

from .collect_workflow_runs import (
    extract_run_data,
    get_existing_run_ids,
    collect_workflow_runs,
    collect_org_workflow_runs,
)
from .github_client import GitHubAPIError
from .storage import DailyStatsStore


def make_fake_run(run_id=1001, name="CI Build", status="completed", conclusion="success",
                  branch="main", event="push", actor_login="dev1", repo_name="test-repo",
                  repo_full="Devopulence/test-repo"):
    """Build a fake GitHub API workflow run response."""
    return {
        "id": run_id,
        "name": name,
        "workflow_id": 12345,
        "status": status,
        "conclusion": conclusion,
        "event": event,
        "head_branch": branch,
        "head_sha": "abc123def456",
        "actor": {"login": actor_login, "id": 99},
        "created_at": "2026-03-16T10:00:00Z",
        "updated_at": "2026-03-16T10:05:00Z",
        "run_started_at": "2026-03-16T10:00:05Z",
        "run_attempt": 1,
        "run_number": 42,
        "html_url": f"https://github.com/{repo_full}/actions/runs/{run_id}",
        "repository": {"full_name": repo_full, "name": repo_name},
        # Extra fields that should NOT appear in extracted output
        "jobs_url": "https://api.github.com/...",
        "logs_url": "https://api.github.com/...",
        "check_suite_id": 999,
    }


class TestExtractRunData(unittest.TestCase):
    """Test the field extraction from raw GitHub API responses."""

    def test_extracts_core_fields(self):
        run = make_fake_run(run_id=2001, name="Deploy", status="completed",
                            conclusion="failure", branch="release/1.0")
        extracted = extract_run_data(run)

        self.assertEqual(extracted["id"], 2001)
        self.assertEqual(extracted["name"], "Deploy")
        self.assertEqual(extracted["status"], "completed")
        self.assertEqual(extracted["conclusion"], "failure")
        self.assertEqual(extracted["head_branch"], "release/1.0")
        self.assertEqual(extracted["event"], "push")
        self.assertEqual(extracted["run_attempt"], 1)
        self.assertEqual(extracted["run_number"], 42)

    def test_flattens_actor(self):
        run = make_fake_run(actor_login="johnd")
        extracted = extract_run_data(run)

        self.assertEqual(extracted["actor_login"], "johnd")
        self.assertEqual(extracted["actor_id"], 99)
        # Original nested actor should NOT be present
        self.assertNotIn("actor", extracted)

    def test_flattens_repository(self):
        run = make_fake_run(repo_full="MyOrg/my-app", repo_name="my-app")
        extracted = extract_run_data(run)

        self.assertEqual(extracted["repository_full_name"], "MyOrg/my-app")
        self.assertEqual(extracted["repository_name"], "my-app")
        self.assertNotIn("repository", extracted)

    def test_preserves_timestamps(self):
        run = make_fake_run()
        extracted = extract_run_data(run)

        self.assertEqual(extracted["created_at"], "2026-03-16T10:00:00Z")
        self.assertEqual(extracted["updated_at"], "2026-03-16T10:05:00Z")
        self.assertEqual(extracted["run_started_at"], "2026-03-16T10:00:05Z")

    def test_excludes_extra_fields(self):
        run = make_fake_run()
        extracted = extract_run_data(run)

        self.assertNotIn("jobs_url", extracted)
        self.assertNotIn("logs_url", extracted)
        self.assertNotIn("check_suite_id", extracted)

    def test_handles_missing_fields(self):
        run = {"id": 3001, "name": "Minimal"}
        extracted = extract_run_data(run)

        self.assertEqual(extracted["id"], 3001)
        self.assertEqual(extracted["name"], "Minimal")
        self.assertIsNone(extracted.get("status"))
        self.assertIsNone(extracted.get("conclusion"))


class TestGetExistingRunIds(unittest.TestCase):
    """Test deduplication ID extraction from storage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DailyStatsStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_store_returns_empty_set(self):
        ids = get_existing_run_ids(self.store, "2026-03-16")
        self.assertEqual(ids, set())

    def test_extracts_ids_from_stored_runs(self):
        self.store.append_workflow_runs(
            [{"id": 1001}, {"id": 1002}, {"id": 1003}],
            collection_date="2026-03-16",
        )
        ids = get_existing_run_ids(self.store, "2026-03-16")
        self.assertEqual(ids, {1001, 1002, 1003})


class TestCollectWorkflowRuns(unittest.TestCase):
    """Test the main collection pipeline with mocked GitHub API."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_basic_collection(self, MockClient):
        """Collect runs and verify they're stored correctly."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = [
            make_fake_run(run_id=1001),
            make_fake_run(run_id=1002),
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4998, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_fetched"], 2)
        self.assertEqual(summary["runs_new"], 2)
        self.assertEqual(summary["runs_skipped_duplicate"], 0)
        self.assertFalse(summary["errors"])

        # Verify storage
        store = DailyStatsStore(self.tmpdir)
        records = store.get_workflow_runs(collection_date="2026-03-16")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["data"]["id"], 1001)
        self.assertEqual(records[1]["data"]["id"], 1002)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_deduplication(self, MockClient):
        """Second collection skips already-stored runs."""
        store = DailyStatsStore(self.tmpdir)
        store.append_workflow_runs(
            [{"id": 1001, "name": "existing"}],
            collection_date="2026-03-16",
        )

        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = [
            make_fake_run(run_id=1001),  # Already exists
            make_fake_run(run_id=1002),  # New
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4998, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_fetched"], 2)
        self.assertEqual(summary["runs_new"], 1)
        self.assertEqual(summary["runs_skipped_duplicate"], 1)

        records = store.get_workflow_runs(collection_date="2026-03-16")
        # 1 original + 1 new
        self.assertEqual(len(records), 2)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_no_dedup_flag(self, MockClient):
        """With deduplicate=False, all runs are stored."""
        store = DailyStatsStore(self.tmpdir)
        store.append_workflow_runs(
            [{"id": 1001}],
            collection_date="2026-03-16",
        )

        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = [
            make_fake_run(run_id=1001),
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4998, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            deduplicate=False,
        )

        self.assertEqual(summary["runs_new"], 1)
        self.assertEqual(summary["runs_skipped_duplicate"], 0)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_filters_passed_to_client(self, MockClient):
        """Verify filters are forwarded to the GitHub client."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = []
        mock_instance.get_rate_limit_status.return_value = {"remaining": 5000, "limit": 5000}
        mock_instance.request_count = 0

        collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            status="completed",
            branch="main",
            event="push",
            created=">=2026-03-15",
            collection_date="2026-03-16",
        )

        mock_instance.list_workflow_runs.assert_called_once_with(
            max_pages=10,
            status="completed",
            branch="main",
            event="push",
            created=">=2026-03-15",
        )

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_workflow_specific_collection(self, MockClient):
        """Collect runs for a specific workflow file."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs_for_workflow.return_value = [
            make_fake_run(run_id=5001),
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            workflow_id="runner_test.yml",
            collection_date="2026-03-16",
        )

        mock_instance.list_workflow_runs_for_workflow.assert_called_once()
        self.assertEqual(summary["runs_new"], 1)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_api_error_handled(self, MockClient):
        """API errors are captured in summary, not raised."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.side_effect = GitHubAPIError(
            403, "Bad credentials"
        )

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="bad-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_fetched"], 0)
        self.assertTrue(len(summary["errors"]) > 0)
        self.assertIn("403", summary["errors"][0])

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_collection_logged(self, MockClient):
        """Verify collection metadata is logged to the store."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = [make_fake_run()]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        store = DailyStatsStore(self.tmpdir)
        log = store.get_collection_log(collection_date="2026-03-16")
        self.assertTrue(len(log) > 0)
        self.assertEqual(log[-1]["collector"], "collect_workflow_runs")
        self.assertIn("duration_seconds", log[-1]["summary"])

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_empty_result(self, MockClient):
        """No runs returned is handled gracefully."""
        mock_instance = MockClient.return_value
        mock_instance.list_workflow_runs.return_value = []
        mock_instance.get_rate_limit_status.return_value = {"remaining": 5000, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_workflow_runs(
            owner="Devopulence",
            repo="test-workflows",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_fetched"], 0)
        self.assertEqual(summary["runs_new"], 0)
        self.assertFalse(summary["errors"])


class TestCollectOrgWorkflowRuns(unittest.TestCase):
    """Test org-wide collection with mocked GitHub API."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_org_collection(self, MockClient):
        """Collect runs across org repos."""
        mock_instance = MockClient.return_value
        mock_instance.list_org_workflow_runs.return_value = [
            make_fake_run(run_id=1001, repo_full="Devopulence/repo-a", repo_name="repo-a"),
            make_fake_run(run_id=1002, repo_full="Devopulence/repo-b", repo_name="repo-b"),
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4990, "limit": 5000}
        mock_instance.request_count = 5

        summary = collect_org_workflow_runs(
            org="Devopulence",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_fetched"], 2)
        self.assertEqual(summary["runs_new"], 2)
        self.assertEqual(summary["repos_scanned"], 2)

    @patch("src.monitoring.collect_workflow_runs.GitHubClient")
    def test_org_api_error_handled(self, MockClient):
        """Org-level API errors captured in summary."""
        mock_instance = MockClient.return_value
        mock_instance.list_org_workflow_runs.side_effect = GitHubAPIError(
            404, "Not Found"
        )

        summary = collect_org_workflow_runs(
            org="NonExistent",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertTrue(len(summary["errors"]) > 0)


if __name__ == "__main__":
    unittest.main()