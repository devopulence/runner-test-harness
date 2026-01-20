"""
Workflow Tracker Module
Tracks GitHub workflow runs and collects metrics using job_name input matching.
"""

import asyncio
import logging
import ssl
import time
import certifi
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
import aiohttp

logger = logging.getLogger(__name__)


class WorkflowTracker:
    """
    Tracks GitHub workflow runs and their status.

    Uses job_name input matching for reliable correlation between
    dispatched workflows and GitHub runs - essential for shared environments
    where multiple users/processes may trigger workflows.
    """

    def __init__(self, github_token: str, owner: str, repo: str):
        """
        Initialize the workflow tracker

        Args:
            github_token: GitHub authentication token
            owner: Repository owner
            repo: Repository name
        """
        self.token = github_token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self.tracked_workflows: Dict[str, Dict] = {}  # tracking_id -> workflow_data
        self.matched_run_ids: Set[int] = set()  # Prevent double-matching
        self._session: Optional[aiohttp.ClientSession] = None

        # Track the baseline - runs that existed before our test started
        self.baseline_run_id: Optional[int] = None
        self.test_start_time: Optional[datetime] = None

        # Test run ID for job_name matching
        self.test_run_id: Optional[str] = None

        # Bulk mode for high-concurrency tests (reduces API calls for status updates)
        self.bulk_mode: bool = False

        # Cache for completed workflow run IDs (skip re-fetching)
        self.completed_cache: Set[int] = set()

        # Rate limit tracking
        self.rate_limit_remaining: int = 5000
        self.rate_limit_reset: int = 0

    def set_bulk_mode(self, enabled: bool) -> None:
        """
        Set bulk polling mode for high-concurrency tests.
        When enabled, uses optimized API calls to avoid rate limiting.

        Args:
            enabled: Whether to enable bulk mode
        """
        self.bulk_mode = enabled
        logger.info(f"Bulk polling mode: {'enabled' if enabled else 'disabled'}")

    def set_test_run_id(self, test_run_id: str):
        """
        Set the test run ID used for job_name matching.

        Args:
            test_run_id: The unique identifier for this test run
        """
        self.test_run_id = test_run_id
        logger.info(f"Workflow tracker will match job_name={test_run_id}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper SSL certificates"""
        if self._session is None or self._session.closed:
            import os
            # Check if SSL verification should be disabled (for corporate proxies)
            if os.environ.get('DISABLE_SSL_VERIFY', '').lower() in ('1', 'true', 'yes'):
                connector = aiohttp.TCPConnector(ssl=False)
            else:
                # Use exact same CA bundle as requests library
                try:
                    import requests.certs
                    ca_bundle = requests.certs.where()
                except ImportError:
                    ca_bundle = (
                        os.environ.get('REQUESTS_CA_BUNDLE') or
                        os.environ.get('SSL_CERT_FILE') or
                        os.environ.get('CURL_CA_BUNDLE') or
                        certifi.where()
                    )
                ssl_context = ssl.create_default_context(cafile=ca_bundle)
                connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(headers=self.headers, connector=connector)
        return self._session

    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _update_rate_limit(self, response: aiohttp.ClientResponse) -> None:
        """Update rate limit tracking from response headers"""
        try:
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
            self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
        except (ValueError, TypeError):
            pass

    async def _check_rate_limit(self) -> bool:
        """
        Check if rate limit is low and pause if needed.

        Returns:
            True if we had to wait, False otherwise
        """
        if self.rate_limit_remaining < 100:
            wait_seconds = max(self.rate_limit_reset - time.time(), 60)
            logger.warning(f"Rate limit low ({self.rate_limit_remaining} remaining), waiting {wait_seconds:.0f}s")
            await asyncio.sleep(min(wait_seconds, 120))  # Cap at 2 minutes
            return True
        return False

    async def _api_get_with_backoff(self, url: str, params: dict = None) -> Tuple[Optional[dict], int]:
        """
        Make GET API call with rate limit backoff handling.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Tuple of (response_data, status_code)
        """
        session = await self._get_session()

        for attempt in range(5):
            try:
                async with session.get(url, params=params) as resp:
                    self._update_rate_limit(resp)

                    if resp.status == 403:
                        # Rate limited - wait and retry
                        wait_seconds = max(self.rate_limit_reset - time.time(), 60)
                        logger.warning(f"Rate limited (403), waiting {wait_seconds:.0f}s (attempt {attempt + 1}/5)")
                        await asyncio.sleep(min(wait_seconds, 120))
                        continue

                    if resp.status == 200:
                        data = await resp.json()
                        return data, resp.status

                    # Other error
                    return None, resp.status

            except Exception as e:
                logger.error(f"API call error (attempt {attempt + 1}/5): {e}")
                await asyncio.sleep(5 * (attempt + 1))

        logger.error(f"Failed to complete API call after 5 attempts: {url}")
        return None, 0

    async def initialize_baseline(self):
        """
        Record the baseline state before test starts.
        Call this before dispatching any workflows.
        """
        self.test_start_time = datetime.now(timezone.utc)

        try:
            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 1}

            # Use backoff wrapper for rate limit handling
            data, status = await self._api_get_with_backoff(url, params)

            if data and status == 200:
                runs = data.get("workflow_runs", [])
                if runs:
                    self.baseline_run_id = runs[0]["id"]
                    logger.info(f"Baseline established: run_id={self.baseline_run_id}, time={self.test_start_time}")
                else:
                    self.baseline_run_id = 0
                    logger.info(f"No existing runs, baseline_run_id=0")
            else:
                logger.error(f"Failed to get baseline: HTTP {status}")
                self.baseline_run_id = 0
        except Exception as e:
            logger.error(f"Error getting baseline: {e}")
            self.baseline_run_id = 0

    async def get_run_inputs(self, run_id: int) -> Optional[Dict]:
        """
        Fetch the inputs for a specific workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            Dict of inputs or None if not available
        """
        try:
            # Use backoff wrapper for rate limit handling
            url = f"{self.base_url}/actions/runs/{run_id}"
            data, status = await self._api_get_with_backoff(url)

            if data and status == 200:
                # Check if inputs are directly available (newer API)
                if data.get("inputs"):
                    return data["inputs"]

        except Exception as e:
            logger.debug(f"Error getting run inputs for {run_id}: {e}")

        return None

    async def get_run_job_name(self, run_id: int) -> Optional[str]:
        """
        Get the job_name input value from a workflow run.

        This checks the run's jobs to find the job_name that was passed
        as an input to the workflow.

        Args:
            run_id: The workflow run ID

        Returns:
            The job_name value or None
        """
        try:
            # Get the run details which may include inputs (with rate limit handling)
            url = f"{self.base_url}/actions/runs/{run_id}"
            run_data, status = await self._api_get_with_backoff(url)

            if run_data and status == 200:
                # Check for inputs in the run (available for workflow_dispatch)
                inputs = run_data.get("inputs") or {}
                if "job_name" in inputs:
                    return inputs["job_name"]

                # Also check display_title which might contain our identifier
                display_title = run_data.get("display_title", "")

                # If we have a test_run_id, check if it's in the title
                if self.test_run_id and self.test_run_id in display_title:
                    return self.test_run_id

            # If inputs not in run, try to get from the first job's name
            # Some workflows include the job_name in the job title
            jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
            jobs_data, jobs_status = await self._api_get_with_backoff(jobs_url)

            if jobs_data and jobs_status == 200:
                jobs = jobs_data.get("jobs", [])

                for job in jobs:
                    job_name = job.get("name", "")
                    # Check if our test_run_id is in the job name
                    if self.test_run_id and self.test_run_id in job_name:
                        return self.test_run_id

                    # Look for patterns like "job_name: xxx" in steps
                    for step in job.get("steps", []):
                        step_name = step.get("name", "")
                        if self.test_run_id and self.test_run_id in step_name:
                            return self.test_run_id

        except Exception as e:
            logger.debug(f"Error getting job_name for run {run_id}: {e}")

        return None

    async def get_new_runs(self, workflow_file: str = None) -> List[Dict]:
        """
        Get all runs created after baseline that we haven't matched yet.

        Args:
            workflow_file: Optional filter by workflow file (e.g., "build_job")

        Returns:
            List of new, unmatched runs
        """
        new_runs = []

        try:
            # Check rate limit before API call
            await self._check_rate_limit()

            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 100}

            # Use backoff wrapper for rate limit handling
            data, status = await self._api_get_with_backoff(url, params)

            if data and status == 200:
                for run in data.get("workflow_runs", []):
                    run_id = run["id"]

                    # Skip if we've already matched this run
                    if run_id in self.matched_run_ids:
                        continue

                    # Skip if this run existed before our test
                    if self.baseline_run_id and run_id <= self.baseline_run_id:
                        continue

                    # Filter by workflow file if specified
                    if workflow_file:
                        run_path = run.get("path", "")
                        run_file = run_path.split("/")[-1].replace(".yml", "").replace(".yaml", "")
                        if run_file.lower() != workflow_file.lower():
                            continue

                    new_runs.append(run)

                logger.info(f"Found {len(new_runs)} new unmatched runs (baseline={self.baseline_run_id})")
            else:
                logger.error(f"API error getting runs: status={status}")

        except Exception as e:
            logger.error(f"Error getting new runs: {e}")

        return new_runs

    async def get_new_runs_with_inputs(self, workflow_file: str = None) -> List[Dict]:
        """
        Get all new runs with their inputs, for job_name matching.

        Args:
            workflow_file: Optional filter by workflow file (e.g., "build_job")

        Returns:
            List of runs with job_name data
        """
        new_runs = []

        try:
            # Use backoff wrapper for rate limit handling
            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 100}

            data, status = await self._api_get_with_backoff(url, params)

            if data and status == 200:
                for run in data.get("workflow_runs", []):
                    run_id = run["id"]

                    # Skip if we've already matched this run
                    if run_id in self.matched_run_ids:
                        continue

                    # Skip if this run existed before our test
                    if self.baseline_run_id and run_id <= self.baseline_run_id:
                        continue

                    # Filter by workflow file if specified
                    if workflow_file:
                        run_path = run.get("path", "")
                        run_file = run_path.split("/")[-1].replace(".yml", "").replace(".yaml", "")
                        if run_file.lower() != workflow_file.lower():
                            continue

                    # Get the job_name for this run
                    job_name = await self.get_run_job_name(run_id)
                    run["_job_name"] = job_name

                    new_runs.append(run)

                logger.debug(f"Found {len(new_runs)} new unmatched runs")
            else:
                logger.error(f"API error getting runs: status={status}")

        except Exception as e:
            logger.error(f"Error getting new runs: {e}")

        return new_runs

    async def track_workflow(self, workflow_name: str, dispatch_time: datetime) -> str:
        """
        Start tracking a workflow after dispatch

        Args:
            workflow_name: Name of the workflow (e.g., "build_job")
            dispatch_time: When the workflow was dispatched

        Returns:
            Tracking ID
        """
        tracking_id = f"{workflow_name}_{dispatch_time.timestamp()}"

        # Initialize baseline if not done
        if self.baseline_run_id is None:
            await self.initialize_baseline()

        # Store as pending - we'll match it during polling using job_name
        self.tracked_workflows[tracking_id] = {
            "run_id": None,
            "workflow_name": workflow_name,
            "dispatch_time": dispatch_time,
            "status": "pending",
            "conclusion": None,
            "queued_at": None,
            "started_at": None,
            "completed_at": None,
            "queue_time": None,
            "execution_time": None,
            "job_name": self.test_run_id  # Store expected job_name for matching
        }

        logger.info(f"Tracking workflow dispatch: {workflow_name} (job_name={self.test_run_id})")
        return tracking_id

    async def match_pending_workflows(self):
        """
        Match pending tracked workflows with actual GitHub runs.

        Uses baseline run_id to identify runs created during this test,
        then matches by run order (oldest pending -> oldest new run).
        """
        # Get pending workflows
        pending = [
            (tid, data) for tid, data in self.tracked_workflows.items()
            if data.get("run_id") is None
        ]

        if not pending:
            return

        # Get workflow file name from first pending (assuming all same type)
        workflow_name = pending[0][1]["workflow_name"]

        # Get new runs (run_id > baseline, not already matched)
        new_runs = await self.get_new_runs(workflow_name)

        # Sort by run_id (oldest first) to match in dispatch order
        matching_runs = sorted(new_runs, key=lambda r: r["id"])
        pending.sort(key=lambda x: x[1]["dispatch_time"])

        logger.info(f"Matching {len(pending)} pending workflows with {len(matching_runs)} new runs")

        # Match pending workflows with new runs in order
        for (tracking_id, workflow_data), run in zip(pending, matching_runs):
            run_id = run["id"]

            # Mark this run as matched
            self.matched_run_ids.add(run_id)

            # Update workflow data
            workflow_data["run_id"] = run_id
            workflow_data["github_run"] = run
            workflow_data["status"] = run["status"]
            workflow_data["conclusion"] = run.get("conclusion")

            # Note: Don't set queue_time here - run-level timestamps are inaccurate
            # Real queue time will be calculated from job-level data in update_workflow_status

            logger.info(f"Matched {tracking_id} -> run {run_id} (status: {run['status']})")

    async def update_workflow_status(self, tracking_id: str) -> Dict:
        """
        Update the status of a tracked workflow.

        Fetches job-level data for accurate queue time measurement.
        Queue time = job.started_at - job.created_at (time waiting for runner)

        Args:
            tracking_id: The tracking ID

        Returns:
            Updated workflow data
        """
        if tracking_id not in self.tracked_workflows:
            return {}

        workflow_data = self.tracked_workflows[tracking_id]

        # If we don't have a run_id, can't update
        if not workflow_data.get("run_id"):
            return workflow_data

        run_id = workflow_data["run_id"]

        try:
            # Get run status using backoff wrapper
            url = f"{self.base_url}/actions/runs/{run_id}"
            data, status = await self._api_get_with_backoff(url)

            if data and status == 200:
                workflow_data["github_run"] = data
                workflow_data["status"] = data["status"]
                workflow_data["conclusion"] = data.get("conclusion")
            else:
                logger.warning(f"Failed to get run {run_id}: HTTP {status}")
                return workflow_data

            # Only fetch job-level data when workflow is completed (saves API calls)
            if data["status"] == "completed" and workflow_data.get("queue_time") is None:
                jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
                jobs_data, jobs_status = await self._api_get_with_backoff(jobs_url)

                if jobs_data and jobs_status == 200:
                    jobs = jobs_data.get("jobs", [])

                    if jobs:
                        # Use the first/main job for timing
                        job = jobs[0]

                        # Queue time: job.created_at to job.started_at
                        if job.get("created_at") and job.get("started_at"):
                            job_created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                            job_started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                            workflow_data["queued_at"] = job_created
                            workflow_data["started_at"] = job_started
                            workflow_data["queue_time"] = (job_started - job_created).total_seconds()

                        # Execution time: job.started_at to job.completed_at
                        if job.get("started_at") and job.get("completed_at"):
                            job_started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                            job_completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                            workflow_data["completed_at"] = job_completed
                            workflow_data["execution_time"] = (job_completed - job_started).total_seconds()

                        logger.info(f"Workflow {run_id} completed: queue={workflow_data['queue_time']:.1f}s, "
                                   f"exec={workflow_data['execution_time']:.1f}s")

        except Exception as e:
            logger.error(f"Error updating workflow status: {e}")

        return workflow_data

    async def update_all_workflows(self) -> Dict:
        """
        Update status of all tracked workflows

        Behavior depends on bulk_mode:
        - bulk_mode=False: Per-workflow status updates (accurate, more API calls)
        - bulk_mode=True: Single list call, only individual fetches for completions

        Returns:
            Summary of workflow states
        """
        # First, try to match any pending workflows using job_name
        await self.match_pending_workflows()

        # Check rate limit before making API calls
        await self._check_rate_limit()

        if self.bulk_mode:
            # BULK MODE: Single API call to get all runs, update status from list data
            await self._bulk_update_workflow_status()
        else:
            # ACCURATE MODE: Per-workflow status updates (existing behavior)
            tasks = []
            for tracking_id in self.tracked_workflows:
                if self.tracked_workflows[tracking_id].get("run_id"):
                    tasks.append(self.update_workflow_status(tracking_id))

            if tasks:
                await asyncio.gather(*tasks)

        # Calculate summary
        summary = {
            "total": len(self.tracked_workflows),
            "pending": sum(1 for w in self.tracked_workflows.values() if w.get("run_id") is None),
            "queued": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "queued"),
            "in_progress": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "in_progress"),
            "completed": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "completed"),
            "successful": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "success"),
            "failed": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "failure"),
        }

        logger.info(f"Workflow status: {summary}")
        return summary

    async def _bulk_update_workflow_status(self) -> None:
        """
        Bulk update workflow status using a single API call.
        Only fetches individual job details for newly completed workflows.
        """
        # Build map of run_id -> tracking_id for quick lookup
        run_id_to_tracking: Dict[int, str] = {}
        for tracking_id, workflow in self.tracked_workflows.items():
            run_id = workflow.get("run_id")
            if run_id and run_id not in self.completed_cache:
                run_id_to_tracking[run_id] = tracking_id

        if not run_id_to_tracking:
            return

        # Single API call to get all recent runs
        runs_url = f"{self.base_url}/actions/runs"
        params = {"per_page": 100}

        data, status = await self._api_get_with_backoff(runs_url, params)
        if not data or status != 200:
            return

        runs = data.get("workflow_runs", [])

        # Update status from list data
        newly_completed = []
        for run in runs:
            run_id = run.get("id")
            if run_id in run_id_to_tracking:
                tracking_id = run_id_to_tracking[run_id]
                workflow_data = self.tracked_workflows[tracking_id]

                old_status = workflow_data.get("status")
                workflow_data["status"] = run["status"]
                workflow_data["conclusion"] = run.get("conclusion")

                # Track newly completed workflows for job detail fetch
                if run["status"] == "completed" and old_status != "completed":
                    newly_completed.append(tracking_id)

        # Fetch job details only for newly completed workflows (for timing data)
        for tracking_id in newly_completed:
            await self._fetch_completion_details(tracking_id)

    async def _fetch_completion_details(self, tracking_id: str) -> None:
        """
        Fetch job-level details for a completed workflow.
        Called only once per workflow when it completes.
        """
        workflow_data = self.tracked_workflows.get(tracking_id)
        if not workflow_data:
            return

        run_id = workflow_data.get("run_id")
        if not run_id or run_id in self.completed_cache:
            return

        jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
        data, status = await self._api_get_with_backoff(jobs_url)

        if data and status == 200:
            jobs = data.get("jobs", [])
            if jobs:
                job = jobs[0]

                # Queue time: job.created_at to job.started_at
                if job.get("created_at") and job.get("started_at"):
                    job_created = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                    job_started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                    workflow_data["queued_at"] = job_created
                    workflow_data["started_at"] = job_started
                    workflow_data["queue_time"] = (job_started - job_created).total_seconds()

                # Execution time: job.started_at to job.completed_at
                if job.get("started_at") and job.get("completed_at"):
                    job_started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                    job_completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                    workflow_data["completed_at"] = job_completed
                    workflow_data["execution_time"] = (job_completed - job_started).total_seconds()

                logger.info(f"Workflow {run_id} completed: queue={workflow_data.get('queue_time', 0):.1f}s, "
                           f"exec={workflow_data.get('execution_time', 0):.1f}s")

        # Add to cache to skip future fetches
        self.completed_cache.add(run_id)

    async def get_active_jobs_count(self) -> int:
        """
        Get the exact count of currently running JOBS.

        Queries our in-progress runs and counts jobs with status="in_progress".
        This reveals actual runner capacity through observation:
        - 1 runner can only run 1 job at a time
        - Max observed concurrent = actual runner count

        Called every ~30 seconds to sample concurrency.
        At test end, samples give: max, average, median concurrency.

        Returns:
            Exact number of jobs currently executing on runners
        """
        try:
            # Get list of in_progress runs (1 API call)
            runs_url = f"{self.base_url}/actions/runs"
            params = {"status": "in_progress", "per_page": 100}

            data, resp_status = await self._api_get_with_backoff(runs_url, params)
            if not data or resp_status != 200:
                return 0

            # Filter to only runs we're tracking
            tracked_run_ids = set(
                w.get("run_id") for w in self.tracked_workflows.values()
                if w.get("run_id")
            )

            in_progress_runs = [
                run for run in data.get("workflow_runs", [])
                if run.get("id") in tracked_run_ids
            ]

            if not in_progress_runs:
                return 0

            # Query jobs for each in-progress run, count running jobs
            total_active_jobs = 0

            for run in in_progress_runs:
                run_id = run["id"]
                jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
                jobs_data, jobs_status = await self._api_get_with_backoff(jobs_url)

                if jobs_data and jobs_status == 200:
                    for job in jobs_data.get("jobs", []):
                        if job.get("status") == "in_progress":
                            total_active_jobs += 1

            return total_active_jobs

        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")

        return 0

    async def get_full_snapshot(self) -> Dict[str, Any]:
        """
        Get a complete snapshot of all tracked workflow runs and their jobs.

        Captures everything GitHub returns - nothing is discarded.
        Used by SnapshotCollector to persist all poll data.

        Returns:
            Dict containing:
            - timestamp: When snapshot was taken
            - workflows: List of workflow runs with full job data
              - Each workflow includes: run_id, status, created_at, etc.
              - Each job includes: job_id, status, runner_name, runner_id, timestamps, etc.
        """
        from datetime import datetime, timezone

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workflows": []
        }

        try:
            # Get list of in_progress runs (1 API call)
            runs_url = f"{self.base_url}/actions/runs"
            params = {"status": "in_progress", "per_page": 100}

            data, resp_status = await self._api_get_with_backoff(runs_url, params)
            if not data or resp_status != 200:
                return snapshot

            # Filter to only runs we're tracking
            tracked_run_ids = set(
                w.get("run_id") for w in self.tracked_workflows.values()
                if w.get("run_id")
            )

            in_progress_runs = [
                run for run in data.get("workflow_runs", [])
                if run.get("id") in tracked_run_ids
            ]

            # Get full details for each workflow run
            for run in in_progress_runs:
                run_id = run["id"]

                workflow_data = {
                    "run_id": run_id,
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                    "created_at": run.get("created_at"),
                    "updated_at": run.get("updated_at"),
                    "run_started_at": run.get("run_started_at"),
                    "jobs": []
                }

                # Get all jobs for this run
                jobs_url = f"{self.base_url}/actions/runs/{run_id}/jobs"
                jobs_data, jobs_status = await self._api_get_with_backoff(jobs_url)

                if jobs_data and jobs_status == 200:
                    for job in jobs_data.get("jobs", []):
                        job_data = {
                            "job_id": job.get("id"),
                            "name": job.get("name"),
                            "status": job.get("status"),
                            "conclusion": job.get("conclusion"),
                            "created_at": job.get("created_at"),
                            "started_at": job.get("started_at"),
                            "completed_at": job.get("completed_at"),
                            "runner_id": job.get("runner_id"),
                            "runner_name": job.get("runner_name"),
                            "runner_group_id": job.get("runner_group_id"),
                            "runner_group_name": job.get("runner_group_name")
                        }
                        workflow_data["jobs"].append(job_data)

                snapshot["workflows"].append(workflow_data)

            return snapshot

        except Exception as e:
            logger.error(f"Error getting full snapshot: {e}")

        return snapshot

    def get_metrics(self) -> Dict:
        """
        Get aggregated metrics from tracked workflows

        Returns:
            Metrics dictionary
        """
        queue_times = []
        execution_times = []

        for workflow in self.tracked_workflows.values():
            if workflow.get("queue_time") is not None:
                queue_times.append(workflow["queue_time"])
            if workflow.get("execution_time") is not None:
                execution_times.append(workflow["execution_time"])

        return {
            "queue_times": queue_times,
            "execution_times": execution_times,
            "successful": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "success"),
            "failed": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "failure"),
            "pending": sum(1 for w in self.tracked_workflows.values() if w.get("run_id") is None),
            "matched": sum(1 for w in self.tracked_workflows.values() if w.get("run_id") is not None)
        }
