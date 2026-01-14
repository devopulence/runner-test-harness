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
from typing import Optional, Dict, Any

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()

from src.orchestrator.environment_switcher import EnvironmentSwitcher
from src.orchestrator.scenario_runner import ScenarioRunner
from src.analysis.test_specific_analyzer import TestAnalyzerFactory
from src.orchestrator.test_run_tracker import load_test_run

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

    async def run_test(self, test_type: str, workload_override: str = None) -> bool:
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

            # Apply workload override if specified
            if workload_override:
                print(f"🔧 Overriding workload type: {workload_override}")

                # Get the profile that will be used
                profile_name = test_type
                if test_type in ['performance', 'capacity', 'stress', 'load', 'spike']:
                    # These are built-in test types that map to profiles
                    profile_name = test_type

                # Override the workload inputs for this profile
                if profile_name in self.runner.environment.test_profiles:
                    profile = self.runner.environment.test_profiles[profile_name]
                    if not hasattr(profile, 'workload_inputs') or profile.workload_inputs is None:
                        profile.workload_inputs = {}
                    profile.workload_inputs['workload_type'] = workload_override
                    profile.workload_inputs['enable_randomization'] = True

                    # Log the override
                    workload_times = {
                        'test': '30-60 seconds',
                        'light': '2-3 minutes',
                        'standard': '3-5 minutes',
                        'heavy': '5-8 minutes'
                    }
                    print(f"  Workload duration: {workload_times.get(workload_override, 'unknown')}")

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

            # Run test-specific analysis
            self._run_automatic_analysis(test_type, metrics)

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

    def _run_automatic_analysis(self, test_type: str, metrics):
        """Run test-specific analysis automatically after test completion."""
        try:
            print(f"\n🔬 Running {test_type} test analysis...")
            print("=" * 60)

            # Check if we have completed workflows to analyze
            if not metrics.queue_times and not metrics.execution_times:
                print("\n⚠️ No completed workflows to analyze yet")
                print("Workflows are still running or queued. Analysis requires completed workflows.")
                print(f"Status: {metrics.successful_workflows} completed, {metrics.failed_workflows} failed, {metrics.total_workflows} total")

                # Still save what tracking info we have
                if self.runner and self.runner.test_run_tracker:
                    test_run_id = self.runner.test_run_tracker.test_run_id
                    print(f"\nTest Run ID: {test_run_id}")
                    print("Run analysis later with:")
                    print(f"  python analyze_specific_test.py --test-run-id {test_run_id}")
                return

            # Get the appropriate analyzer (normalize test type for variants like performance_fast)
            base_test_type = test_type.split('_')[0] if '_' in test_type else test_type
            # Map validation/quick to performance analyzer
            if base_test_type in ['validation', 'quick']:
                base_test_type = 'performance'
            analyzer = TestAnalyzerFactory.get_analyzer(base_test_type)

            # Prepare metrics for analysis
            stats = metrics.calculate_statistics()
            # Use observed runner count (max concurrent jobs) instead of hardcoded config
            observed_runners = max(metrics.concurrent_jobs) if metrics.concurrent_jobs else 4
            analysis_metrics = {
                'queue_times': [qt / 60 for qt in metrics.queue_times],  # Convert to minutes
                'execution_times': [et / 60 for et in metrics.execution_times],  # Convert to minutes
                'total_times': [(qt + et) / 60 for qt, et in zip(metrics.queue_times, metrics.execution_times)] if metrics.queue_times and metrics.execution_times else [],
                'job_count': metrics.total_workflows,
                'total_workflows': metrics.total_workflows,
                'failed_workflows': metrics.failed_workflows,
                'duration_minutes': stats.get('duration_minutes', 30),
                'runner_count': observed_runners,  # Now uses observed max, not config
                'runner_utilization': [u * 100 for u in metrics.runner_utilization] if metrics.runner_utilization else []
            }

            # Run analysis
            analysis = analyzer.analyze(analysis_metrics)

            # Display key findings based on test type
            self._display_test_analysis(test_type, analysis)

            # Generate recommendations
            recommendations = analyzer.generate_recommendations(analysis)
            if recommendations:
                print("\n📋 Recommendations:")
                print("-" * 40)
                for rec in recommendations:
                    print(f"  {rec}")

            # Save analysis results
            if self.runner and self.runner.test_run_tracker:
                analysis_dir = Path(f'test_results/{self.switcher.current_environment.name if self.switcher.current_environment else "aws-ecs"}/analysis')
                analysis_dir.mkdir(parents=True, exist_ok=True)

                test_run_id = self.runner.test_run_tracker.test_run_id
                analysis_file = analysis_dir / f"{test_run_id}_analysis.json"

                import json
                with open(analysis_file, 'w') as f:
                    json.dump({
                        'test_run_id': test_run_id,
                        'test_type': test_type,
                        'analysis': analysis,
                        'metrics': analysis_metrics,
                        'recommendations': recommendations
                    }, f, indent=2)

                print(f"\n📄 Analysis saved to: {analysis_file}")

        except Exception as e:
            logger.error(f"Error running automatic analysis: {e}")
            print(f"\n⚠️ Analysis failed: {e}")

    def _display_test_analysis(self, test_type: str, analysis: Dict[str, Any]):
        """Display test-specific analysis results."""
        # Check if analysis has no data
        if analysis.get("status") == "NO_DATA":
            print(f"\n⚠️ {analysis.get('message', 'No data available for analysis')}")
            return

        # Normalize test type to base type (strip _fast, _medium, etc.)
        base_test_type = test_type.split('_')[0] if '_' in test_type else test_type
        # Map validation/quick to performance
        if base_test_type in ['validation', 'quick']:
            base_test_type = 'performance'

        if base_test_type == "performance":
            # Performance test focuses on baseline and consistency
            print("\n🎯 Performance Analysis:")
            print("-" * 40)
            if "overall_rating" in analysis:
                print(f"Overall Rating: {analysis['overall_rating']}")
            if "queue_analysis" in analysis:
                print(f"Queue Health: {analysis['queue_analysis']['health']}")
            if "execution_analysis" in analysis:
                print(f"Execution Consistency: {analysis['execution_analysis']['consistency']}")
            if "predictability" in analysis:
                print(f"Predictability: {analysis['predictability']['score']}")
                print(f"  {analysis['predictability']['interpretation']}")
            if "baseline_metrics" in analysis:
                sla = analysis['baseline_metrics']['recommended_sla']
                print(f"\nRecommended SLAs:")
                print(f"  P50: {sla['p50']:.1f} minutes")
                print(f"  P95: {sla['p95']:.1f} minutes")
                print(f"  P99: {sla['p99']:.1f} minutes")

        elif base_test_type == "load":
            # Load test focuses on degradation and sustainability
            print("\n📈 Load Test Analysis:")
            print("-" * 40)
            if "degradation_analysis" in analysis:
                deg = analysis['degradation_analysis']
                print(f"Performance Degradation: {deg['pattern']}")
                print(f"  {deg['interpretation']}")
            if "throughput_analysis" in analysis:
                tp = analysis['throughput_analysis']
                print(f"Throughput: {tp['workflows_per_hour']:.1f} workflows/hour")
                print(f"  Rating: {tp['rating']}")
            if "sustainability" in analysis:
                sus = analysis['sustainability']
                print(f"Load Sustainability: {sus['verdict']}")
                print(f"  {sus['description']}")

        elif base_test_type == "stress":
            # Stress test focuses on breaking points
            print("\n💥 Stress Test Analysis:")
            print("-" * 40)
            if "stress_metrics" in analysis:
                stress = analysis['stress_metrics']
                print(f"Max Queue Time: {stress['max_queue_time']:.1f} minutes")
                print(f"Breaking Point Reached: {'Yes' if stress['breaking_point_reached'] else 'No'}")
            if "failure_analysis" in analysis:
                fail = analysis['failure_analysis']
                print(f"Failure Rate: {fail['failure_rate']:.1f}%")
                print(f"System Resilience: {fail['system_resilience']}")
            if "stress_handling" in analysis:
                handling = analysis['stress_handling']
                print(f"Stress Handling: {handling['rating']}")
                print(f"  {handling['description']}")

        elif base_test_type == "capacity":
            # Capacity test focuses on maximum throughput
            print("\n⚡ Capacity Analysis:")
            print("-" * 40)
            if "capacity_metrics" in analysis:
                cap = analysis['capacity_metrics']
                print(f"Actual Throughput: {cap['actual_throughput']:.2f} workflows/min")
                print(f"Efficiency: {cap['efficiency_percent']:.1f}%")
                print(f"Capacity Usage: {cap['capacity_utilized']}")
            if "saturation_analysis" in analysis:
                sat = analysis['saturation_analysis']
                print(f"Average Utilization: {sat['average_utilization']:.1f}%")
                print(f"Saturation State: {sat['saturation_state']}")
            if "optimization" in analysis:
                opt = analysis['optimization']
                print(f"Runner Optimization: {opt['recommendation']}")

        elif base_test_type == "spike":
            # Spike test focuses on elasticity
            print("\n⚡ Spike Test Analysis:")
            print("-" * 40)

            # Get spike peak for context
            spike_peak = analysis.get('spike_response', {}).get('spike_peak', 0)
            overall_rating = analysis.get('spike_handling_rating', '')

            if "spike_response" in analysis:
                spike = analysis['spike_response']
                # spike_peak is in MINUTES (converted before analysis)
                # Only show multiplier if it's meaningful (spike peak was significant)
                if spike_peak > 1:  # More than 1 minute queue during spike
                    print(f"Max Queue During Spike: {spike_peak:.1f} minutes")
                    print(f"Spike Impact: {spike['response_multiplier']:.1f}x baseline")
                else:
                    print(f"Max Queue During Spike: {spike_peak * 60:.0f} seconds")

            # Only show recovery quality if spike had significant impact
            if "recovery" in analysis and spike_peak > 1:
                rec = analysis['recovery']
                print(f"Recovery Quality: {rec['recovery_quality']}")

            if "elasticity" in analysis:
                elast = analysis['elasticity']
                print(f"System Elasticity: {elast['rating']}")
                print(f"  {elast['description']}")

            if overall_rating:
                print(f"Overall: {overall_rating}")

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

        if 'concurrent_jobs' in stats:
            print(f"\nConcurrent Jobs (Runners Active):")
            cj = stats['concurrent_jobs']
            print(f"  Max Observed: {cj['max']}")
            print(f"  Average: {cj['mean']:.1f}")

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
        '-w', '--workload',
        choices=['test', 'light', 'standard', 'heavy'],
        help='Override workload type (test=30-60s, light=2-3m, standard=3-5m, heavy=5-8m)'
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
        success = asyncio.run(harness.run_test(args.test, args.workload))
        sys.exit(0 if success else 1)
    elif args.profile:
        success = asyncio.run(harness.run_test(args.profile, args.workload))
        sys.exit(0 if success else 1)
    else:
        # Default to interactive if no test specified
        harness.interactive_mode()


if __name__ == "__main__":
    main()