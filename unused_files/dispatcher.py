"""
GitHub Workflow Dispatcher with batch and async capabilities
Handles concurrent workflow dispatching with rate limiting and retry logic
"""

import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """Workflow execution status"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class WorkflowDispatchRequest:
    """Request to dispatch a workflow"""
    owner: str
    repo: str
    workflow_id: str
    ref: str = "main"
    inputs: Optional[Dict] = None
    test_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class WorkflowRun:
    """Workflow run information"""
    run_id: int
    test_id: str
    workflow_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    queue_time_seconds: Optional[float] = None
    execution_time_seconds: Optional[float] = None
    html_url: Optional[str] = None
    conclusion: Optional[str] = None


class RateLimiter:
    """GitHub API rate limiter"""

    def __init__(self, max_requests_per_second: int = 10):
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        async with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_request_time = time.time()


class GitHubWorkflowDispatcher:
    """Enhanced workflow dispatcher with batch and async capabilities"""

    def __init__(self, token: str, max_concurrent: int = 10, rate_limit_per_second: int = 10):
        self.token = token
        self.max_concurrent = max_concurrent
        self.rate_limiter = RateLimiter(rate_limit_per_second)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def __aenter__(self):
        """Context manager entry"""
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute total timeout
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=connector
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()

    async def dispatch_workflow(self, request: WorkflowDispatchRequest) -> Optional[int]:
        """
        Dispatch a single workflow
        Returns the run_id if successful, None otherwise
        """
        url = f"https://api.github.com/repos/{request.owner}/{request.repo}/actions/workflows/{request.workflow_id}/dispatches"

        payload = {"ref": request.ref}
        if request.inputs:
            # Add test_id to inputs if provided
            if request.test_id:
                request.inputs["test_id"] = request.test_id
            payload["inputs"] = request.inputs
        elif request.test_id:
            payload["inputs"] = {"test_id": request.test_id}

        async with self.semaphore:
            await self.rate_limiter.acquire()

            try:
                async with self.session.post(url, json=payload) as response:
                    if response.status == 204:
                        logger.info(f"✅ Dispatched workflow {request.workflow_id} for {request.owner}/{request.repo}")
                        # Get the run ID by polling recent runs
                        run_id = await self._get_recent_run_id(request)
                        return run_id
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Failed to dispatch workflow: {response.status} - {error_text}")
                        return None

            except asyncio.TimeoutError:
                logger.error(f"⏱️ Timeout dispatching workflow {request.workflow_id}")
                return None
            except Exception as e:
                logger.error(f"❌ Error dispatching workflow: {str(e)}")
                return None

    async def _get_recent_run_id(self, request: WorkflowDispatchRequest, max_attempts: int = 10) -> Optional[int]:
        """
        Poll for recently created workflow run
        GitHub doesn't return run_id immediately, so we need to poll
        """
        url = f"https://api.github.com/repos/{request.owner}/{request.repo}/actions/runs"

        for attempt in range(max_attempts):
            await asyncio.sleep(2)  # Wait before checking
            await self.rate_limiter.acquire()

            try:
                params = {
                    "per_page": 10,
                    "event": "workflow_dispatch"
                }

                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        runs = data.get("workflow_runs", [])

                        # Look for our test_id in recent runs
                        for run in runs:
                            # Check if this run was created recently (within last minute)
                            created_at = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                            time_diff = (datetime.now().astimezone() - created_at).total_seconds()

                            if time_diff < 60:  # Created within last minute
                                return run["id"]

            except Exception as e:
                logger.error(f"Error getting run ID: {str(e)}")

        return None

    async def dispatch_batch(self, requests: List[WorkflowDispatchRequest]) -> List[Tuple[WorkflowDispatchRequest, Optional[int]]]:
        """
        Dispatch multiple workflows concurrently
        Returns list of (request, run_id) tuples
        """
        logger.info(f"📦 Dispatching batch of {len(requests)} workflows")

        tasks = [self.dispatch_workflow(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dispatch_results = []
        for request, result in zip(requests, results):
            if isinstance(result, Exception):
                logger.error(f"Exception for {request.workflow_id}: {str(result)}")
                dispatch_results.append((request, None))
            else:
                dispatch_results.append((request, result))

        successful = sum(1 for _, run_id in dispatch_results if run_id is not None)
        logger.info(f"✅ Successfully dispatched {successful}/{len(requests)} workflows")

        return dispatch_results

    async def monitor_run(self, owner: str, repo: str, run_id: int, timeout_seconds: int = 3600) -> WorkflowRun:
        """
        Monitor a workflow run until completion or timeout
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning(f"⏱️ Monitoring timeout for run {run_id}")
                return WorkflowRun(
                    run_id=run_id,
                    test_id="",
                    workflow_id="",
                    status=WorkflowStatus.TIMED_OUT.value,
                    created_at=datetime.now(),
                )

            await self.rate_limiter.acquire()

            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()

                        status = data["status"]
                        conclusion = data.get("conclusion")

                        # Parse timestamps
                        created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
                        started_at = None
                        completed_at = None
                        queue_time = None
                        execution_time = None

                        if data.get("run_started_at"):
                            started_at = datetime.fromisoformat(data["run_started_at"].replace("Z", "+00:00"))
                            queue_time = (started_at - created_at).total_seconds()

                        if conclusion and data.get("updated_at"):
                            completed_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
                            if started_at:
                                execution_time = (completed_at - started_at).total_seconds()

                        workflow_run = WorkflowRun(
                            run_id=run_id,
                            test_id=data.get("name", ""),
                            workflow_id=data["path"].split("/")[-1] if "/" in data["path"] else data["path"],
                            status=status,
                            created_at=created_at,
                            started_at=started_at,
                            completed_at=completed_at,
                            queue_time_seconds=queue_time,
                            execution_time_seconds=execution_time,
                            html_url=data["html_url"],
                            conclusion=conclusion
                        )

                        if conclusion:  # Workflow completed
                            logger.info(f"✅ Run {run_id} completed with conclusion: {conclusion}")
                            return workflow_run

                        # Still running, wait before next poll
                        await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error monitoring run {run_id}: {str(e)}")
                await asyncio.sleep(10)

    async def monitor_batch(self, runs: List[Tuple[str, str, int]], timeout_seconds: int = 3600) -> List[WorkflowRun]:
        """
        Monitor multiple workflow runs concurrently
        runs: List of (owner, repo, run_id) tuples
        """
        logger.info(f"👀 Monitoring {len(runs)} workflow runs")

        tasks = [
            self.monitor_run(owner, repo, run_id, timeout_seconds)
            for owner, repo, run_id in runs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        workflow_runs = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Monitoring exception: {str(result)}")
            else:
                workflow_runs.append(result)

        return workflow_runs

    async def get_rate_limit(self) -> Dict:
        """Get current API rate limit status"""
        url = "https://api.github.com/rate_limit"

        await self.rate_limiter.acquire()

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    core = data["rate"]["core"]
                    logger.info(f"📊 API Rate Limit: {core['remaining']}/{core['limit']} "
                              f"(resets at {datetime.fromtimestamp(core['reset'])})")
                    return core
        except Exception as e:
            logger.error(f"Error getting rate limit: {str(e)}")

        return {}


async def example_batch_dispatch():
    """Example of batch workflow dispatching"""
    import os

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")

    # Create batch of workflow requests
    requests = [
        WorkflowDispatchRequest(
            owner="your-org",
            repo="test-workflows",
            workflow_id="simple_test.yml",
            ref="main",
            test_id=f"test_{i}",
            inputs={"complexity": "simple"}
        )
        for i in range(5)
    ]

    # Dispatch and monitor
    async with GitHubWorkflowDispatcher(token) as dispatcher:
        # Check rate limits
        await dispatcher.get_rate_limit()

        # Dispatch workflows
        dispatch_results = await dispatcher.dispatch_batch(requests)

        # Filter successful dispatches
        runs_to_monitor = [
            (req.owner, req.repo, run_id)
            for req, run_id in dispatch_results
            if run_id is not None
        ]

        # Monitor all runs
        if runs_to_monitor:
            workflow_runs = await dispatcher.monitor_batch(runs_to_monitor)

            # Print results
            for run in workflow_runs:
                print(f"Run {run.run_id}: {run.status} - "
                      f"Queue: {run.queue_time_seconds:.1f}s, "
                      f"Execution: {run.execution_time_seconds:.1f}s" if run.execution_time_seconds else "")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_batch_dispatch())