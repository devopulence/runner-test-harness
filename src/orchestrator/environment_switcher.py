"""
Environment Switcher Module
Manages switching between AWS ECS and OpenShift environments for portable testing
"""

import os
import yaml
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for a single workflow"""
    name: str
    file: str
    description: str
    default_inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestProfile:
    """Configuration for a test profile"""
    name: str
    duration_minutes: int
    workflows: List[str]
    dispatch_pattern: str
    jobs_per_minute: Optional[float] = None
    burst_size: Optional[int] = None
    burst_interval: Optional[int] = None
    normal_rate: Optional[float] = None
    spike_rate: Optional[float] = None
    spike_duration: Optional[int] = None
    spike_start: Optional[int] = None


@dataclass
class EnvironmentConfig:
    """Complete environment configuration"""
    name: str
    description: str
    type: str
    github_owner: str
    github_repo: str
    runner_labels: List[str]
    runner_count: int
    workflows: List[WorkflowConfig]
    test_profiles: Dict[str, TestProfile]
    metrics: Dict[str, Any]
    network: Dict[str, Any]
    logging_config: Dict[str, Any]
    raw_config: Dict[str, Any]


class EnvironmentSwitcher:
    """
    Manages environment configurations and switching between them
    """

    def __init__(self, config_dir: str = "config"):
        """
        Initialize the environment switcher

        Args:
            config_dir: Directory containing environment configurations
        """
        self.config_dir = Path(config_dir)
        self.environments_dir = self.config_dir / "environments"
        self.base_config_path = self.config_dir / "base_config.yaml"

        self.base_config: Dict[str, Any] = {}
        self.current_environment: Optional[EnvironmentConfig] = None
        self.available_environments: Dict[str, Path] = {}

        # Load base configuration
        self._load_base_config()

        # Discover available environments
        self._discover_environments()

    def _load_base_config(self) -> None:
        """Load the base configuration file"""
        if self.base_config_path.exists():
            try:
                with open(self.base_config_path, 'r') as f:
                    self.base_config = yaml.safe_load(f)
                logger.info(f"Loaded base configuration from {self.base_config_path}")
            except Exception as e:
                logger.error(f"Failed to load base configuration: {e}")
                self.base_config = {}
        else:
            logger.warning(f"Base configuration not found at {self.base_config_path}")

    def _discover_environments(self) -> None:
        """Discover available environment configurations"""
        if not self.environments_dir.exists():
            logger.warning(f"Environments directory not found: {self.environments_dir}")
            return

        for config_file in self.environments_dir.glob("*.yaml"):
            env_name = config_file.stem
            self.available_environments[env_name] = config_file
            logger.debug(f"Discovered environment: {env_name}")

        logger.info(f"Found {len(self.available_environments)} environment(s): "
                   f"{list(self.available_environments.keys())}")

    def list_environments(self) -> List[str]:
        """
        List all available environments

        Returns:
            List of environment names
        """
        return list(self.available_environments.keys())

    def load_environment(self, environment_name: str) -> EnvironmentConfig:
        """
        Load a specific environment configuration

        Args:
            environment_name: Name of the environment to load

        Returns:
            Loaded environment configuration

        Raises:
            ValueError: If environment not found
        """
        if environment_name not in self.available_environments:
            raise ValueError(f"Environment '{environment_name}' not found. "
                           f"Available: {self.list_environments()}")

        config_path = self.available_environments[environment_name]

        try:
            with open(config_path, 'r') as f:
                env_config = yaml.safe_load(f)

            # Merge with base configuration
            merged_config = self._merge_configs(self.base_config, env_config)

            # Parse into EnvironmentConfig object
            environment = self._parse_environment_config(merged_config)

            self.current_environment = environment
            logger.info(f"Loaded environment: {environment_name}")

            return environment

        except Exception as e:
            logger.error(f"Failed to load environment '{environment_name}': {e}")
            raise

    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge base configuration with environment-specific overrides

        Args:
            base: Base configuration
            override: Environment-specific configuration

        Returns:
            Merged configuration
        """
        merged = base.copy()

        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # Override value
                merged[key] = value

        return merged

    def _parse_environment_config(self, config: Dict[str, Any]) -> EnvironmentConfig:
        """
        Parse raw configuration into EnvironmentConfig object

        Args:
            config: Raw configuration dictionary

        Returns:
            Parsed EnvironmentConfig
        """
        # Parse workflows
        workflows = []
        for wf in config.get('workflows', {}).get('available', []):
            workflows.append(WorkflowConfig(
                name=wf['name'],
                file=wf['file'],
                description=wf.get('description', ''),
                default_inputs=wf.get('default_inputs', {})
            ))

        # Parse test profiles
        test_profiles = {}
        for profile_name, profile_config in config.get('test_profiles', {}).items():
            test_profiles[profile_name] = TestProfile(
                name=profile_name,
                duration_minutes=profile_config['duration_minutes'],
                workflows=profile_config['workflows'],
                dispatch_pattern=profile_config['dispatch_pattern'],
                jobs_per_minute=profile_config.get('jobs_per_minute'),
                burst_size=profile_config.get('burst_size'),
                burst_interval=profile_config.get('burst_interval'),
                normal_rate=profile_config.get('normal_rate'),
                spike_rate=profile_config.get('spike_rate'),
                spike_duration=profile_config.get('spike_duration'),
                spike_start=profile_config.get('spike_start')
            )

        return EnvironmentConfig(
            name=config['environment']['name'],
            description=config['environment']['description'],
            type=config['environment']['type'],
            github_owner=config['github']['owner'],
            github_repo=config['github']['repo'],
            runner_labels=config['github']['runner_labels'],
            runner_count=config['runners']['count'],
            workflows=workflows,
            test_profiles=test_profiles,
            metrics=config.get('metrics', {}),
            network=config.get('network', {}),
            logging_config=config.get('logging', {}),
            raw_config=config
        )

    def get_current_environment(self) -> Optional[EnvironmentConfig]:
        """
        Get the currently loaded environment

        Returns:
            Current environment configuration or None
        """
        return self.current_environment

    def validate_environment(self, environment: Optional[EnvironmentConfig] = None) -> Dict[str, Any]:
        """
        Validate an environment configuration

        Args:
            environment: Environment to validate (uses current if None)

        Returns:
            Validation results dictionary
        """
        env = environment or self.current_environment
        if not env:
            return {"valid": False, "errors": ["No environment loaded"]}

        errors = []
        warnings = []

        # Check runner count
        if env.runner_count != 4:
            warnings.append(f"Runner count is {env.runner_count}, expected 4 for testing")

        # Check workflows exist
        workflow_dir = Path('.github/workflows/realistic')
        for workflow in env.workflows:
            workflow_path = workflow_dir / workflow.file
            if not workflow_path.exists():
                errors.append(f"Workflow file not found: {workflow_path}")

        # Check required configurations
        if not env.github_owner or not env.github_repo:
            errors.append("GitHub owner and repo must be specified")

        # Check test profiles
        if not env.test_profiles:
            warnings.append("No test profiles defined")

        # Validate network configuration for production
        if env.type == "production":
            if not env.network.get('proxy', {}).get('enabled'):
                warnings.append("Proxy not configured for production environment")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "environment": env.name
        }

    def get_workflow_config(self, workflow_name: str) -> Optional[WorkflowConfig]:
        """
        Get configuration for a specific workflow

        Args:
            workflow_name: Name of the workflow

        Returns:
            Workflow configuration or None
        """
        if not self.current_environment:
            return None

        for workflow in self.current_environment.workflows:
            if workflow.name == workflow_name:
                return workflow

        return None

    def get_test_profile(self, profile_name: str) -> Optional[TestProfile]:
        """
        Get a specific test profile

        Args:
            profile_name: Name of the test profile

        Returns:
            Test profile or None
        """
        if not self.current_environment:
            return None

        return self.current_environment.test_profiles.get(profile_name)

    def export_config(self, output_path: str, format: str = "json") -> None:
        """
        Export current environment configuration

        Args:
            output_path: Path to save configuration
            format: Output format (json or yaml)
        """
        if not self.current_environment:
            raise ValueError("No environment loaded")

        config = self.current_environment.raw_config

        with open(output_path, 'w') as f:
            if format == "json":
                json.dump(config, f, indent=2)
            elif format == "yaml":
                yaml.dump(config, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported configuration to {output_path}")

    def get_github_token(self) -> str:
        """
        Get GitHub token from environment variable

        Returns:
            GitHub token

        Raises:
            ValueError: If token not found
        """
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable not set")
        return token

    def apply_network_settings(self) -> None:
        """
        Apply network settings from current environment
        (proxy, SSL, etc.)
        """
        if not self.current_environment:
            return

        network_config = self.current_environment.network

        # Apply proxy settings
        if network_config.get('proxy', {}).get('enabled'):
            proxy_settings = network_config['proxy']
            if 'http_proxy' in proxy_settings:
                os.environ['HTTP_PROXY'] = proxy_settings['http_proxy']
                os.environ['http_proxy'] = proxy_settings['http_proxy']
            if 'https_proxy' in proxy_settings:
                os.environ['HTTPS_PROXY'] = proxy_settings['https_proxy']
                os.environ['https_proxy'] = proxy_settings['https_proxy']
            if 'no_proxy' in proxy_settings:
                os.environ['NO_PROXY'] = proxy_settings['no_proxy']
                os.environ['no_proxy'] = proxy_settings['no_proxy']

            logger.info("Applied proxy settings from environment configuration")

        # Apply SSL settings
        if network_config.get('ssl', {}).get('ca_bundle'):
            ca_bundle = network_config['ssl']['ca_bundle']
            os.environ['REQUESTS_CA_BUNDLE'] = ca_bundle
            os.environ['SSL_CERT_FILE'] = ca_bundle
            logger.info(f"Applied SSL CA bundle: {ca_bundle}")

    def switch_environment(self, environment_name: str) -> EnvironmentConfig:
        """
        Switch to a different environment

        Args:
            environment_name: Name of environment to switch to

        Returns:
            New environment configuration
        """
        logger.info(f"Switching from {self.current_environment.name if self.current_environment else 'None'} "
                   f"to {environment_name}")

        # Load new environment
        new_env = self.load_environment(environment_name)

        # Apply network settings
        self.apply_network_settings()

        # Validate new environment
        validation = self.validate_environment(new_env)
        if not validation['valid']:
            logger.error(f"Environment validation failed: {validation['errors']}")
        if validation['warnings']:
            logger.warning(f"Environment warnings: {validation['warnings']}")

        return new_env

    def summary(self) -> str:
        """
        Get a summary of the current environment

        Returns:
            Summary string
        """
        if not self.current_environment:
            return "No environment loaded"

        env = self.current_environment
        summary = f"""
Environment: {env.name} ({env.type})
Description: {env.description}
GitHub: {env.github_owner}/{env.github_repo}
Runners: {env.runner_count} runners with labels {env.runner_labels}
Workflows: {len(env.workflows)} available
Test Profiles: {list(env.test_profiles.keys())}
        """
        return summary.strip()


# Example usage and testing
if __name__ == "__main__":
    # Initialize switcher
    switcher = EnvironmentSwitcher()

    # List available environments
    print("Available environments:", switcher.list_environments())

    # Load AWS ECS environment
    if "aws_ecs" in switcher.list_environments():
        aws_env = switcher.load_environment("aws_ecs")
        print("\nAWS ECS Environment Summary:")
        print(switcher.summary())

        # Validate environment
        validation = switcher.validate_environment()
        print(f"\nValidation: {'✓' if validation['valid'] else '✗'}")
        if validation['errors']:
            print("Errors:", validation['errors'])
        if validation['warnings']:
            print("Warnings:", validation['warnings'])

    # Switch to OpenShift (if available)
    if "openshift_prod" in switcher.list_environments():
        print("\n" + "=" * 50)
        openshift_env = switcher.switch_environment("openshift_prod")
        print("\nOpenShift Environment Summary:")
        print(switcher.summary())

        # Get a test profile
        capacity_test = switcher.get_test_profile("capacity")
        if capacity_test:
            print(f"\nCapacity Test Profile:")
            print(f"  Duration: {capacity_test.duration_minutes} minutes")
            print(f"  Workflows: {capacity_test.workflows}")
            print(f"  Jobs/minute: {capacity_test.jobs_per_minute}")