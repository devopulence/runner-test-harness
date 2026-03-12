"""Tests for the GitHub API client with pagination and rate limiting (Story 2)."""

import json
import time
from unittest.mock import patch, MagicMock, PropertyMock

from github_client import GitHubClient, GitHubAPIError, RateLimitError


def _mock_response(status_code=200, json_data=None, headers=None):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = json.dumps(json_data or {})
    resp.headers = {
        "X-RateLimit-Remaining": "4999",
        "X-RateLimit-Limit": "5000",
        "X-RateLimit-Reset": str(int(time.time()) + 3600),
        "X-RateLimit-Used": "1",
        **(headers or {}),
    }
    return resp


def _make_client(**kwargs):
    """Create a client with a fake token."""
    defaults = {"token": "ghp_test_token", "owner": "testorg", "repo": "testrepo"}
    defaults.update(kwargs)
    return GitHubClient(**defaults)


# --- Pagination Tests ---

def test_single_page():
    """Single-page response returns all items."""
    client = _make_client()
    runs_data = {
        "total_count": 2,
        "workflow_runs": [
            {"id": 1, "status": "completed"},
            {"id": 2, "status": "in_progress"},
        ]
    }
    with patch.object(client._session, "request", return_value=_mock_response(json_data=runs_data)):
        runs = client.list_workflow_runs()
        assert len(runs) == 2
        assert runs[0]["id"] == 1
        assert runs[1]["id"] == 2
    print("PASS: test_single_page")


def test_multi_page_pagination():
    """Link header pagination fetches all pages."""
    client = _make_client()

    page1_data = {"workflow_runs": [{"id": i} for i in range(1, 101)]}
    page1_resp = _mock_response(json_data=page1_data, headers={
        "Link": '<https://api.github.com/repos/testorg/testrepo/actions/runs?page=2>; rel="next", '
                '<https://api.github.com/repos/testorg/testrepo/actions/runs?page=3>; rel="last"'
    })

    page2_data = {"workflow_runs": [{"id": i} for i in range(101, 201)]}
    page2_resp = _mock_response(json_data=page2_data, headers={
        "Link": '<https://api.github.com/repos/testorg/testrepo/actions/runs?page=3>; rel="next"'
    })

    page3_data = {"workflow_runs": [{"id": 201}]}
    page3_resp = _mock_response(json_data=page3_data)

    with patch.object(client._session, "request", side_effect=[page1_resp, page2_resp, page3_resp]):
        runs = client.list_workflow_runs()
        assert len(runs) == 201
        assert runs[0]["id"] == 1
        assert runs[-1]["id"] == 201
    print("PASS: test_multi_page_pagination")


def test_max_pages_limit():
    """Pagination stops at max_pages."""
    client = _make_client()

    page_data = {"workflow_runs": [{"id": 1}]}
    page_resp = _mock_response(json_data=page_data, headers={
        "Link": '<https://api.github.com/next?page=2>; rel="next"'
    })

    with patch.object(client._session, "request", return_value=page_resp):
        runs = client.list_workflow_runs(max_pages=2)
        assert len(runs) == 2  # 1 item per page * 2 pages
    print("PASS: test_max_pages_limit")


# --- Rate Limiting Tests ---

def test_rate_limit_tracking():
    """Rate limit state is updated from response headers."""
    client = _make_client()
    resp = _mock_response(json_data={"workflow_runs": []}, headers={
        "X-RateLimit-Remaining": "4500",
        "X-RateLimit-Limit": "5000",
        "X-RateLimit-Used": "500",
        "X-RateLimit-Reset": "1999999999",
    })

    with patch.object(client._session, "request", return_value=resp):
        client.list_workflow_runs()

    status = client.get_rate_limit_status()
    assert status["remaining"] == 4500
    assert status["limit"] == 5000
    assert status["used"] == 500
    assert status["reset"] == 1999999999
    print("PASS: test_rate_limit_tracking")


@patch("github_client.time.sleep")
def test_primary_rate_limit_retry(mock_sleep):
    """Primary rate limit (remaining=0) triggers wait then retry."""
    client = _make_client()

    rate_limited_resp = _mock_response(status_code=429, json_data={"message": "rate limit"}, headers={
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(int(time.time()) + 60),
    })
    success_resp = _mock_response(json_data={"workflow_runs": [{"id": 1}]})

    with patch.object(client._session, "request", side_effect=[rate_limited_resp, success_resp]):
        runs = client.list_workflow_runs()
        assert len(runs) == 1
        mock_sleep.assert_called()
    print("PASS: test_primary_rate_limit_retry")


@patch("github_client.time.sleep")
def test_secondary_rate_limit_retry_after(mock_sleep):
    """Secondary rate limit with Retry-After header."""
    client = _make_client()

    rate_limited_resp = _mock_response(status_code=403, json_data={"message": "secondary rate limit"}, headers={
        "Retry-After": "30",
        "X-RateLimit-Remaining": "100",
    })
    success_resp = _mock_response(json_data={"workflow_runs": [{"id": 1}]})

    with patch.object(client._session, "request", side_effect=[rate_limited_resp, success_resp]):
        runs = client.list_workflow_runs()
        assert len(runs) == 1
        mock_sleep.assert_any_call(30)
    print("PASS: test_secondary_rate_limit_retry_after")


# --- Retry / Backoff Tests ---

@patch("github_client.time.sleep")
@patch("github_client.random.uniform", return_value=0.5)
def test_transient_error_retry(mock_random, mock_sleep):
    """500 errors trigger exponential backoff retry."""
    client = _make_client()

    error_resp = _mock_response(status_code=502, json_data={"message": "Bad Gateway"})
    success_resp = _mock_response(json_data={"workflow_runs": [{"id": 1}]})

    with patch.object(client._session, "request", side_effect=[error_resp, error_resp, success_resp]):
        runs = client.list_workflow_runs()
        assert len(runs) == 1
        assert mock_sleep.call_count == 2  # Two retries before success
    print("PASS: test_transient_error_retry")


def test_non_retryable_error_raises():
    """404 raises GitHubAPIError immediately (no retry)."""
    client = _make_client()
    error_resp = _mock_response(status_code=404, json_data={"message": "Not Found"})

    with patch.object(client._session, "request", return_value=error_resp):
        try:
            client.get_workflow_run(99999)
            assert False, "Should have raised"
        except GitHubAPIError as e:
            assert e.status_code == 404
            assert "Not Found" in str(e)
    print("PASS: test_non_retryable_error_raises")


@patch("github_client.time.sleep")
def test_max_retries_exhausted(mock_sleep):
    """All retries fail raises GitHubAPIError."""
    client = _make_client(max_retries=3)
    error_resp = _mock_response(status_code=500, json_data={"message": "Server Error"})

    with patch.object(client._session, "request", return_value=error_resp):
        try:
            client.list_workflow_runs()
            assert False, "Should have raised"
        except GitHubAPIError as e:
            assert "Max retries" in str(e)
    print("PASS: test_max_retries_exhausted")


# --- Endpoint Tests ---

def test_list_jobs_for_run():
    """list_jobs_for_run returns job data with steps."""
    client = _make_client()
    jobs_data = {
        "total_count": 1,
        "jobs": [{
            "id": 5001,
            "run_id": 1001,
            "name": "build",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2026-03-11T10:00:00Z",
            "completed_at": "2026-03-11T10:05:00Z",
            "runner_name": "runner-1",
            "runner_id": 42,
            "steps": [
                {"name": "Set up job", "status": "completed", "conclusion": "success", "number": 1}
            ],
        }]
    }

    with patch.object(client._session, "request", return_value=_mock_response(json_data=jobs_data)):
        jobs = client.list_jobs_for_run(1001)
        assert len(jobs) == 1
        assert jobs[0]["runner_name"] == "runner-1"
        assert jobs[0]["steps"][0]["name"] == "Set up job"
    print("PASS: test_list_jobs_for_run")


def test_get_workflow_run():
    """get_workflow_run returns a single run dict."""
    client = _make_client()
    run_data = {"id": 1001, "name": "CI Build", "status": "completed", "conclusion": "success"}

    with patch.object(client._session, "request", return_value=_mock_response(json_data=run_data)):
        run = client.get_workflow_run(1001)
        assert run["id"] == 1001
        assert run["conclusion"] == "success"
    print("PASS: test_get_workflow_run")


def test_list_workflow_runs_with_filters():
    """Filters are passed as query params."""
    client = _make_client()
    resp = _mock_response(json_data={"workflow_runs": [{"id": 1}]})

    with patch.object(client._session, "request", return_value=resp) as mock_req:
        runs = client.list_workflow_runs(status="completed", branch="main", created=">=2026-03-11")
        assert len(runs) == 1

        # Verify params were passed
        call_kwargs = mock_req.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params", {})
        assert params["status"] == "completed"
        assert params["branch"] == "main"
        assert params["created"] == ">=2026-03-11"
    print("PASS: test_list_workflow_runs_with_filters")


def test_list_workflow_runs_for_workflow():
    """Can filter runs by workflow file."""
    client = _make_client()
    resp = _mock_response(json_data={"workflow_runs": [{"id": 1, "name": "CI"}]})

    with patch.object(client._session, "request", return_value=resp) as mock_req:
        runs = client.list_workflow_runs_for_workflow("ci.yml", status="completed")
        assert len(runs) == 1

        call_args = mock_req.call_args
        url = call_args.kwargs.get("url") or call_args[1].get("url") or call_args[0][1]
        assert "/actions/workflows/ci.yml/runs" in url
    print("PASS: test_list_workflow_runs_for_workflow")


# --- Configuration Tests ---

def test_enterprise_base_url():
    """Supports GitHub Enterprise URLs."""
    client = _make_client(base_url="https://github.example.com/api/v3")
    assert client._repo_url("/actions/runs") == \
        "https://github.example.com/api/v3/repos/testorg/testrepo/actions/runs"
    print("PASS: test_enterprise_base_url")


def test_context_manager():
    """Client works as a context manager."""
    with _make_client() as client:
        assert client.token == "ghp_test_token"
    print("PASS: test_context_manager")


def test_request_counter():
    """Request counter increments per request."""
    client = _make_client()
    resp = _mock_response(json_data={"workflow_runs": []})

    with patch.object(client._session, "request", return_value=resp):
        client.list_workflow_runs()
        client.list_workflow_runs()
        assert client.request_count == 2
    print("PASS: test_request_counter")


def test_no_token_raises():
    """Missing token raises ValueError."""
    try:
        with patch.dict("os.environ", {}, clear=True):
            GitHubClient(token=None, owner="x", repo="y")
        assert False, "Should have raised"
    except ValueError as e:
        assert "No token" in str(e)
    print("PASS: test_no_token_raises")


# --- Link Header Parsing ---

def test_link_header_parsing():
    """Link header is correctly parsed into rel:url dict."""
    client = _make_client()
    header = (
        '<https://api.github.com/repos/org/repo/actions/runs?page=2>; rel="next", '
        '<https://api.github.com/repos/org/repo/actions/runs?page=5>; rel="last"'
    )
    links = client._parse_link_header(header)
    assert links["next"] == "https://api.github.com/repos/org/repo/actions/runs?page=2"
    assert links["last"] == "https://api.github.com/repos/org/repo/actions/runs?page=5"
    print("PASS: test_link_header_parsing")


if __name__ == "__main__":
    test_single_page()
    test_multi_page_pagination()
    test_max_pages_limit()
    test_rate_limit_tracking()
    test_primary_rate_limit_retry()
    test_secondary_rate_limit_retry_after()
    test_transient_error_retry()
    test_non_retryable_error_raises()
    test_max_retries_exhausted()
    test_list_jobs_for_run()
    test_get_workflow_run()
    test_list_workflow_runs_with_filters()
    test_list_workflow_runs_for_workflow()
    test_enterprise_base_url()
    test_context_manager()
    test_request_counter()
    test_no_token_raises()
    test_link_header_parsing()
    print("\nAll Story 2 tests passed!")