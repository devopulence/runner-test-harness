import os
import sys
import json
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def trigger_workflow_dispatch(
        owner: str,
        repo: str,
        workflow_id_or_filename: str,
        ref: str = "main",
        inputs: dict | None = None,
        token: str | None = None,
        api_version: str = "2022-11-28",
        ca_bundle: str | None = None,
        proxies: dict | None = None,
        timeout: int = 30,
) -> None:
    """
    Triggers a GitHub Actions workflow via the workflow_dispatch REST API.

    Args:
        owner: GitHub org/user that owns the repository.
        repo: Repository name.
        workflow_id_or_filename: Numeric workflow ID or workflow file name (e.g., 'deploy.yml').
        ref: Branch or tag where the workflow file exists (default 'main').
        inputs: Dict of workflow_dispatch inputs defined in your workflow YAML.
        token: Personal Access Token (PAT) with appropriate scopes.
        api_version: GitHub API version header (default '2022-11-28').
        ca_bundle: Path to corporate CA PEM (if your network intercepts TLS).
        proxies: Dict with 'http' and/or 'https' proxy URLs.
        timeout: Request timeout in seconds.

    Raises:
        requests.HTTPError: If the API call fails.
    """
    if token is None:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("No token provided. Set GITHUB_TOKEN env var or pass token=...")

    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id_or_filename}/dispatches"

    payload = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": api_version,
        "Content-Type": "application/json",
        "User-Agent": "workflow-dispatch-python"
    }

    # Robust session with retries for transient network/proxy hiccups
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["POST"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    print(f"Dispatching workflow '{workflow_id_or_filename}' on ref '{ref}' for {owner}/{repo}...")
    resp = session.post(
        url,
        headers=headers,
        json=payload,  # send JSON body
        verify=ca_bundle if ca_bundle else True,
        proxies=proxies if proxies else None,
        timeout=timeout,
    )

    # Success returns 204 No Content
    if resp.status_code == 204:
        print("✅ Workflow dispatch created successfully (HTTP 204).")
        print("You can check the run under 'Actions' in the repository UI.")
    else:
        print(f"⚠️ Unexpected status: {resp.status_code}")
        try:
            print("Response:", resp.json())
        except Exception:
            print("Raw response:", resp.text)
        resp.raise_for_status()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger GitHub Actions workflow_dispatch")
    parser.add_argument("--owner", required=True, help="Repository owner/org (e.g., xxx-sandbox)")
    parser.add_argument("--repo", required=True, help="Repository name (e.g., ghe-test)")
    parser.add_argument("--workflow", required=True, help="Workflow file name or numeric ID (e.g., k8s.yml)")
    parser.add_argument("--ref", default="main", help="Branch or tag containing the workflow file (default: main)")
    parser.add_argument("--inputs", default=None, help="JSON string for workflow inputs (optional)")
    parser.add_argument("--token", default=os.getenv("GITHUB_TOKEN"),
                        help="PAT or GitHub App token (default: env GITHUB_TOKEN)")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds (default: 30)")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        args = parse_args()

        # Parse inputs JSON if provided
        inputs_dict = None
        if args.inputs:
            try:
                inputs_dict = json.loads(args.inputs)
            except json.JSONDecodeError as e:
                print(f"Error parsing --inputs JSON: {e}")
                sys.exit(1)

        # Optional corporate CA & proxies from environment
        ca_bundle = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
        proxies = {k: v for k, v in {
            "http": os.getenv("HTTP_PROXY"),
            "https": os.getenv("HTTPS_PROXY"),
        }.items() if v}

        trigger_workflow_dispatch(
            owner=args.owner,
            repo=args.repo,
            workflow_id_or_filename=args.workflow,
            ref=args.ref,
            inputs=inputs_dict,
            token=args.token,
            ca_bundle=ca_bundle,
            proxies=proxies if proxies else None,
            timeout=args.timeout,
        )
    except Exception as e:
        print("Error:", e)

