"""
Test Run Tracker - Tracks workflows dispatched by each test run.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class TestRunTracker:
    """Track workflows dispatched during a test run."""

    def __init__(self, test_type: str, environment: str):
        """
        Initialize a test run tracker.

        Args:
            test_type: Type of test (performance, load, stress, etc)
            environment: Environment name (aws-ecs, openshift, etc)
        """
        self.test_type = test_type
        self.environment = environment
        self.test_run_id = self._generate_test_id()
        self.start_time = datetime.now()
        self.workflow_ids = []
        self.workflow_names = []

    def _generate_test_id(self) -> str:
        """Generate a unique test run ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{self.test_type}_{timestamp}_{short_uuid}"

    def get_job_name(self) -> str:
        """Get the job_name to tag workflows with."""
        return self.test_run_id

    def add_workflow(self, workflow_id: int, workflow_name: str):
        """Record a dispatched workflow."""
        self.workflow_ids.append(workflow_id)
        self.workflow_names.append(workflow_name)

    def save_tracking_data(self) -> str:
        """Save tracking data to file."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() / 60

        tracking_data = {
            "test_run_id": self.test_run_id,
            "test_type": self.test_type,
            "environment": self.environment,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": duration,
            "workflow_count": len(self.workflow_ids),
            "workflow_ids": self.workflow_ids,
            "workflow_names": self.workflow_names,
            "metadata": {
                "job_name_tag": self.test_run_id,
                "query_hint": f"Search for workflows with job_name={self.test_run_id}"
            }
        }

        # Save to tracking directory
        tracking_dir = Path(f"test_results/{self.environment}/tracking")
        tracking_dir.mkdir(parents=True, exist_ok=True)

        tracking_file = tracking_dir / f"{self.test_run_id}.json"
        with open(tracking_file, 'w') as f:
            json.dump(tracking_data, f, indent=2)

        # Also save as "latest" for easy access
        latest_file = tracking_dir / "latest.json"
        with open(latest_file, 'w') as f:
            json.dump(tracking_data, f, indent=2)

        print(f"\n📌 Test Run ID: {self.test_run_id}")
        print(f"📄 Tracking saved to: {tracking_file}")

        return str(tracking_file)


def load_test_run(test_run_id: str = None, environment: str = "aws-ecs") -> Dict[str, Any]:
    """
    Load tracking data for a specific test run.

    Args:
        test_run_id: Specific test run ID, or None for latest
        environment: Environment name

    Returns:
        Tracking data dictionary
    """
    tracking_dir = Path(f"test_results/{environment}/tracking")

    if test_run_id:
        tracking_file = tracking_dir / f"{test_run_id}.json"
    else:
        tracking_file = tracking_dir / "latest.json"

    if not tracking_file.exists():
        raise FileNotFoundError(f"Test run tracking not found: {tracking_file}")

    with open(tracking_file) as f:
        return json.load(f)


def list_test_runs(environment: str = "aws-ecs") -> List[Dict[str, str]]:
    """
    List all test runs for an environment.

    Returns:
        List of test run summaries
    """
    tracking_dir = Path(f"test_results/{environment}/tracking")
    if not tracking_dir.exists():
        return []

    runs = []
    for file in sorted(tracking_dir.glob("*.json")):
        if file.name == "latest.json":
            continue

        with open(file) as f:
            data = json.load(f)
            runs.append({
                "test_run_id": data["test_run_id"],
                "test_type": data["test_type"],
                "start_time": data["start_time"],
                "duration_minutes": data.get("duration_minutes", 0),
                "workflow_count": data.get("workflow_count", 0)
            })

    return runs