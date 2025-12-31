#!/usr/bin/env python3
"""
Quick test script to verify the GitHub Runner Performance Testing Harness is working
Tests basic workflow dispatch and metrics collection with your repository
"""

import asyncio
import os
import sys
from datetime import datetime
import logging

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dispatcher import GitHubWorkflowDispatcher, WorkflowDispatchRequest
from metrics_collector import MetricsCollector, MetricsStorage, MetricsAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def quick_test():
    """Run a quick test with 1-2 workflows to verify everything works"""

    # Check for GitHub token
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        logger.error("❌ GITHUB_TOKEN environment variable not set")
        print("\nPlease set your GitHub token:")
        print("  export GITHUB_TOKEN='your_token_here'")
        return False

    print("\n" + "="*60)
    print("GITHUB RUNNER QUICK TEST")
    print("="*60)
    print(f"Repository: Devopulence/test-workflows")
    print(f"Timestamp: {datetime.now()}")
    print("="*60 + "\n")

    test_id = f"quick_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async with GitHubWorkflowDispatcher(token, max_concurrent=2, rate_limit_per_second=5) as dispatcher:
        # Check API rate limit first
        print("📊 Checking GitHub API rate limit...")
        rate_info = await dispatcher.get_rate_limit()

        if rate_info and rate_info.get('remaining', 0) < 100:
            logger.warning(f"⚠️  Low API rate limit: {rate_info['remaining']} remaining")

        # Create a simple test workflow dispatch
        print("\n🚀 Dispatching test workflow...")

        request = WorkflowDispatchRequest(
            owner="Devopulence",
            repo="test-workflows",
            workflow_id="simple_test.yml",
            ref="main",
            test_id=test_id,
            inputs={
                "test_id": test_id,
                "complexity": "simple"
            }
        )

        # Dispatch the workflow
        run_id = await dispatcher.dispatch_workflow(request)

        if not run_id:
            logger.error("❌ Failed to dispatch workflow")
            print("\nPossible issues:")
            print("  1. Check that the repository exists: https://github.com/Devopulence/test-workflows")
            print("  2. Ensure workflows are uploaded (run: bash setup_workflows.sh)")
            print("  3. Verify your token has 'workflow' permissions")
            return False

        print(f"✅ Workflow dispatched successfully! Run ID: {run_id}")
        print(f"📍 View run: https://github.com/Devopulence/test-workflows/actions/runs/{run_id}")

        # Monitor the workflow
        print("\n⏳ Monitoring workflow execution...")
        print("   This will take about 30-60 seconds for a simple workflow")

        workflow_run = await dispatcher.monitor_run(
            "Devopulence",
            "test-workflows",
            run_id,
            timeout_seconds=300  # 5 minute timeout for quick test
        )

        # Display results
        if workflow_run:
            print(f"\n📊 Workflow Results:")
            print(f"   Status: {workflow_run.status}")
            print(f"   Conclusion: {workflow_run.conclusion}")

            if workflow_run.queue_time_seconds:
                print(f"   Queue Time: {workflow_run.queue_time_seconds:.1f} seconds")

            if workflow_run.execution_time_seconds:
                print(f"   Execution Time: {workflow_run.execution_time_seconds:.1f} seconds")

            if workflow_run.conclusion == "success":
                print("\n✅ SUCCESS! The testing harness is working correctly!")
                print("\nYou can now run more comprehensive tests:")
                print("  - Performance test: python test_harness.py --test performance")
                print("  - Load test: python test_harness.py --test load")
                print("  - Full suite: python test_harness.py")
                return True
            else:
                print(f"\n⚠️  Workflow completed with status: {workflow_run.conclusion}")
                print(f"Check the run for details: {workflow_run.html_url}")
                return False
        else:
            print("\n⚠️  Workflow monitoring timed out or failed")
            return False


async def test_repository_access():
    """Test if we can access the repository"""
    import aiohttp

    token = os.getenv('GITHUB_TOKEN')
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Check repository
        url = "https://api.github.com/repos/Devopulence/test-workflows"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ Repository found: {data['full_name']}")
                print(f"   Description: {data.get('description', 'No description')}")
                return True
            elif response.status == 404:
                print("❌ Repository not found or not accessible")
                print("   Run: bash setup_workflows.sh to create it")
                return False
            else:
                print(f"❌ Unexpected status: {response.status}")
                return False


async def check_workflows():
    """Check if workflows are present in the repository"""
    import aiohttp

    token = os.getenv('GITHUB_TOKEN')
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        # Check for workflows
        url = "https://api.github.com/repos/Devopulence/test-workflows/actions/workflows"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                workflows = data.get('workflows', [])

                if workflows:
                    print(f"✅ Found {len(workflows)} workflow(s):")
                    for wf in workflows:
                        print(f"   - {wf['name']} ({wf['path']})")
                    return True
                else:
                    print("⚠️  No workflows found in repository")
                    print("   Run: bash setup_workflows.sh to upload them")
                    return False
            else:
                print(f"❌ Could not check workflows: {response.status}")
                return False


async def main():
    """Main test function"""
    print("\n🔍 Pre-flight checks...")
    print("-" * 40)

    # Check GitHub token
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN not set")
        print("\nSet your token with:")
        print("  export GITHUB_TOKEN='your_github_token'")
        sys.exit(1)
    else:
        print("✅ GitHub token found")

    # Check repository access
    if not await test_repository_access():
        sys.exit(1)

    # Check workflows
    if not await check_workflows():
        print("\n⚠️  No workflows found. Would you like to set them up?")
        print("Run: bash setup_workflows.sh")
        sys.exit(1)

    # Run quick test
    print("\n" + "-" * 40)
    success = await quick_test()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)