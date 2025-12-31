"""
Configuration Manager for GitHub Runner Performance Testing Harness
Loads and manages configuration from YAML files with environment variable support
"""

import os
import yaml
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    """GitHub API configuration"""
    owner: str
    repo: str
    token: str
    rate_limit: int = 10
    max_concurrent: int = 20

    @classmethod
    def from_dict(cls, data: Dict) -> 'GitHubConfig':
        # Get token from env var if not in config
        token = data.get('token') or os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GitHub token not found in config or GITHUB_TOKEN env var")

        return cls(
            owner=data['owner'],
            repo=data['repo'],
            token=token,
            rate_limit=data.get('rate_limit', 10),
            max_concurrent=data.get('max_concurrent', 20)
        )


@dataclass
class TestScenarioConfig:
    """Configuration for a specific test scenario"""
    enabled: bool
    config: Dict[str, Any]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)


@dataclass
class MonitoringConfig:
    """Monitoring configuration"""
    poll_interval: int
    workflow_timeout: int
    real_time: bool
    metrics: List[str]

    @classmethod
    def from_dict(cls, data: Dict) -> 'MonitoringConfig':
        return cls(
            poll_interval=data.get('poll_interval', 10),
            workflow_timeout=data.get('workflow_timeout', 3600),
            real_time=data.get('real_time', True),
            metrics=data.get('metrics', ['queue_time', 'execution_time', 'success_rate'])
        )


@dataclass
class StorageConfig:
    """Storage configuration"""
    metrics_path: Path
    results_path: Path
    reports_path: Path
    retention_days: int

    @classmethod
    def from_dict(cls, data: Dict) -> 'StorageConfig':
        return cls(
            metrics_path=Path(data.get('metrics_path', './metrics')),
            results_path=Path(data.get('results_path', './results')),
            reports_path=Path(data.get('reports_path', './reports')),
            retention_days=data.get('retention_days', 30)
        )

    def create_directories(self):
        """Create storage directories if they don't exist"""
        self.metrics_path.mkdir(exist_ok=True, parents=True)
        self.results_path.mkdir(exist_ok=True, parents=True)
        self.reports_path.mkdir(exist_ok=True, parents=True)


class ConfigManager:
    """Manages harness configuration"""

    def __init__(self, config_file: str = "config.yaml", environment: Optional[str] = None):
        self.config_file = Path(config_file)
        self.raw_config = {}
        self.environment = environment

        # Load configuration
        self.load_config()

        # Parse main sections
        self.github = GitHubConfig.from_dict(self.raw_config['github'])
        self.monitoring = MonitoringConfig.from_dict(self.raw_config['monitoring'])
        self.storage = StorageConfig.from_dict(self.raw_config['storage'])

        # Create storage directories
        self.storage.create_directories()

        # Parse test scenarios
        self.test_scenarios = self._parse_test_scenarios()

        # Parse workflows
        self.workflows = self.raw_config.get('test_workflows', {}).get('workflows', {})

        # Store other config sections
        self.runners = self.raw_config.get('runners', {})
        self.reporting = self.raw_config.get('reporting', {})
        self.alerts = self.raw_config.get('alerts', {})
        self.execution = self.raw_config.get('execution', {})

    def load_config(self):
        """Load configuration from YAML file"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        with open(self.config_file, 'r') as f:
            self.raw_config = yaml.safe_load(f)

        # Apply environment-specific overrides if specified
        if not self.environment:
            self.environment = self.raw_config.get('environment', 'development')

        if self.environment and 'environments' in self.raw_config:
            env_config = self.raw_config['environments'].get(self.environment, {})
            self._merge_config(self.raw_config, env_config)

        logger.info(f"Loaded configuration for environment: {self.environment}")

    def _merge_config(self, base: Dict, override: Dict):
        """Recursively merge override config into base config"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _parse_test_scenarios(self) -> Dict[str, TestScenarioConfig]:
        """Parse test scenario configurations"""
        scenarios = {}
        scenario_configs = self.raw_config.get('test_scenarios', {})

        for scenario_name, scenario_data in scenario_configs.items():
            if isinstance(scenario_data, dict):
                enabled = scenario_data.get('enabled', False)
                scenarios[scenario_name] = TestScenarioConfig(
                    enabled=enabled,
                    config=scenario_data
                )

        return scenarios

    def get_test_scenario(self, scenario_name: str) -> Optional[TestScenarioConfig]:
        """Get configuration for a specific test scenario"""
        return self.test_scenarios.get(scenario_name)

    def get_enabled_scenarios(self) -> List[str]:
        """Get list of enabled test scenarios"""
        return [name for name, config in self.test_scenarios.items() if config.enabled]

    def get_workflow_config(self, workflow_type: str) -> Optional[Dict]:
        """Get configuration for a specific workflow type"""
        return self.workflows.get(workflow_type)

    def get_workflow_file(self, workflow_type: str) -> Optional[str]:
        """Get workflow file path for a specific type"""
        workflow = self.get_workflow_config(workflow_type)
        if workflow:
            workflow_dir = self.raw_config.get('test_workflows', {}).get('directory', './test_workflows')
            return os.path.join(workflow_dir, workflow['file'])
        return None

    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode"""
        return self.execution.get('dry_run', False)

    def get_dashboard_config(self) -> Dict:
        """Get dashboard configuration"""
        return self.reporting.get('dashboard', {})

    def save_config_snapshot(self, output_path: Optional[Path] = None):
        """Save current configuration snapshot"""
        if not output_path:
            output_path = self.storage.results_path / "config_snapshot.json"

        snapshot = {
            'environment': self.environment,
            'github': {
                'owner': self.github.owner,
                'repo': self.github.repo,
                'rate_limit': self.github.rate_limit,
                'max_concurrent': self.github.max_concurrent
            },
            'enabled_scenarios': self.get_enabled_scenarios(),
            'runners': self.runners,
            'monitoring': {
                'poll_interval': self.monitoring.poll_interval,
                'workflow_timeout': self.monitoring.workflow_timeout
            },
            'execution': self.execution
        }

        with open(output_path, 'w') as f:
            json.dump(snapshot, f, indent=2)

        logger.info(f"Saved configuration snapshot to {output_path}")
        return output_path

    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues"""
        issues = []

        # Check GitHub configuration
        if not self.github.owner:
            issues.append("GitHub owner not specified")
        if not self.github.repo:
            issues.append("GitHub repository not specified")
        if not self.github.token:
            issues.append("GitHub token not found")

        # Check workflow files exist
        workflow_dir = Path(self.raw_config.get('test_workflows', {}).get('directory', './test_workflows'))
        if not workflow_dir.exists():
            issues.append(f"Workflow directory not found: {workflow_dir}")
        else:
            for workflow_type, workflow_config in self.workflows.items():
                workflow_file = workflow_dir / workflow_config['file']
                if not workflow_file.exists():
                    issues.append(f"Workflow file not found: {workflow_file}")

        # Check at least one test scenario is enabled
        if not self.get_enabled_scenarios():
            issues.append("No test scenarios are enabled")

        # Validate scenario configurations
        for scenario_name, scenario in self.test_scenarios.items():
            if scenario.enabled:
                if scenario_name == 'load':
                    if scenario.get('steady_state', {}).get('workflows_per_minute', 0) <= 0:
                        issues.append(f"Invalid workflows_per_minute in {scenario_name}")

        return issues

    def print_config_summary(self):
        """Print configuration summary"""
        print("\n" + "=" * 60)
        print("CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Environment: {self.environment}")
        print(f"GitHub: {self.github.owner}/{self.github.repo}")
        print(f"Runner Type: {self.runners.get('type', 'unknown')}")
        print(f"Enabled Scenarios: {', '.join(self.get_enabled_scenarios())}")

        print("\nTest Workflows:")
        for name, config in self.workflows.items():
            print(f"  - {name}: {config['file']} ({config.get('expected_duration', 'unknown')}s)")

        print("\nStorage Paths:")
        print(f"  - Metrics: {self.storage.metrics_path}")
        print(f"  - Results: {self.storage.results_path}")
        print(f"  - Reports: {self.storage.reports_path}")

        print("\nMonitoring:")
        print(f"  - Poll Interval: {self.monitoring.poll_interval}s")
        print(f"  - Timeout: {self.monitoring.workflow_timeout}s")
        print(f"  - Real-time: {self.monitoring.real_time}")

        if self.is_dry_run():
            print("\n⚠️  DRY RUN MODE ENABLED - No workflows will be dispatched")

        print("=" * 60 + "\n")


# Example usage
if __name__ == "__main__":
    # Load configuration
    config = ConfigManager()

    # Validate
    issues = config.validate_config()
    if issues:
        print("Configuration issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("Configuration valid!")

    # Print summary
    config.print_config_summary()

    # Save snapshot
    config.save_config_snapshot()