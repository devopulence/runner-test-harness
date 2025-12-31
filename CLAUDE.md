# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a GitHub Runner Performance Testing Harness designed to comprehensively test the performance, scalability, and capacity of GitHub workflow runners.

### Current Status (Dec 31, 2024)
- **Phase**: Transitioning from public runners to ECS Fargate deployment
- **Key Decision**: Using ECS Fargate instead of OpenShift for self-hosted runners
- **Architecture**: 4 ECS Fargate tasks (hard limit) as GitHub runners
- **Testing Method**: Sleep-based workflows for controlled timing

### Critical Constraints
- **4 Runner Limit**: Both OpenShift and ECS environments limited to exactly 4 runners
- **1 Runner = 1 Job**: Each runner can only execute one job at a time
- **Repository**: Currently using `Devopulence/test-workflows` for testing

### Testing Scope
The harness enables the following types of performance testing:
- **Performance Testing**: Baseline performance metrics
- **Scalability Testing**: How runners handle increasing workloads
- **Load Testing**: Behavior under expected load conditions
- **Spike Testing**: Response to sudden load increases
- **Stress Testing**: Breaking point identification
- **Volume Testing**: Large-scale data processing capabilities
- **Capacity Testing**: Maximum concurrent workflow handling

### Implementation Strategy
1. **Current**: Testing on public GitHub runners with artificial 4-runner limit
2. **Next**: Deploy 4 ECS Fargate runners via Terraform
3. **Testing**: Use `runner_test.yml` with configurable sleep durations
4. **Metrics**: Queue time, execution time, throughput analysis

### Core Component
The `main.py` script provides the foundation for triggering GitHub Actions workflows via the workflow_dispatch REST API, serving as the primary mechanism for generating test load on runners.

## Current Infrastructure Status

### Terraform Deployment (In Progress)
Located in `terraform/` directory:
1. **`00-provider.tf`** - AWS provider configuration
2. **`01-network.tf`** - VPC, Subnet, Internet Gateway, Security Group (DEPLOY FIRST)
3. **`ecs-github-runners.tf`** - Full ECS setup (needs breaking down into modules)

**Next Steps for Terraform**:
- User needs to provide AWS Account ID and Region
- Deploy network foundation first
- Then add IAM roles, Secrets Manager, and ECS resources

### Test Workflows for ECS
- **`runner_test.yml`** - Configurable sleep-based workflow
  - Parameters: `sleep_duration` (seconds), `job_count` (1-20), `job_type` (parallel/sequential)
  - Perfect for testing 4-runner constraint behavior

### Testing Scripts
- **`test_ecs_simple.py`** - Simple ECS runner tests with sleep workflows
- **`test_4_runners.py`** - Simulates 4-runner constraint on public runners
- **`demonstrate_4_runner_limit.py`** - Visual demonstration of runner limits

## Key Commands

### Running the Script

```bash
# Basic usage - trigger a workflow
python main.py --owner <org_or_user> --repo <repository> --workflow <workflow_file.yml>

# With custom branch/tag
python main.py --owner pnc-sandbox --repo ghe-test --workflow k8s.yml --ref develop

# With workflow inputs (JSON format)
python main.py --owner pnc-sandbox --repo ghe-test --workflow deploy.yml --inputs '{"environment":"staging","version":"1.2.3"}'

# Using environment token instead of CLI arg
export GITHUB_TOKEN="your_pat_token"
python main.py --owner pnc-sandbox --repo ghe-test --workflow build.yml
```

### Environment Configuration

The script supports several environment variables for enterprise/corporate environments:

- `GITHUB_TOKEN`: GitHub Personal Access Token (PAT) with appropriate permissions
- `REQUESTS_CA_BUNDLE` or `SSL_CERT_FILE`: Path to corporate CA certificate bundle for TLS interception
- `HTTP_PROXY` / `HTTPS_PROXY`: Corporate proxy URLs if needed

## Architecture

The codebase consists of a single module with clear separation of concerns:

1. **`trigger_workflow_dispatch()`** - Core function that handles the GitHub API interaction
   - Implements retry logic for network resilience (5 retries with exponential backoff)
   - Supports corporate proxy and custom CA certificates
   - Returns HTTP 204 on success (standard GitHub API behavior for workflow dispatch)

2. **CLI Interface** - Argument parsing and execution wrapper
   - Validates and parses JSON inputs
   - Automatically detects proxy and CA settings from environment
   - Provides clear success/error messaging

## Key Implementation Details

- **Authentication**: Uses Bearer token authentication with GitHub API v2022-11-28
- **Error Handling**: Robust retry mechanism for transient failures (429, 5xx status codes)
- **Network Configuration**: Supports corporate environments with proxy and custom CA certificates
- **Workflow Identification**: Accepts either workflow filename (e.g., 'deploy.yml') or numeric workflow ID

## Dependencies

The project uses the following Python packages:
- `requests`: HTTP client library for API calls
- `urllib3`: For retry configuration
- Standard library modules: `os`, `sys`, `json`, `argparse`

## Development Environment

- Python 3.11+ required
- PyCharm IDE project configuration present (.idea directory)
- Virtual environment configured (.venv directory)
- MCP servers configured for Context7 API and local knowledge graph

## IMMEDIATE NEXT STEPS (for future sessions)

### 1. Complete ECS Fargate Deployment
**Status**: Network foundation ready, awaiting AWS account details
**Need from user**:
- AWS Account ID (12-digit)
- AWS Region (e.g., us-east-1)

**Then**:
```bash
cd terraform
# Deploy network first
terraform apply -target=aws_vpc.main [... see STEP_BY_STEP.md]
# Then deploy IAM, Secrets, ECS
```

### 2. Test with Real ECS Runners
Once deployed:
```bash
# Quick test
make test-ecs
# Or
python test_ecs_simple.py
```

### 3. Key Files to Review
- `terraform/STEP_BY_STEP.md` - Where we left off with infrastructure
- `ECS_FARGATE_TESTING_STRATEGY.md` - Testing approach with sleep workflows
- `runner_test.yml` - The configurable test workflow
- `test_ecs_simple.py` - Test automation for ECS runners

### Current Blockers
- Need AWS Account ID and Region to continue Terraform deployment
- Network layer ready to deploy (01-network.tf)
- ECS configuration complete but needs to be broken into modules