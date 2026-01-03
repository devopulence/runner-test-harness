#!/usr/bin/env python3
"""
Main test runner for GitHub Runner Performance Test Harness
Portable testing for both AWS ECS and OpenShift environments
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.orchestrator.environment_switcher import EnvironmentSwitcher
from src.orchestrator.scenario_runner import ScenarioRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestHarness:
    """Main test harness for running performance tests"""

    def __init__(self):
        """Initialize the test harness"""
        self.switcher = EnvironmentSwitcher()
        self.runner: Optional[ScenarioRunner] = None
        self.github_token: Optional[str] = None

    def setup(self, environment_name: str) -> bool:
        """
        Setup the test harness for a specific environment

        Args:
            environment_name: Name of environment to use

        Returns:
            True if setup successful, False otherwise
        """
        try:
            # Load environment
            logger.info(f"Loading environment: {environment_name}")
            environment = self.switcher.load_environment(environment_name)

            # Validate environment
            validation = self.switcher.validate_environment(environment)
            if not validation['valid']:
                logger.error(f"Environment validation failed: {validation['errors']}")
                return False

            if validation['warnings']:
                logger.warning(f"Environment warnings: {validation['warnings']}")

            # Apply network settings
            self.switcher.apply_network_settings()

            # Get GitHub token
            self.github_token = os.getenv('GITHUB_TOKEN')
            if not self.github_token:
                logger.error("GITHUB_TOKEN environment variable not set")
                print("\nPlease set your GitHub token:")
                print("  export GITHUB_TOKEN='your_github_pat_token'")
                return False

            # Create scenario runner
            self.runner = ScenarioRunner(environment, self.github_token)

            logger.info("Test harness setup complete")
            print("\n" + "=" * 60)
            print(self.switcher.summary())
            print("=" * 60 + "\n")

            return True

        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False

    async def run_test(self, test_type: str) -> bool:
        """
        Run a specific test type

        Args:
            test_type: Type of test to run

        Returns:
            True if test successful, False otherwise
        """
        if not self.runner:
            logger.error("Test harness not initialized")
            return False

        try:
            logger.info(f"Starting {test_type} test")
            print(f"\n🚀 Running {test_type} test...")
            print("Press Ctrl+C to abort\n")

            # Map test types to runner methods
            test_methods = {
                'performance': self.runner.run_performance_test,
                'capacity': self.runner.run_capacity_test,
                'stress': self.runner.run_stress_test,
                'load': self.runner.run_load_test,
                'spike': self.runner.run_spike_test
            }

            if test_type not in test_methods:
                # Try to run as a test profile
                metrics = await self.runner.run_test_profile(test_type)
            else:
                # Run predefined test
                metrics = await test_methods[test_type]()

            # Generate report
            report_path = self.runner.generate_report(metrics)

            # Display results
            self._display_results(metrics)

            print(f"\n✅ Test complete!")
            print(f"📊 Report saved to: {report_path}")

            return True

        except KeyboardInterrupt:
            logger.warning("Test aborted by user")
            if self.runner:
                self.runner.abort_test()
            return False
        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False

    def _display_results(self, metrics):
        """Display test results summary"""
        stats = metrics.calculate_statistics()

        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)

        print(f"\nWorkflows:")
        print(f"  Total: {stats['total_workflows']}")
        print(f"  Successful: {stats['successful_workflows']}")
        print(f"  Failed: {stats['failed_workflows']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")

        if 'queue_time' in stats:
            print(f"\nQueue Time (seconds):")
            qt = stats['queue_time']
            print(f"  Min: {qt['min']:.1f}")
            print(f"  Max: {qt['max']:.1f}")
            print(f"  Mean: {qt['mean']:.1f}")
            print(f"  Median: {qt['median']:.1f}")
            print(f"  P95: {qt['p95']:.1f}")

        if 'execution_time' in stats:
            print(f"\nExecution Time (seconds):")
            et = stats['execution_time']
            print(f"  Min: {et['min']:.1f}")
            print(f"  Max: {et['max']:.1f}")
            print(f"  Mean: {et['mean']:.1f}")
            print(f"  Median: {et['median']:.1f}")
            print(f"  P95: {et['p95']:.1f}")

        if 'throughput' in stats:
            print(f"\nThroughput:")
            tp = stats['throughput']
            print(f"  Jobs per hour: {tp['total_jobs_per_hour']:.1f}")

        if 'runner_utilization' in stats:
            print(f"\nRunner Utilization:")
            ru = stats['runner_utilization']
            print(f"  Average: {ru['mean']:.1%}")
            print(f"  Peak: {ru['max']:.1%}")

        print(f"\nTest Duration: {stats['duration_minutes']:.1f} minutes")

    def list_tests(self):
        """List available tests for current environment"""
        if not self.switcher.current_environment:
            print("No environment loaded")
            return

        env = self.switcher.current_environment
        print("\nAvailable Test Profiles:")
        print("-" * 40)

        for name, profile in env.test_profiles.items():
            print(f"\n{name}:")
            print(f"  Duration: {profile.duration_minutes} minutes")
            print(f"  Pattern: {profile.dispatch_pattern}")
            print(f"  Workflows: {', '.join(profile.workflows)}")

            if profile.jobs_per_minute:
                print(f"  Rate: {profile.jobs_per_minute} jobs/minute")

    def interactive_mode(self):
        """Run in interactive mode"""
        print("\n" + "=" * 60)
        print("GitHub Runner Performance Test Harness")
        print("=" * 60)

        # List environments
        environments = self.switcher.list_environments()
        print("\nAvailable Environments:")
        for i, env in enumerate(environments, 1):
            print(f"  {i}. {env}")

        # Select environment
        while True:
            try:
                choice = input("\nSelect environment (number or name): ").strip()
                if choice.isdigit():
                    env_name = environments[int(choice) - 1]
                else:
                    env_name = choice

                if self.setup(env_name):
                    break
            except (ValueError, IndexError):
                print("Invalid selection")

        # Show available tests
        self.list_tests()

        # Select and run test
        while True:
            test_name = input("\nEnter test name (or 'quit'): ").strip()
            if test_name.lower() == 'quit':
                break

            asyncio.run(self.run_test(test_name))

            if input("\nRun another test? (y/n): ").lower() != 'y':
                break


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="GitHub Runner Performance Test Harness"
    )
    parser.add_argument(
        '-e', '--environment',
        help='Environment to use (aws_ecs or openshift_prod)',
        default='aws_ecs'
    )
    parser.add_argument(
        '-t', '--test',
        help='Test type to run (performance, capacity, stress, load, spike)',
        choices=['performance', 'capacity', 'stress', 'load', 'spike']
    )
    parser.add_argument(
        '-p', '--profile',
        help='Test profile name from environment config'
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List available tests for environment'
    )
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration without running tests'
    )

    args = parser.parse_args()

    # Create harness
    harness = TestHarness()

    # Interactive mode
    if args.interactive:
        harness.interactive_mode()
        return

    # Setup environment
    if not harness.setup(args.environment):
        sys.exit(1)

    # List tests
    if args.list:
        harness.list_tests()
        return

    # Dry run
    if args.dry_run:
        print("\n✅ Configuration validated successfully")
        print("Ready to run tests")
        return

    # Run specific test
    if args.test:
        success = asyncio.run(harness.run_test(args.test))
        sys.exit(0 if success else 1)
    elif args.profile:
        success = asyncio.run(harness.run_test(args.profile))
        sys.exit(0 if success else 1)
    else:
        # Default to interactive if no test specified
        harness.interactive_mode()


if __name__ == "__main__":
    main()