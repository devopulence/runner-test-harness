"""
Workflow Tracker Module
Tracks GitHub workflow runs and collects metrics
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import aiohttp
import time

logger = logging.getLogger(__name__)


class WorkflowTracker:
    """Tracks GitHub workflow runs and their status"""

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
        self.tracked_workflows = {}  # workflow_id -> workflow_data

    async def get_latest_workflow_run(self, workflow_name: str, after_timestamp: datetime) -> Optional[Dict]:
        """
        Get the latest workflow run after a given timestamp

        Args:
            workflow_name: Name of the workflow
            after_timestamp: Only return runs created after this time

        Returns:
            Workflow run data or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/actions/runs"
                params = {
                    "per_page": 10,
                    "status": "queued,in_progress,completed"
                }

                async with session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Find the run that matches our workflow and timestamp
                        for run in data.get("workflow_runs", []):
                            run_created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))

                            # Check if this run is after our dispatch and matches the workflow
                            if (run_created > after_timestamp and
                                workflow_name.lower() in run["name"].lower()):
                                return run

        except Exception as e:
            logger.error(f"Error getting workflow run: {e}")

        return None

    async def track_workflow(self, workflow_name: str, dispatch_time: datetime) -> str:
        """
        Start tracking a workflow after dispatch

        Args:
            workflow_name: Name of the workflow
            dispatch_time: When the workflow was dispatched

        Returns:
            Tracking ID
        """
        tracking_id = f"{workflow_name}_{dispatch_time.timestamp()}"

        # Wait a moment for the workflow to appear in GitHub
        await asyncio.sleep(2)

        # Try to find the workflow run
        run = await self.get_latest_workflow_run(workflow_name, dispatch_time)

        if run:
            self.tracked_workflows[tracking_id] = {
                "run_id": run["id"],
                "workflow_name": workflow_name,
                "dispatch_time": dispatch_time,
                "github_run": run,
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "queued_at": datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")),
                "started_at": None,
                "completed_at": None,
                "queue_time": None,
                "execution_time": None
            }
            logger.info(f"Tracking workflow run {run['id']} for {workflow_name}")
        else:
            # Store pending tracking
            self.tracked_workflows[tracking_id] = {
                "run_id": None,
                "workflow_name": workflow_name,
                "dispatch_time": dispatch_time,
                "status": "pending",
                "conclusion": None
            }
            logger.warning(f"Could not find workflow run for {workflow_name} yet")

        return tracking_id

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

        # If we don't have a run_id yet, try to find it
        if not workflow_data.get("run_id"):
            run = await self.get_latest_workflow_run(
                workflow_data["workflow_name"],
                workflow_data["dispatch_time"]
            )
            if run:
                workflow_data["run_id"] = run["id"]
                workflow_data["github_run"] = run
                workflow_data["queued_at"] = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))

        # If we have a run_id, get its current status
        if workflow_data.get("run_id"):
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/actions/runs/{workflow_data['run_id']}"

                    async with session.get(url, headers=self.headers) as resp:
                        if resp.status == 200:
                            run = await resp.json()

                            old_status = workflow_data.get("status")
                            new_status = run["status"]

                            workflow_data["github_run"] = run
                            workflow_data["status"] = new_status
                            workflow_data["conclusion"] = run.get("conclusion")

                            # Track state transitions
                            if old_status == "queued" and new_status == "in_progress":
                                # Job started
                                workflow_data["started_at"] = datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00"))
                                workflow_data["queue_time"] = (workflow_data["started_at"] - workflow_data["queued_at"]).total_seconds()
                                logger.info(f"Workflow {workflow_data['run_id']} started. Queue time: {workflow_data['queue_time']:.1f}s")

                            elif new_status == "completed":
                                # Job completed
                                if not workflow_data.get("completed_at"):
                                    workflow_data["completed_at"] = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))

                                    if workflow_data.get("started_at"):
                                        workflow_data["execution_time"] = (workflow_data["completed_at"] - workflow_data["started_at"]).total_seconds()
                                        logger.info(f"Workflow {workflow_data['run_id']} completed. Execution time: {workflow_data['execution_time']:.1f}s")

            except Exception as e:
                logger.error(f"Error updating workflow status: {e}")

        return workflow_data

    async def update_all_workflows(self) -> Dict:
        """
        Update status of all tracked workflows

        Returns:
            Summary of workflow states
        """
        tasks = []
        for tracking_id in self.tracked_workflows:
            tasks.append(self.update_workflow_status(tracking_id))

        if tasks:
            await asyncio.gather(*tasks)

        # Calculate summary
        summary = {
            "total": len(self.tracked_workflows),
            "queued": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "queued"),
            "in_progress": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "in_progress"),
            "completed": sum(1 for w in self.tracked_workflows.values() if w.get("status") == "completed"),
            "successful": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "success"),
            "failed": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "failure"),
        }

        return summary

    async def get_active_jobs_count(self) -> int:
        """
        Get the count of currently running jobs

        Returns:
            Number of active jobs
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/actions/runs"
                params = {
                    "status": "in_progress",
                    "per_page": 100
                }

                async with session.get(url, headers=self.headers, params=params) as resp:
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
            "failed": sum(1 for w in self.tracked_workflows.values() if w.get("conclusion") == "failure")
        }