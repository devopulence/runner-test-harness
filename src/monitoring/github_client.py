"""
GitHub API Client with Pagination and Rate Limiting (Story 2)

A synchronous HTTP client for the GitHub REST API, purpose-built for
monitoring data collection. Handles:
- Automatic pagination via Link headers
- Primary rate limit tracking (X-RateLimit-* headers)
- Secondary rate limit handling (Retry-After header)
- Exponential backoff with jitter on transient errors
- Corporate proxy and custom CA certificate support

Usage:
    client = GitHubClient(token="ghp_xxx", owner="myorg", repo="myrepo")
    runs = client.list_workflow_runs(status="completed", created=">=2026-03-11")
    for run in runs:
        jobs = client.list_jobs_for_run(run["id"])
"""

import logging
import os
import re
import time
import random
from pathlib import Path
from typing import Any, Optional, Iterator

from dotenv import load_dotenv
import requests

# Load .env from project root (walks up from this file to find it)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Transient HTTP status codes that warrant a retry
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

# Default max pages to fetch during pagination (safety limit)
DEFAULT_MAX_PAGES = 50


class RateLimitError(Exception):
    """Raised when the GitHub API rate limit is exhausted."""

    def __init__(self, reset_at: int, remaining: int = 0):
        self.reset_at = reset_at
        self.remaining = remaining
        wait = max(reset_at - int(time.time()), 0)
        super().__init__(f"Rate limit exhausted. Resets in {wait}s (at epoch {reset_at})")


class GitHubAPIError(Exception):
    """Raised for non-retryable GitHub API errors."""

    def __init__(self, status_code: int, message: str, response: Optional[dict] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(f"GitHub API error {status_code}: {message}")


class GitHubClient:
    """
    Synchronous GitHub REST API client with pagination and rate limiting.

    Args:
        token: GitHub PAT or app token. Falls back to GITHUB_TOKEN env var.
        owner: Repository owner (org or user).
        repo: Repository name.
        base_url: GitHub API base URL (for Enterprise, e.g. https://github.example.com/api/v3).
        api_version: GitHub API version header.
        max_retries: Max retry attempts for transient errors.
        backoff_factor: Multiplier for exponential backoff between retries.
        timeout: HTTP request timeout in seconds.
        ca_bundle: Path to CA certificate bundle (for corporate proxies).
        proxies: Dict of proxy URLs ({"https": "http://proxy:8080"}).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        owner: str = "",
        repo: str = "",
        base_url: str = "https://api.github.com",
        api_version: str = "2022-11-28",
        max_retries: int = 5,
        backoff_factor: float = 1.0,
        timeout: int = 30,
        ca_bundle: Optional[str] = None,
        proxies: Optional[dict] = None,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("No token provided. Set GITHUB_TOKEN env var or pass token=")

        self.owner = owner
        self.repo = repo
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.timeout = timeout
        self.ca_bundle = ca_bundle or os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
        self.proxies = proxies

        # Rate limit state (updated from response headers)
        self.rate_limit_remaining: int = 5000
        self.rate_limit_limit: int = 5000
        self.rate_limit_reset: int = 0
        self.rate_limit_used: int = 0

        # Request counter for observability
        self.request_count: int = 0

        # Build session with transport-level retries for connection errors
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": "github-monitoring-client/1.0",
        })
        # Transport-level retries for connection errors only
        # (application-level retries for HTTP errors handled in _request)
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[],  # We handle status retries ourselves
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # --- Rate limit tracking ---

    def _update_rate_limit(self, response: requests.Response) -> None:
        """Update rate limit state from response headers."""
        try:
            self.rate_limit_remaining = int(response.headers.get("X-RateLimit-Remaining", self.rate_limit_remaining))
            self.rate_limit_limit = int(response.headers.get("X-RateLimit-Limit", self.rate_limit_limit))
            self.rate_limit_reset = int(response.headers.get("X-RateLimit-Reset", self.rate_limit_reset))
            self.rate_limit_used = int(response.headers.get("X-RateLimit-Used", self.rate_limit_used))
        except (ValueError, TypeError):
            pass

    def get_rate_limit_status(self) -> dict:
        """Return current rate limit state."""
        return {
            "remaining": self.rate_limit_remaining,
            "limit": self.rate_limit_limit,
            "used": self.rate_limit_used,
            "reset": self.rate_limit_reset,
            "reset_in_seconds": max(self.rate_limit_reset - int(time.time()), 0),
        }

    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle rate limit responses per GitHub docs:
        - Primary: x-ratelimit-remaining == 0 → wait until x-ratelimit-reset
        - Secondary: retry-after header → wait that many seconds
        """
        # Secondary rate limit (has Retry-After header)
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            wait = int(retry_after)
            logger.warning("Secondary rate limit hit. Waiting %ds (Retry-After header)", wait)
            time.sleep(wait)
            return

        # Primary rate limit exhausted
        if self.rate_limit_remaining == 0:
            wait = max(self.rate_limit_reset - int(time.time()), 1)
            logger.warning(
                "Primary rate limit exhausted (%d/%d used). Waiting %ds until reset.",
                self.rate_limit_used, self.rate_limit_limit, wait
            )
            time.sleep(min(wait, 300))  # Cap at 5 minutes
            return

        # Unknown rate limit scenario — wait 60s per GitHub docs
        logger.warning("Rate limited (HTTP %d) with unknown cause. Waiting 60s.", response.status_code)
        time.sleep(60)

    # --- Core request method ---

    def _request(self, method: str, url: str, params: Optional[dict] = None,
                 json_body: Optional[dict] = None) -> requests.Response:
        """
        Make an HTTP request with rate limiting and retry logic.

        Retries on:
        - 429 Too Many Requests (rate limit)
        - 5xx Server errors
        - Connection errors (handled by urllib3 Retry)

        Raises GitHubAPIError for non-retryable failures.
        """
        verify = self.ca_bundle if self.ca_bundle else True

        for attempt in range(self.max_retries):
            try:
                self.request_count += 1
                response = self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body,
                    verify=verify,
                    proxies=self.proxies,
                    timeout=self.timeout,
                )
                self._update_rate_limit(response)

                # Success
                if response.status_code in (200, 201, 204):
                    return response

                # Rate limited — handle and retry
                if response.status_code in (403, 429):
                    is_rate_limit = (
                        self.rate_limit_remaining == 0
                        or response.headers.get("Retry-After")
                        or "rate limit" in response.text.lower()
                    )
                    if is_rate_limit:
                        self._handle_rate_limit(response)
                        continue

                # Transient server error — backoff and retry
                if response.status_code in RETRYABLE_STATUSES:
                    wait = self.backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "Transient error %d on attempt %d/%d. Retrying in %.1fs.",
                        response.status_code, attempt + 1, self.max_retries, wait
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable error
                try:
                    error_body = response.json()
                    message = error_body.get("message", response.text[:200])
                except Exception:
                    error_body = None
                    message = response.text[:200]

                raise GitHubAPIError(response.status_code, message, error_body)

            except requests.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait = self.backoff_factor * (2 ** attempt)
                    logger.warning("Connection error on attempt %d/%d: %s. Retrying in %.1fs.",
                                   attempt + 1, self.max_retries, e, wait)
                    time.sleep(wait)
                else:
                    raise

        raise GitHubAPIError(0, f"Max retries ({self.max_retries}) exhausted")

    # --- Pagination ---

    def _parse_link_header(self, link_header: str) -> dict:
        """Parse GitHub Link header into {rel: url} dict."""
        links = {}
        for part in link_header.split(","):
            match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', part.strip())
            if match:
                links[match.group(2)] = match.group(1)
        return links

    def _paginate(self, url: str, params: Optional[dict] = None,
                  max_pages: int = DEFAULT_MAX_PAGES) -> Iterator[dict]:
        """
        Auto-paginate through GitHub API results using Link headers.

        Yields individual items from each page. Stops when:
        - No 'next' link in response
        - max_pages reached (safety limit)
        """
        params = dict(params or {})
        params.setdefault("per_page", 100)
        current_url = url
        current_params = params

        for page_num in range(1, max_pages + 1):
            response = self._request("GET", current_url, params=current_params)

            data = response.json()

            # GitHub list endpoints return either an array or {total_count, items_key: [...]}
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Find the array field (workflow_runs, jobs, etc.)
                items = None
                for key, value in data.items():
                    if isinstance(value, list):
                        items = value
                        break
                if items is None:
                    yield data
                    return
            else:
                return

            for item in items:
                yield item

            # Check for next page via Link header
            link_header = response.headers.get("Link", "")
            links = self._parse_link_header(link_header)

            if "next" not in links:
                break

            # Next page URL is absolute — don't re-send params
            current_url = links["next"]
            current_params = None

            logger.debug("Fetching page %d for %s", page_num + 1, url)

    # --- Repo-scoped URL helper ---

    def _repo_url(self, path: str) -> str:
        """Build a repo-scoped API URL."""
        return f"{self.base_url}/repos/{self.owner}/{self.repo}{path}"

    # --- GitHub Actions endpoints ---

    def list_workflow_runs(self, max_pages: int = DEFAULT_MAX_PAGES, **filters) -> list[dict]:
        """
        List workflow runs for the repository.

        Supported filters (passed as query params):
            status: "queued", "in_progress", "completed"
            branch: branch name
            event: "push", "pull_request", "workflow_dispatch", etc.
            actor: GitHub username
            created: date filter (e.g. ">=2026-03-11", "2026-03-11..2026-03-12")
            per_page: results per page (max 100, default 100)

        Returns:
            List of workflow run dicts.
        """
        url = self._repo_url("/actions/runs")
        params = {k: v for k, v in filters.items() if v is not None}
        return list(self._paginate(url, params=params, max_pages=max_pages))

    def get_workflow_run(self, run_id: int) -> dict:
        """Get a single workflow run by ID."""
        url = self._repo_url(f"/actions/runs/{run_id}")
        response = self._request("GET", url)
        return response.json()

    def list_jobs_for_run(self, run_id: int, filter: str = "latest",
                          max_pages: int = 10) -> list[dict]:
        """
        List jobs for a specific workflow run.

        Args:
            run_id: Workflow run ID.
            filter: "latest" (most recent attempt) or "all" (all attempts).
            max_pages: Max pages to fetch.

        Returns:
            List of job dicts with steps, runner info, timestamps.
        """
        url = self._repo_url(f"/actions/runs/{run_id}/jobs")
        params = {"filter": filter}
        return list(self._paginate(url, params=params, max_pages=max_pages))

    def list_workflow_runs_for_workflow(self, workflow_id: str,
                                       max_pages: int = DEFAULT_MAX_PAGES,
                                       **filters) -> list[dict]:
        """
        List runs for a specific workflow file.

        Args:
            workflow_id: Workflow filename (e.g. "ci.yml") or numeric ID.
            **filters: Same filters as list_workflow_runs.
        """
        url = self._repo_url(f"/actions/workflows/{workflow_id}/runs")
        params = {k: v for k, v in filters.items() if v is not None}
        return list(self._paginate(url, params=params, max_pages=max_pages))

    # --- Organization-level endpoints ---

    def list_org_repos(self, org: str, max_pages: int = DEFAULT_MAX_PAGES,
                       repo_type: str = "all", sort: str = "updated") -> list[dict]:
        """
        List all repositories for an organization.

        Args:
            org: Organization name.
            repo_type: "all", "public", "private", "forks", "sources", "member".
            sort: "created", "updated", "pushed", "full_name".
            max_pages: Max pages to fetch.

        Returns:
            List of repository dicts.
        """
        url = f"{self.base_url}/orgs/{org}/repos"
        params = {"type": repo_type, "sort": sort}
        return list(self._paginate(url, params=params, max_pages=max_pages))

    def list_org_workflow_runs(self, org: str, max_pages_per_repo: int = 5,
                               **filters) -> list[dict]:
        """
        List workflow runs across ALL repos in an organization.

        Iterates all org repos and collects workflow runs from each.
        Each run dict is enriched with 'repository.full_name' for identification.

        Args:
            org: Organization name.
            max_pages_per_repo: Max pages to fetch per repo (default 5 = up to 500 runs/repo).
            **filters: Passed to list_workflow_runs (status, created, branch, etc.)

        Returns:
            List of workflow run dicts from all repos, sorted by created_at descending.
        """
        repos = self.list_org_repos(org)
        logger.info("Found %d repos in org '%s'", len(repos), org)

        all_runs = []
        for repo in repos:
            repo_name = repo["name"]
            repo_full = repo["full_name"]

            # Temporarily override owner/repo for the API call
            orig_owner, orig_repo = self.owner, self.repo
            self.owner = org
            self.repo = repo_name

            try:
                runs = self.list_workflow_runs(max_pages=max_pages_per_repo, **filters)
                if runs:
                    logger.info("  %s: %d runs", repo_full, len(runs))
                    all_runs.extend(runs)
            except GitHubAPIError as e:
                # Skip repos where Actions is disabled or no access
                if e.status_code in (404, 403):
                    logger.debug("  %s: skipped (HTTP %d)", repo_full, e.status_code)
                else:
                    logger.warning("  %s: error %s", repo_full, e)
            finally:
                self.owner, self.repo = orig_owner, orig_repo

        # Sort all runs by created_at descending (newest first)
        all_runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        logger.info("Total: %d workflow runs across %d repos", len(all_runs), len(repos))
        return all_runs

    def get_rate_limit(self) -> dict:
        """Query the /rate_limit endpoint for current rate limit status."""
        url = f"{self.base_url}/rate_limit"
        response = self._request("GET", url)
        return response.json()

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
