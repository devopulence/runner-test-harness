"""
Post-Hoc Analysis Module
Analyzes workflow runs after test completion to get accurate metrics
without rate limiting concerns during the test.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import aiohttp
import ssl
import certifi

logger = logging.getLogger(__name__)


@dataclass
class JobMetrics:
    """Metrics for a single job"""
    job_id: int
    job_name: str
    run_id: int
    workflow_name: str
    status: str
    conclusion: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    queue_time: Optional[float]  # seconds
    execution_time: Optional[float]  # seconds
    total_time: Optional[float]  # seconds
    runner_id: Optional[int]
    runner_name: Optional[str]


@dataclass
class ConcurrencyPoint:
    """A point in time where concurrency changed"""
    timestamp: datetime
    concurrent_jobs: int
    event: str  # "start" or "end"
    job_id: int


@dataclass
class PostHocAnalysis:
    """Complete post-hoc analysis results"""
    test_run_id: str
    total_runs: int
    total_jobs: int
    successful_jobs: int
    failed_jobs: int

    # Timing metrics
    queue_times: List[float] = field(default_factory=list)
    execution_times: List[float] = field(default_factory=list)
    total_times: List[float] = field(default_factory=list)

    # Concurrency metrics (primary - may be from snapshots or timestamps)
    max_concurrent_jobs: int = 0
    concurrency_timeline: List[ConcurrencyPoint] = field(default_factory=list)
    avg_concurrent_jobs: float = 0.0

    # Timestamp-based concurrency (always calculated from job start/end times)
    # This is the TRUE overlap based on actual job execution windows
    timestamp_max_concurrent: int = 0
    timestamp_avg_concurrent: float = 0.0

    # Runner metrics
    runners_used: Dict[str, int] = field(default_factory=dict)  # runner_name -> job_count
    runner_busy_time: Dict[str, float] = field(default_factory=dict)  # runner_name -> seconds

    # Raw data
    jobs: List[JobMetrics] = field(default_factory=list)

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate summary statistics"""
        import statistics

        stats = {
            "test_run_id": self.test_run_id,
            "total_runs": self.total_runs,
            "total_jobs": self.total_jobs,
            "successful_jobs": self.successful_jobs,
            "failed_jobs": self.failed_jobs,
            "success_rate": self.successful_jobs / self.total_jobs if self.total_jobs > 0 else 0,
        }

        # Queue time stats
        if self.queue_times:
            stats["queue_time"] = {
                "min": min(self.queue_times),
                "max": max(self.queue_times),
                "mean": statistics.mean(self.queue_times),
                "median": statistics.median(self.queue_times),
                "p95": sorted(self.queue_times)[int(len(self.queue_times) * 0.95)] if len(self.queue_times) > 1 else self.queue_times[0],
                "stdev": statistics.stdev(self.queue_times) if len(self.queue_times) > 1 else 0
            }

        # Execution time stats
        if self.execution_times:
            stats["execution_time"] = {
                "min": min(self.execution_times),
                "max": max(self.execution_times),
                "mean": statistics.mean(self.execution_times),
                "median": statistics.median(self.execution_times),
                "p95": sorted(self.execution_times)[int(len(self.execution_times) * 0.95)] if len(self.execution_times) > 1 else self.execution_times[0],
                "stdev": statistics.stdev(self.execution_times) if len(self.execution_times) > 1 else 0
            }

        # Concurrency stats
        stats["concurrency"] = {
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "avg_concurrent_jobs": self.avg_concurrent_jobs,
        }

        # Runner stats
        stats["runners"] = {
            "unique_runners_used": len(self.runners_used),
            "runners": self.runners_used,
            "runner_busy_time": self.runner_busy_time
        }

        return stats


class PostHocAnalyzer:
    """
    Analyzes workflow runs after test completion.

    Queries GitHub API for all runs matching the test's job_name,
    collects job-level details, and calculates accurate metrics
    from timestamps.
    """

    def __init__(self, github_token: str, owner: str, repo: str):
        self.token = github_token
        self.owner = owner
        self.repo = repo
        self.headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = f"https://api.github.com/repos/{owner}/{repo}"
        self._session: Optional[aiohttp.ClientSession] = None

        # Rate limit tracking
        self.rate_limit_remaining: int = 5000
        self.rate_limit_reset: int = 0
        self.api_calls_made: int = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            import os
            if os.environ.get('DISABLE_SSL_VERIFY', '').lower() in ('1', 'true', 'yes'):
                connector = aiohttp.TCPConnector(ssl=False)
            else:
                try:
                    import requests.certs
                    ca_bundle = requests.certs.where()
                except ImportError:
                    ca_bundle = certifi.where()
                ssl_context = ssl.create_default_context(cafile=ca_bundle)
                connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(headers=self.headers, connector=connector)
        return self._session

    async def close(self):
        """Close the session"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _api_get_with_backoff(self, url: str, params: dict = None) -> Tuple[Optional[dict], int]:
        """Make GET request with rate limit handling"""
        session = await self._get_session()

        for attempt in range(5):
            try:
                # Check rate limit before calling
                if self.rate_limit_remaining < 50:
                    wait_seconds = max(self.rate_limit_reset - time.time(), 30)
                    logger.info(f"Rate limit low ({self.rate_limit_remaining}), waiting {wait_seconds:.0f}s...")
                    await asyncio.sleep(min(wait_seconds, 120))

                async with session.get(url, params=params) as resp:
                    # Update rate limit tracking
                    self.rate_limit_remaining = int(resp.headers.get('X-RateLimit-Remaining', 5000))
                    self.rate_limit_reset = int(resp.headers.get('X-RateLimit-Reset', 0))
                    self.api_calls_made += 1

                    if resp.status == 403:
                        wait_seconds = max(self.rate_limit_reset - time.time(), 60)
                        logger.warning(f"Rate limited (403), waiting {wait_seconds:.0f}s (attempt {attempt + 1}/5)")
                        await asyncio.sleep(min(wait_seconds, 120))
                        continue

                    if resp.status == 200:
                        return await resp.json(), 200

                    logger.warning(f"API returned {resp.status} for {url}")
                    return None, resp.status

            except Exception as e:
                logger.error(f"API error (attempt {attempt + 1}/5): {e}")
                await asyncio.sleep(5 * (attempt + 1))

        return None, 0

    async def get_runs_by_job_name(self, job_name: str, created_after: datetime = None) -> List[Dict]:
        """
        Get all workflow runs that have the specified job_name input.

        Args:
            job_name: The unique test run identifier
            created_after: Only get runs created after this time

        Returns:
            List of matching workflow runs
        """
        matching_runs = []
        page = 1
        per_page = 100

        logger.info(f"Searching for runs with job_name: {job_name}")

        while True:
            url = f"{self.base_url}/actions/runs"
            params = {
                "per_page": per_page,
                "page": page,
                "event": "workflow_dispatch"  # Only workflow_dispatch has inputs
            }

            if created_after:
                params["created"] = f">={created_after.strftime('%Y-%m-%dT%H:%M:%SZ')}"

            data, status = await self._api_get_with_backoff(url, params)

            if not data or status != 200:
                break

            runs = data.get("workflow_runs", [])

            if not runs:
                break

            # Filter runs that match our job_name
            for run in runs:
                inputs = run.get("inputs") or {}
                if inputs.get("job_name") == job_name:
                    matching_runs.append(run)

            # Check if we need to continue pagination
            if len(runs) < per_page:
                break

            page += 1

            # Safety limit
            if page > 20:
                logger.warning("Reached pagination limit (2000 runs)")
                break

        logger.info(f"Found {len(matching_runs)} runs matching job_name: {job_name}")
        return matching_runs

    async def get_jobs_for_run(self, run_id: int) -> List[Dict]:
        """Get all jobs for a workflow run"""
        jobs = []
        page = 1

        while True:
            url = f"{self.base_url}/actions/runs/{run_id}/jobs"
            params = {"per_page": 100, "page": page}

            data, status = await self._api_get_with_backoff(url, params)

            if not data or status != 200:
                break

            page_jobs = data.get("jobs", [])
            jobs.extend(page_jobs)

            if len(page_jobs) < 100:
                break

            page += 1

        return jobs

    async def analyze(self, job_name: str, created_after: datetime = None,
                     delay_between_calls: float = 0.1,
                     run_ids: List[int] = None,
                     snapshot_concurrency: Dict[str, Any] = None) -> PostHocAnalysis:
        """
        Perform complete post-hoc analysis of a test run.

        Args:
            job_name: The unique test run identifier (test_run_id)
            created_after: Only analyze runs created after this time
            delay_between_calls: Delay between API calls to avoid rate limits
            run_ids: Optional list of run IDs to analyze directly (skips search)
            snapshot_concurrency: Optional dict with accurate concurrency from snapshots:
                - max_concurrent_jobs: int
                - avg_concurrent_jobs: float
                - max_concurrent_runners: int
                If provided, these values are used instead of timestamp inference.

        Returns:
            PostHocAnalysis with all metrics
        """
        logger.info(f"Starting post-hoc analysis for: {job_name}")

        # If run_ids provided, use them directly (more efficient)
        if run_ids:
            logger.info(f"Using {len(run_ids)} pre-tracked run IDs")
            runs = [{"id": run_id} for run_id in run_ids]
        else:
            # Fall back to searching by job_name
            runs = await self.get_runs_by_job_name(job_name, created_after)

        if not runs:
            logger.warning(f"No runs found for job_name: {job_name}")
            return PostHocAnalysis(
                test_run_id=job_name,
                total_runs=0,
                total_jobs=0,
                successful_jobs=0,
                failed_jobs=0
            )

        # Collect all jobs from all runs
        all_jobs: List[JobMetrics] = []

        for i, run in enumerate(runs):
            run_id = run["id"]
            workflow_name = run.get("name", "unknown")

            logger.info(f"Fetching jobs for run {i+1}/{len(runs)}: {run_id}")

            jobs = await self.get_jobs_for_run(run_id)

            for job in jobs:
                # Parse timestamps
                created_at = datetime.fromisoformat(job["created_at"].replace("Z", "+00:00"))
                started_at = None
                completed_at = None
                queue_time = None
                execution_time = None
                total_time = None

                if job.get("started_at"):
                    started_at = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                    queue_time = (started_at - created_at).total_seconds()

                if job.get("completed_at"):
                    completed_at = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                    if started_at:
                        execution_time = (completed_at - started_at).total_seconds()
                    total_time = (completed_at - created_at).total_seconds()

                job_metrics = JobMetrics(
                    job_id=job["id"],
                    job_name=job["name"],
                    run_id=run_id,
                    workflow_name=workflow_name,
                    status=job["status"],
                    conclusion=job.get("conclusion"),
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    queue_time=queue_time,
                    execution_time=execution_time,
                    total_time=total_time,
                    runner_id=job.get("runner_id"),
                    runner_name=job.get("runner_name")
                )
                all_jobs.append(job_metrics)

            # Small delay to be nice to the API
            if delay_between_calls > 0:
                await asyncio.sleep(delay_between_calls)

        # Calculate metrics
        analysis = self._calculate_metrics(job_name, runs, all_jobs, snapshot_concurrency)

        logger.info(f"Post-hoc analysis complete. API calls made: {self.api_calls_made}")

        return analysis

    def _calculate_metrics(self, job_name: str, runs: List[Dict],
                          jobs: List[JobMetrics],
                          snapshot_concurrency: Dict[str, Any] = None) -> PostHocAnalysis:
        """
        Calculate all metrics from collected job data.

        Args:
            job_name: Test run identifier
            runs: List of workflow runs
            jobs: List of job metrics
            snapshot_concurrency: If provided, use these values as primary concurrency metrics
        """

        # Basic counts
        successful = sum(1 for j in jobs if j.conclusion == "success")
        failed = sum(1 for j in jobs if j.conclusion == "failure")

        # Timing lists
        queue_times = [j.queue_time for j in jobs if j.queue_time is not None]
        execution_times = [j.execution_time for j in jobs if j.execution_time is not None]
        total_times = [j.total_time for j in jobs if j.total_time is not None]

        # Runner stats from completed jobs
        runners_used: Dict[str, int] = {}
        runner_busy_time: Dict[str, float] = {}

        for job in jobs:
            if job.runner_name:
                runners_used[job.runner_name] = runners_used.get(job.runner_name, 0) + 1
                if job.execution_time:
                    runner_busy_time[job.runner_name] = runner_busy_time.get(job.runner_name, 0) + job.execution_time

        # ALWAYS calculate timestamp-based concurrency from actual job start/end times
        # This is the TRUE overlap based on when jobs were actually running
        ts_max_concurrent, ts_avg_concurrent, timeline = self._calculate_concurrency(jobs)
        logger.info(f"TIMESTAMP-BASED concurrency (from job start/end times): max={ts_max_concurrent}, avg={ts_avg_concurrent:.1f}")

        # Primary concurrency metrics - use snapshot data if available, otherwise timestamp
        if snapshot_concurrency:
            max_concurrent = snapshot_concurrency.get("max_concurrent_jobs", 0)
            avg_concurrent = snapshot_concurrency.get("avg_concurrent_jobs", 0.0)
            logger.info(f"SNAPSHOT-BASED concurrency (from polling samples): max={max_concurrent}, avg={avg_concurrent:.1f}")
        else:
            max_concurrent = ts_max_concurrent
            avg_concurrent = ts_avg_concurrent

        return PostHocAnalysis(
            test_run_id=job_name,
            total_runs=len(runs),
            total_jobs=len(jobs),
            successful_jobs=successful,
            failed_jobs=failed,
            queue_times=queue_times,
            execution_times=execution_times,
            total_times=total_times,
            max_concurrent_jobs=max_concurrent,
            avg_concurrent_jobs=avg_concurrent,
            concurrency_timeline=timeline,
            timestamp_max_concurrent=ts_max_concurrent,
            timestamp_avg_concurrent=ts_avg_concurrent,
            runners_used=runners_used,
            runner_busy_time=runner_busy_time,
            jobs=jobs
        )

    def _calculate_concurrency(self, jobs: List[JobMetrics]) -> Tuple[int, float, List[ConcurrencyPoint]]:
        """
        Calculate max and average concurrency from job time ranges.

        Uses an event-based approach: create events for each job start/end,
        sort by time, and track concurrent count as we process events.
        """
        events: List[Tuple[datetime, str, int]] = []  # (timestamp, event_type, job_id)

        for job in jobs:
            if job.started_at and job.completed_at:
                events.append((job.started_at, "start", job.job_id))
                events.append((job.completed_at, "end", job.job_id))

        if not events:
            return 0, 0.0, []

        # Sort by timestamp (ends before starts at same time to handle instant jobs)
        events.sort(key=lambda x: (x[0], 0 if x[1] == "end" else 1))

        timeline: List[ConcurrencyPoint] = []
        current_concurrent = 0
        max_concurrent = 0

        # For calculating weighted average
        total_job_seconds = 0.0
        concurrency_sum = 0.0

        prev_time = events[0][0]

        for timestamp, event_type, job_id in events:
            # Add time-weighted concurrency
            if current_concurrent > 0:
                duration = (timestamp - prev_time).total_seconds()
                concurrency_sum += current_concurrent * duration
                total_job_seconds += duration

            # Update concurrent count
            if event_type == "start":
                current_concurrent += 1
            else:
                current_concurrent -= 1

            max_concurrent = max(max_concurrent, current_concurrent)

            timeline.append(ConcurrencyPoint(
                timestamp=timestamp,
                concurrent_jobs=current_concurrent,
                event=event_type,
                job_id=job_id
            ))

            prev_time = timestamp

        avg_concurrent = concurrency_sum / total_job_seconds if total_job_seconds > 0 else 0

        return max_concurrent, avg_concurrent, timeline

    def get_concurrency_timeline_display(self, jobs: List[JobMetrics], interval_seconds: int = 30) -> List[Dict]:
        """
        Generate a human-readable concurrency timeline at regular intervals.

        Args:
            jobs: List of job metrics with started_at and completed_at
            interval_seconds: Time interval for each bucket (default 30 seconds)

        Returns:
            List of dicts with time offset and concurrent count
        """
        # Filter jobs with valid timestamps
        valid_jobs = [j for j in jobs if j.started_at and j.completed_at]

        if not valid_jobs:
            return []

        # Find time range
        min_time = min(j.started_at for j in valid_jobs)
        max_time = max(j.completed_at for j in valid_jobs)

        timeline = []
        current_time = min_time

        while current_time <= max_time:
            # Count jobs running at this moment
            # A job is running if: started_at <= current_time < completed_at
            concurrent = sum(
                1 for j in valid_jobs
                if j.started_at <= current_time < j.completed_at
            )

            # Calculate offset from start in minutes
            offset_seconds = (current_time - min_time).total_seconds()
            offset_minutes = offset_seconds / 60

            timeline.append({
                "time": current_time.strftime("%H:%M:%S"),
                "offset_min": round(offset_minutes, 1),
                "concurrent": concurrent
            })

            current_time = current_time + timedelta(seconds=interval_seconds)

        return timeline

    def print_concurrency_timeline(self, jobs: List[JobMetrics], interval_seconds: int = 30) -> None:
        """
        Print a visual concurrency timeline showing jobs running at each interval.

        Args:
            jobs: List of job metrics
            interval_seconds: Time interval for sampling
        """
        timeline = self.get_concurrency_timeline_display(jobs, interval_seconds)

        if not timeline:
            logger.info("No job data available for timeline")
            return

        max_concurrent = max(t["concurrent"] for t in timeline)

        logger.info("")
        logger.info("CONCURRENCY TIMELINE (every %d seconds):", interval_seconds)
        logger.info("-" * 60)

        for entry in timeline:
            bar = "█" * entry["concurrent"]
            spaces = " " * (max_concurrent - entry["concurrent"])
            logger.info(f"  {entry['offset_min']:5.1f}m | {bar}{spaces} | {entry['concurrent']}")

        logger.info("-" * 60)
        logger.info(f"  Peak concurrent: {max_concurrent}")
