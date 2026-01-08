#!/usr/bin/env python3
"""
Debug single workflow execution to investigate timing issue
"""
import os
import json
import time
from main import trigger_workflow_dispatch

# Get GitHub token
token = os.getenv('GITHUB_TOKEN')
if not token:
    print("Error: GITHUB_TOKEN not set")
    exit(1)

# Dispatch a single standard workflow
print("Dispatching single build_job with 'standard' workload...")
print("Expected duration: 8-15 minutes")
print("Actual duration from performance test: 18-27 minutes")
print("-" * 60)

# Record dispatch time
dispatch_time = time.time()

# Trigger workflow with standard workload
trigger_workflow_dispatch(
    owner="devopulence",
    repo="pythonProject",
    workflow_id_or_filename="build_job.yml",
    ref="main",
    inputs={
        "workload_type": "standard",
        "enable_randomization": "true",
        "job_name": "debug_timing"
    },
    token=token
)

print(f"Workflow dispatched at: {time.strftime('%H:%M:%S UTC')}")
print("\nMonitor progress with:")
print("  python capture_current_metrics.py")
print("\nOr watch the GitHub Actions UI")
print("\nExpected completion in 8-15 minutes if working correctly")
print("Previous actual: 18-27 minutes")
