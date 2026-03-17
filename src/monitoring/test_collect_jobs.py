"""
Tests for Job-Level Data Collector (Task 4)

Tests the job collection pipeline: stored runs → GitHub API → extract → dedup → storage.
Uses mocked GitHubClient to avoid real API calls.

Run: python -m pytest src/monitoring/test_collect_jobs.py -v
"""

import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from .collect_jobs import (
    extract_job_data,
    get_existing_job_ids,
    collect_jobs,
    collect_org_jobs,
    _get_stored_run_ids_by_repo,
)
from .github_client import GitHubAPIError
from .storage import DailyStatsStore


def make_fake_job(job_id=5001, run_id=1001, name="Build", status="completed",
                  conclusion="success", runner_name="ecs-runner-abc",
                  runner_id=129, branch="main"):
    """Build a fake GitHub API job response."""
    return {
        "id": job_id,
        "run_id": run_id,
        "workflow_name": "CI Pipeline",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-03-16T10:00:00Z",
        "started_at": "2026-03-16T10:00:05Z",
        "completed_at": "2026-03-16T10:05:00Z",
        "head_branch": branch,
        "head_sha": "abc123",
        "run_attempt": 1,
        "html_url": f"https://github.com/devopulence/pythonProject/actions/runs/{run_id}/job/{job_id}",
        "labels": ["self-hosted", "linux"],
        "runner_id": runner_id,
        "runner_name": runner_name,
        "runner_group_id": 1,
        "runner_group_name": "Default",
        "steps": [
            {
                "name": "Set up job",
                "number": 1,
                "status": "completed",
                "conclusion": "success",
                "started_at": "2026-03-16T10:00:05Z",
                "completed_at": "2026-03-16T10:00:06Z",
            },
            {
                "name": "Build",
                "number": 2,
                "status": "completed",
                "conclusion": "success",
                "started_at": "2026-03-16T10:00:06Z",
                "completed_at": "2026-03-16T10:04:50Z",
            },
            {
                "name": "Complete job",
                "number": 3,
                "status": "completed",
                "conclusion": "success",
                "started_at": "2026-03-16T10:04:50Z",
                "completed_at": "2026-03-16T10:05:00Z",
            },
        ],
        # Extra fields that should NOT appear in extracted output
        "node_id": "CR_xxx",
        "run_url": "https://api.github.com/...",
        "url": "https://api.github.com/...",
        "check_run_url": "https://api.github.com/...",
    }


def _seed_workflow_runs(store, runs_data, collection_date="2026-03-16"):
    """Helper to seed workflow runs into storage for job collection to read."""
    store.append_workflow_runs(runs_data, collection_date=collection_date)


class TestExtractJobData(unittest.TestCase):
    """Test field extraction from raw GitHub job responses."""

    def test_extracts_core_fields(self):
        job = make_fake_job(job_id=6001, run_id=2001, name="Deploy",
                            conclusion="failure", runner_name="runner-xyz")
        extracted = extract_job_data(job)

        self.assertEqual(extracted["id"], 6001)
        self.assertEqual(extracted["run_id"], 2001)
        self.assertEqual(extracted["name"], "Deploy")
        self.assertEqual(extracted["conclusion"], "failure")
        self.assertEqual(extracted["runner_name"], "runner-xyz")
        self.assertEqual(extracted["runner_id"], 129)
        self.assertEqual(extracted["runner_group_name"], "Default")

    def test_extracts_timestamps(self):
        job = make_fake_job()
        extracted = extract_job_data(job)

        self.assertEqual(extracted["created_at"], "2026-03-16T10:00:00Z")
        self.assertEqual(extracted["started_at"], "2026-03-16T10:00:05Z")
        self.assertEqual(extracted["completed_at"], "2026-03-16T10:05:00Z")

    def test_extracts_labels(self):
        job = make_fake_job()
        extracted = extract_job_data(job)

        self.assertEqual(extracted["labels"], ["self-hosted", "linux"])

    def test_extracts_steps_with_essential_fields(self):
        job = make_fake_job()
        extracted = extract_job_data(job)

        self.assertEqual(len(extracted["steps"]), 3)
        step = extracted["steps"][1]
        self.assertEqual(step["name"], "Build")
        self.assertEqual(step["number"], 2)
        self.assertEqual(step["status"], "completed")
        self.assertEqual(step["conclusion"], "success")
        self.assertEqual(step["started_at"], "2026-03-16T10:00:06Z")
        self.assertEqual(step["completed_at"], "2026-03-16T10:04:50Z")

    def test_excludes_extra_fields(self):
        job = make_fake_job()
        extracted = extract_job_data(job)

        self.assertNotIn("node_id", extracted)
        self.assertNotIn("run_url", extracted)
        self.assertNotIn("url", extracted)
        self.assertNotIn("check_run_url", extracted)

    def test_handles_missing_steps(self):
        job = {"id": 7001, "run_id": 3001, "name": "Minimal"}
        extracted = extract_job_data(job)

        self.assertEqual(extracted["id"], 7001)
        self.assertIsNone(extracted.get("steps"))


class TestGetStoredRunIdsByRepo(unittest.TestCase):
    """Test reading stored runs grouped by repo."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DailyStatsStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_store(self):
        result = _get_stored_run_ids_by_repo(self.store, "2026-03-16")
        self.assertEqual(result, {})

    def test_groups_by_repo(self):
        _seed_workflow_runs(self.store, [
            {"id": 1001, "repository_full_name": "devopulence/pythonProject"},
            {"id": 1002, "repository_full_name": "devopulence/pythonProject"},
            {"id": 2001, "repository_full_name": "devopulence/actions"},
        ])

        result = _get_stored_run_ids_by_repo(self.store, "2026-03-16")
        self.assertEqual(set(result.keys()), {"devopulence/pythonProject", "devopulence/actions"})
        self.assertEqual(sorted(result["devopulence/pythonProject"]), [1001, 1002])
        self.assertEqual(result["devopulence/actions"], [2001])


class TestGetExistingJobIds(unittest.TestCase):
    """Test dedup ID extraction from storage."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DailyStatsStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_empty_store(self):
        ids = get_existing_job_ids(self.store, "2026-03-16")
        self.assertEqual(ids, set())

    def test_extracts_ids(self):
        self.store.append_jobs(
            [{"id": 5001}, {"id": 5002}],
            collection_date="2026-03-16",
        )
        ids = get_existing_job_ids(self.store, "2026-03-16")
        self.assertEqual(ids, {5001, 5002})


class TestCollectJobs(unittest.TestCase):
    """Test single-repo job collection with mocked API."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DailyStatsStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_basic_collection_with_run_ids(self, MockClient):
        """Collect jobs for explicit run IDs."""
        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.side_effect = [
            [make_fake_job(job_id=5001, run_id=1001), make_fake_job(job_id=5002, run_id=1001)],
            [make_fake_job(job_id=5003, run_id=1002)],
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4990, "limit": 5000}
        mock_instance.request_count = 2

        summary = collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001, 1002],
        )

        self.assertEqual(summary["runs_processed"], 2)
        self.assertEqual(summary["jobs_fetched"], 3)
        self.assertEqual(summary["jobs_new"], 3)
        self.assertFalse(summary["errors"])

        # Verify storage
        records = self.store.get_jobs(collection_date="2026-03-16")
        self.assertEqual(len(records), 3)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_reads_runs_from_storage(self, MockClient):
        """When no run_ids given, reads stored workflow runs."""
        _seed_workflow_runs(self.store, [
            {"id": 1001, "repository_full_name": "devopulence/pythonProject"},
        ])

        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.return_value = [
            make_fake_job(job_id=5001, run_id=1001),
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_processed"], 1)
        self.assertEqual(summary["jobs_new"], 1)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_deduplication(self, MockClient):
        """Second collection skips already-stored jobs."""
        self.store.append_jobs(
            [{"id": 5001}],
            collection_date="2026-03-16",
        )

        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.return_value = [
            make_fake_job(job_id=5001, run_id=1001),  # Already exists
            make_fake_job(job_id=5002, run_id=1001),  # New
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001],
        )

        self.assertEqual(summary["jobs_fetched"], 2)
        self.assertEqual(summary["jobs_new"], 1)
        self.assertEqual(summary["jobs_skipped_duplicate"], 1)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_max_runs_limit(self, MockClient):
        """max_runs limits how many runs are processed."""
        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.return_value = [make_fake_job()]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        summary = collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001, 1002, 1003, 1004, 1005],
            max_runs=2,
        )

        self.assertEqual(summary["runs_processed"], 2)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_404_run_skipped(self, MockClient):
        """Deleted runs (404) are skipped without failing the whole collection."""
        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.side_effect = [
            GitHubAPIError(404, "Not Found"),
            [make_fake_job(job_id=5001, run_id=1002)],
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4998, "limit": 5000}
        mock_instance.request_count = 2

        summary = collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001, 1002],
        )

        self.assertEqual(summary["runs_processed"], 1)
        self.assertEqual(summary["runs_with_errors"], 1)
        self.assertEqual(summary["jobs_new"], 1)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_no_stored_runs_returns_early(self, MockClient):
        """No stored runs for the repo returns summary with zeros."""
        summary = collect_jobs(
            owner="devopulence",
            repo="empty-repo",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["runs_processed"], 0)
        self.assertEqual(summary["jobs_fetched"], 0)
        MockClient.assert_not_called()

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_adds_repo_tag_to_jobs(self, MockClient):
        """Each job gets repository_full_name tagged for org-wide queries."""
        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.return_value = [make_fake_job(job_id=5001)]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001],
        )

        records = self.store.get_jobs(collection_date="2026-03-16")
        self.assertEqual(records[0]["data"]["repository_full_name"], "devopulence/pythonProject")

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_collection_logged(self, MockClient):
        """Collection metadata is logged to the store."""
        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.return_value = [make_fake_job()]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4999, "limit": 5000}
        mock_instance.request_count = 1

        collect_jobs(
            owner="devopulence",
            repo="pythonProject",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
            run_ids=[1001],
        )

        log = self.store.get_collection_log(collection_date="2026-03-16")
        self.assertTrue(len(log) > 0)
        self.assertEqual(log[-1]["collector"], "collect_jobs")


class TestCollectOrgJobs(unittest.TestCase):
    """Test org-wide job collection."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = DailyStatsStore(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_org_collection_across_repos(self, MockClient):
        """Collects jobs across multiple repos from stored runs."""
        _seed_workflow_runs(self.store, [
            {"id": 1001, "repository_full_name": "devopulence/pythonProject"},
            {"id": 2001, "repository_full_name": "devopulence/actions"},
        ])

        mock_instance = MockClient.return_value
        mock_instance.list_jobs_for_run.side_effect = [
            [make_fake_job(job_id=5001, run_id=1001)],
            [make_fake_job(job_id=6001, run_id=2001)],
        ]
        mock_instance.get_rate_limit_status.return_value = {"remaining": 4998, "limit": 5000}
        mock_instance.request_count = 2

        summary = collect_org_jobs(
            org="devopulence",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["repos_processed"], 2)
        self.assertEqual(summary["total_jobs_fetched"], 2)
        self.assertEqual(summary["total_jobs_new"], 2)
        self.assertIn("devopulence/pythonProject", summary["repo_summaries"])
        self.assertIn("devopulence/actions", summary["repo_summaries"])

    @patch("src.monitoring.collect_jobs.GitHubClient")
    def test_org_no_stored_runs(self, MockClient):
        """Org collection with no stored runs returns early."""
        summary = collect_org_jobs(
            org="devopulence",
            token="fake-token",
            store_dir=self.tmpdir,
            collection_date="2026-03-16",
        )

        self.assertEqual(summary["repos_processed"], 0)
        self.assertEqual(summary["total_jobs_fetched"], 0)
        MockClient.assert_not_called()


if __name__ == "__main__":
    unittest.main()
