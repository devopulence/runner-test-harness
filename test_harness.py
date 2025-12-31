#!/usr/bin/env python3
"""
GitHub Runner Performance Testing Harness - Main CLI
Orchestrates performance testing of GitHub runners
"""

import asyncio
import argparse
import sys
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import logging
from pathlib import Path

# Import our modules
from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest
from metrics_collector import MetricsCollector, MetricsStorage, MetricsAnalyzer, WorkflowMetrics
from config_manager import ConfigManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestHarness:
    """Main test harness orchestrator"""

    def __init__(self, config_file: str = "config.yaml", environment: Optional[str] = None):
        """Initialize test harness"""
        self.config = ConfigManager(config_file, environment)
        self.metrics_storage = MetricsStorage(str(self.config.storage.metrics_path))
        self.start_time = None
        self.test_results = {}

    async def run_performance_test(self) -> Dict:
        """Run performance baseline test"""
        logger.info("🚀 Starting Performance Test")

        scenario = self.config.get_test_scenario('performance')
        if not scenario or not scenario.enabled:
            logger.warning("Performance test not enabled")
            return {}

        workflow_count = scenario.get('workflow_count', 10)
        workflow_types = scenario.get('workflow_types', ['simple'])
        sequential = scenario.get('sequential', True)
        interval = scenario.get('interval', 30)

        test_id = f"perf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            rate_limit_per_second=self.config.github.rate_limit
        ) as dispatcher:
            all_metrics = []

            for workflow_type in workflow_types:
                logger.info(f"Testing workflow type: {workflow_type}")

                # Create dispatch requests
                requests = []
                for i in range(workflow_count):
                    workflow_file = self.config.get_workflow_file(workflow_type)
                    if not workflow_file:
                        logger.error(f"Workflow file not found for type: {workflow_type}")
                        continue

                    # Extract just the filename for the workflow_id
                    workflow_id = Path(workflow_file).name

                    requests.append(WorkflowDispatchRequest(
                        owner=self.config.github.owner,
                        repo=self.config.github.repo,
                        workflow_id=workflow_id,
                        ref="main",
                        test_id=f"{test_id}_{workflow_type}_{i}",
                        inputs={"complexity": workflow_type}
                    ))

                if sequential:
                    # Run sequentially with interval
                    for req in requests:
                        logger.info(f"Dispatching {req.workflow_id} (sequential)")
                        run_id = await dispatcher.dispatch_workflow(req)

                        if run_id:
                            # Monitor this run
                            metrics = await dispatcher.monitor_run(
                                req.owner, req.repo, run_id,
                                timeout_seconds=self.config.monitoring.workflow_timeout
                            )
                            all_metrics.append(metrics)

                        # Wait for interval
                        if interval > 0:
                            await asyncio.sleep(interval)
                else:
                    # Run in batch
                    logger.info(f"Dispatching {len(requests)} workflows (batch)")
                    dispatch_results = await dispatcher.dispatch_batch(requests)

                    # Monitor all runs
                    runs_to_monitor = [
                        (req.owner, req.repo, run_id)
                        for req, run_id in dispatch_results
                        if run_id is not None
                    ]

                    if runs_to_monitor:
                        batch_metrics = await dispatcher.monitor_batch(
                            runs_to_monitor,
                            timeout_seconds=self.config.monitoring.workflow_timeout
                        )
                        all_metrics.extend(batch_metrics)

            # Analyze results
            if all_metrics:
                # Convert dispatcher metrics to our WorkflowMetrics format
                workflow_metrics = self._convert_metrics(all_metrics)

                # Store metrics
                for metric in workflow_metrics:
                    self.metrics_storage.add_metric(metric)

                # Aggregate and analyze
                aggregated = MetricsAnalyzer.aggregate_metrics(
                    workflow_metrics, test_id, "performance"
                )

                # Print summary
                MetricsAnalyzer.print_summary(aggregated)

                # Save metrics
                metrics_file = self.metrics_storage.save_metrics()
                logger.info(f"Metrics saved to: {metrics_file}")

                return aggregated.to_dict()

        return {}

    async def run_load_test(self) -> Dict:
        """Run load test with steady-state load"""
        logger.info("🔥 Starting Load Test")

        scenario = self.config.get_test_scenario('load')
        if not scenario or not scenario.enabled:
            logger.warning("Load test not enabled")
            return {}

        steady_state = scenario.get('steady_state', {})
        workflows_per_minute = steady_state.get('workflows_per_minute', 10)
        duration_minutes = steady_state.get('duration_minutes', 30)
        workflow_distribution = steady_state.get('workflow_distribution', {'simple': 1.0})

        test_id = f"load_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            rate_limit_per_second=self.config.github.rate_limit
        ) as dispatcher:
            end_time = time.time() + (duration_minutes * 60)
            all_run_ids = []
            workflow_counter = 0

            logger.info(f"Generating load: {workflows_per_minute} workflows/min for {duration_minutes} minutes")

            while time.time() < end_time:
                minute_start = time.time()

                # Dispatch workflows for this minute
                for i in range(workflows_per_minute):
                    # Select workflow type based on distribution
                    workflow_type = self._select_workflow_type(workflow_distribution)
                    workflow_file = self.config.get_workflow_file(workflow_type)

                    if not workflow_file:
                        continue

                    workflow_id = Path(workflow_file).name

                    request = WorkflowDispatchRequest(
                        owner=self.config.github.owner,
                        repo=self.config.github.repo,
                        workflow_id=workflow_id,
                        ref="main",
                        test_id=f"{test_id}_{workflow_counter}",
                        inputs={"complexity": workflow_type}
                    )

                    # Dispatch asynchronously
                    run_id = await dispatcher.dispatch_workflow(request)
                    if run_id:
                        all_run_ids.append((request.owner, request.repo, run_id))

                    workflow_counter += 1

                    # Space out dispatches within the minute
                    sleep_time = 60 / workflows_per_minute
                    await asyncio.sleep(sleep_time)

                # Log progress
                elapsed = (time.time() - (end_time - duration_minutes * 60)) / 60
                logger.info(f"Progress: {elapsed:.1f}/{duration_minutes} minutes, "
                           f"Dispatched: {workflow_counter} workflows")

            # Monitor all runs
            logger.info(f"Monitoring {len(all_run_ids)} workflow runs...")

            async with MetricsCollector(self.config.github.token, self.metrics_storage) as collector:
                metrics = await collector.collect_batch_metrics(all_run_ids)

                if metrics:
                    # Aggregate results
                    aggregated = MetricsAnalyzer.aggregate_metrics(metrics, test_id, "load")
                    MetricsAnalyzer.print_summary(aggregated)

                    # Save metrics
                    metrics_file = self.metrics_storage.save_metrics()
                    logger.info(f"Metrics saved to: {metrics_file}")

                    return aggregated.to_dict()

        return {}

    async def run_stress_test(self) -> Dict:
        """Run stress test to find breaking point"""
        logger.info("💥 Starting Stress Test")

        scenario = self.config.get_test_scenario('stress')
        if not scenario or not scenario.enabled:
            logger.warning("Stress test not enabled")
            return {}

        initial_wpm = scenario.get('initial_workflows_per_minute', 5)
        increment = scenario.get('increment', 5)
        step_duration = scenario.get('step_duration_minutes', 10)
        max_wpm = scenario.get('max_workflows_per_minute', 100)

        test_id = f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metrics_storage.set_test_id(test_id)

        current_wpm = initial_wpm
        breaking_point = None

        async with GitHubWorkflowDispatcher(
            token=self.config.github.token,
            rate_limit_per_second=self.config.github.rate_limit
        ) as dispatcher:

            while current_wpm <= max_wpm:
                logger.info(f"Testing load level: {current_wpm} workflows/min")

                step_runs = []
                step_start = time.time()
                step_end = step_start + (step_duration * 60)

                # Generate load for this step
                workflow_counter = 0
                while time.time() < step_end:
                    # Dispatch workflows at current rate
                    workflows_this_minute = current_wpm

                    for i in range(workflows_this_minute):
                        workflow_file = self.config.get_workflow_file('simple')
                        if not workflow_file:
                            continue

                        request = WorkflowDispatchRequest(
                            owner=self.config.github.owner,
                            repo=self.config.github.repo,
                            workflow_id=Path(workflow_file).name,
                            ref="main",
                            test_id=f"{test_id}_step{current_wpm}_{workflow_counter}"
                        )

                        run_id = await dispatcher.dispatch_workflow(request)
                        if run_id:
                            step_runs.append((request.owner, request.repo, run_id))

                        workflow_counter += 1

                        # Space out dispatches
                        await asyncio.sleep(60 / workflows_this_minute)

                    # Check if we've reached the step duration
                    if time.time() >= step_end:
                        break

                # Collect metrics for this step
                logger.info(f"Collecting metrics for {len(step_runs)} runs at {current_wpm} wpm...")

                async with MetricsCollector(self.config.github.token, self.metrics_storage) as collector:
                    metrics = await collector.collect_batch_metrics(step_runs)

                    if metrics:
                        # Check failure conditions
                        aggregated = MetricsAnalyzer.aggregate_metrics(
                            metrics, f"{test_id}_step{current_wpm}", "stress"
                        )

                        # Check if breaking point reached
                        if self._check_breaking_point(aggregated, scenario):
                            breaking_point = current_wpm
                            logger.warning(f"Breaking point found at {breaking_point} workflows/min")
                            break

                # Increase load
                current_wpm += increment

            # Final results
            result = {
                "test_id": test_id,
                "test_type": "stress",
                "initial_wpm": initial_wpm,
                "max_tested_wpm": current_wpm - increment,
                "breaking_point": breaking_point,
                "timestamp": datetime.now().isoformat()
            }

            # Save metrics
            metrics_file = self.metrics_storage.save_metrics()
            logger.info(f"Metrics saved to: {metrics_file}")

            return result

        return {}

    async def run_test_suite(self, test_types: Optional[List[str]] = None):
        """Run complete test suite"""
        logger.info("🎯 Starting Test Suite")

        if test_types is None:
            test_types = self.config.get_enabled_scenarios()

        self.start_time = time.time()
        results = {}

        # Run each test type
        for test_type in test_types:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running {test_type.upper()} test")
            logger.info('='*60)

            try:
                if test_type == 'performance':
                    results[test_type] = await self.run_performance_test()
                elif test_type == 'load':
                    results[test_type] = await self.run_load_test()
                elif test_type == 'stress':
                    results[test_type] = await self.run_stress_test()
                else:
                    logger.warning(f"Test type not implemented: {test_type}")

            except Exception as e:
                logger.error(f"Error running {test_type} test: {str(e)}")
                if not self.config.execution.get('continue_on_error', True):
                    break

        # Save final results
        self._save_results(results)

        # Print final summary
        self._print_final_summary(results)

        return results

    def _convert_metrics(self, dispatcher_metrics: List) -> List[WorkflowMetrics]:
        """Convert dispatcher metrics to WorkflowMetrics format"""
        converted = []
        for dm in dispatcher_metrics:
            if dm:  # Check if not None
                wm = WorkflowMetrics(
                    run_id=dm.run_id,
                    workflow_id=dm.workflow_id,
                    test_id=dm.test_id,
                    status=dm.status,
                    conclusion=dm.conclusion,
                    success=dm.conclusion == "success" if dm.conclusion else False,
                    created_at=dm.created_at,
                    started_at=dm.started_at,
                    completed_at=dm.completed_at,
                    queue_time=dm.queue_time_seconds,
                    execution_time=dm.execution_time_seconds,
                    total_time=(dm.queue_time_seconds or 0) + (dm.execution_time_seconds or 0)
                        if dm.queue_time_seconds and dm.execution_time_seconds else None,
                    html_url=dm.html_url
                )
                converted.append(wm)
        return converted

    def _select_workflow_type(self, distribution: Dict[str, float]) -> str:
        """Select workflow type based on distribution"""
        import random
        rand = random.random()
        cumulative = 0

        for workflow_type, probability in distribution.items():
            cumulative += probability
            if rand <= cumulative:
                return workflow_type

        # Default to first type
        return list(distribution.keys())[0] if distribution else 'simple'

    def _check_breaking_point(self, metrics, scenario) -> bool:
        """Check if breaking point conditions are met"""
        thresholds = scenario.get('failure_thresholds', {})

        conditions_met = []

        # Check queue time
        if metrics.avg_queue_time > thresholds.get('queue_time_seconds', 300):
            conditions_met.append("queue_time")

        # Check failure rate
        if metrics.failure_rate > thresholds.get('failure_rate_percent', 10):
            conditions_met.append("failure_rate")

        # Breaking point if any condition met
        if conditions_met:
            logger.warning(f"Breaking point conditions met: {conditions_met}")
            return True

        return False

    def _save_results(self, results: Dict):
        """Save test results to file"""
        results_file = self.config.storage.results_path / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Results saved to: {results_file}")

    def _print_final_summary(self, results: Dict):
        """Print final test summary"""
        duration = time.time() - self.start_time if self.start_time else 0

        print("\n" + "="*60)
        print("TEST SUITE COMPLETED")
        print("="*60)
        print(f"Total Duration: {duration/60:.1f} minutes")
        print(f"Tests Executed: {len(results)}")

        for test_type, result in results.items():
            if result:
                print(f"\n{test_type.upper()}:")
                if isinstance(result, dict):
                    if 'success_rate' in result:
                        print(f"  - Success Rate: {result['success_rate']:.1f}%")
                    if 'avg_queue_time' in result:
                        print(f"  - Avg Queue Time: {result['avg_queue_time']:.1f}s")
                    if 'breaking_point' in result:
                        print(f"  - Breaking Point: {result['breaking_point']} workflows/min")

        print("="*60 + "\n")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="GitHub Runner Performance Testing Harness"
    )

    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Configuration file path'
    )

    parser.add_argument(
        '--environment',
        choices=['development', 'production', 'openshift'],
        help='Environment configuration to use'
    )

    parser.add_argument(
        '--test',
        choices=['performance', 'load', 'stress', 'suite'],
        default='suite',
        help='Test type to run'
    )

    parser.add_argument(
        '--list-tests',
        action='store_true',
        help='List available test types'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate configuration only'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (no actual dispatches)'
    )

    args = parser.parse_args()

    # Create harness
    try:
        harness = TestHarness(args.config, args.environment)
    except Exception as e:
        logger.error(f"Failed to initialize harness: {str(e)}")
        sys.exit(1)

    # Handle dry-run
    if args.dry_run:
        harness.config.execution['dry_run'] = True

    # List tests
    if args.list_tests:
        print("\nAvailable test types:")
        for test_type in harness.config.get_enabled_scenarios():
            print(f"  - {test_type}")
        sys.exit(0)

    # Validate configuration
    if args.validate:
        issues = harness.config.validate_config()
        if issues:
            print("Configuration issues:")
            for issue in issues:
                print(f"  ❌ {issue}")
            sys.exit(1)
        else:
            print("✅ Configuration valid!")
            harness.config.print_config_summary()
            sys.exit(0)

    # Print configuration summary
    harness.config.print_config_summary()

    # Save configuration snapshot
    harness.config.save_config_snapshot()

    # Run tests
    try:
        if args.test == 'suite':
            asyncio.run(harness.run_test_suite())
        elif args.test == 'performance':
            asyncio.run(harness.run_performance_test())
        elif args.test == 'load':
            asyncio.run(harness.run_load_test())
        elif args.test == 'stress':
            asyncio.run(harness.run_stress_test())

    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()