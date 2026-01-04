"""
Workflow Tracker Module
Tracks GitHub workflow runs and collects metrics using job_name input matching.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
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

    def set_test_run_id(self, test_run_id: str):
        """
        Set the test run ID used for job_name matching.

        Args:
            test_run_id: The unique identifier for this test run
        """
        self.test_run_id = test_run_id
        logger.info(f"Workflow tracker will match job_name={test_run_id}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self.headers)
        return self._session

    async def close(self):
        """Close the aiohttp session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def initialize_baseline(self):
        """
        Record the baseline state before test starts.
        Call this before dispatching any workflows.
        """
        self.test_start_time = datetime.now(timezone.utc)

        try:
            session = await self._get_session()
            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 1}

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    runs = data.get("workflow_runs", [])
                    if runs:
                        self.baseline_run_id = runs[0]["id"]
                        logger.info(f"Baseline established: run_id={self.baseline_run_id}, time={self.test_start_time}")
                    else:
                        self.baseline_run_id = 0
                        logger.info(f"No existing runs, baseline_run_id=0")
                else:
                    logger.error(f"Failed to get baseline: HTTP {resp.status}")
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
            session = await self._get_session()
            # The workflow run endpoint doesn't include inputs directly,
            # but we can get them from the jobs endpoint or by checking
            # the workflow_dispatch event payload

            # First try to get from the run details
            url = f"{self.base_url}/actions/runs/{run_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    run = await resp.json()
                    # For workflow_dispatch events, inputs might be in different places
                    # depending on GitHub API version

                    # Check if inputs are directly available (newer API)
                    if run.get("inputs"):
                        return run["inputs"]

                    # Try to get from the triggering actor's event
                    event = run.get("event")
                    if event == "workflow_dispatch":
                        # We need to check the workflow jobs for the job_name
                        # which might be in the job name or step outputs
                        pass

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
            session = await self._get_session()

            # Get the run details which may include inputs
            url = f"{self.base_url}/actions/runs/{run_id}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    run = await resp.json()

                    # Check for inputs in the run (available for workflow_dispatch)
                    inputs = run.get("inputs") or {}
                    if "job_name" in inputs:
                        return inputs["job_name"]

                    # Also check display_title which might contain our identifier
                    display_title = run.get("display_title", "")

                    # If we have a test_run_id, check if it's in the title
                    if self.test_run_id and self.test_run_id in display_title:
                        return self.test_run_id

            # If inputs not in run, try to get from the first job's name
            # Some workflows include the job_name in the job title
            url = f"{self.base_url}/actions/runs/{run_id}/jobs"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    jobs = data.get("jobs", [])

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
            session = await self._get_session()
            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 100}

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()

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
                    text = await resp.text()
                    logger.error(f"API error {resp.status}: {text[:200]}")

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
            session = await self._get_session()
            url = f"{self.base_url}/actions/runs"
            params = {"per_page": 100}

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()

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
                    text = await resp.text()
                    logger.error(f"API error {resp.status}: {text[:200]}")

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

            # Parse timestamps
            created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            workflow_data["queued_at"] = created_at

            if run.get("run_started_at"):
                started_at = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                workflow_data["started_at"] = started_at
                workflow_data["queue_time"] = (started_at - created_at).total_seconds()

            logger.info(f"Matched {tracking_id} -> run {run_id} (status: {run['status']})")

    async def update_workflow_status(self, tracking_id: str) -> Dict:
        """
        Update the status of a tracked workflow

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
            session = await self._get_session()
            url = f"{self.base_url}/actions/runs/{run_id}"

            async with session.get(url) as resp:
                if resp.status == 200:
                    run = await resp.json()

                    old_status = workflow_data.get("status")
                    new_status = run["status"]

                    workflow_data["github_run"] = run
                    workflow_data["status"] = new_status
                    workflow_data["conclusion"] = run.get("conclusion")

                    # Track state transitions
                    if run.get("run_started_at") and not workflow_data.get("started_at"):
                        # Job started
                        started_at = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                        workflow_data["started_at"] = started_at

                        if workflow_data.get("queued_at"):
                            workflow_data["queue_time"] = (started_at - workflow_data["queued_at"]).total_seconds()
                            logger.info(f"Workflow {run_id} started. Queue time: {workflow_data['queue_time']:.1f}s")

                    if new_status == "completed" and not workflow_data.get("completed_at"):
                        # Job completed
                        completed_at = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                        workflow_data["completed_at"] = completed_at

                        if workflow_data.get("started_at"):
                            workflow_data["execution_time"] = (completed_at - workflow_data["started_at"]).total_seconds()
                            logger.info(f"Workflow {run_id} completed ({run.get('conclusion')}). "
                                       f"Execution time: {workflow_data['execution_time']:.1f}s")
                else:
                    logger.warning(f"Failed to get run {run_id}: HTTP {resp.status}")

        except Exception as e:
            logger.error(f"Error updating workflow status: {e}")

        return workflow_data

    async def update_all_workflows(self) -> Dict:
        """
        Update status of all tracked workflows

        Returns:
            Summary of workflow states
        """
        # First, try to match any pending workflows using job_name
        await self.match_pending_workflows()

        # Then update status of all matched workflows
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

    async def get_active_jobs_count(self) -> int:
        """
        Get the count of currently running jobs

        Returns:
            Number of active jobs
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/actions/runs"
            params = {
                "status": "in_progress",
                "per_page": 100
            }

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return len(data.get("workflow_runs", []))

        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")

        return 0

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
