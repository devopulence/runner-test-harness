# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a GitHub Runner Performance Testing Harness designed to comprehensively test the performance, scalability, and capacity of GitHub workflow runners.

### Project Goal

**Primary Objective**: Build a portable testing harness to evaluate GitHub runners in an OpenShift production environment with a 4-server constraint.

**Production Context**:
- **Target Environment**: OpenShift with 4 GitHub runners
- **Real Workload**: CI/CD pipeline operations including:
  - Building software
  - Creating artifacts
  - Running security scans
  - Packaging applications
  - Pushing artifacts (including Docker in Docker)

**Testing Strategy**:
1. **AWS Environment**: Used as a test bed to develop and validate the harness
2. **Simulation Method**: Use sleep-based workflows to simulate build times without actual compilation
3. **Portability**: Harness must be environment-agnostic to run in both AWS (testing) and OpenShift (production)
4. **End Goal**: Deploy this harness to OpenShift to measure real capacity and performance metrics

### Current Status (Jan 4, 2025)
- **Development Environment**: AWS ECS Fargate with 4 runners (mimics OpenShift constraint)
- **Production Environment**: OpenShift with 4 servers (target for testing)
- **Phase**: Performance testing with working persistent runners
- **Architecture**: 4 ECS Fargate tasks to simulate OpenShift's 4-server limit
- **Testing Method**: Sleep-based workflows (3-5 min) to simulate CI/CD build times
- **Runner Status**: ✅ FIXED - Persistent mode working (no EPHEMERAL variable set)

### Critical Constraints
- **4 Runner Limit**: Both OpenShift and ECS environments limited to exactly 4 runners
- **1 Runner = 1 Job**: Each runner can only execute one job at a time
- **Repository**: Currently using `Devopulence/test-workflows` for testing

### Testing Scope
The harness enables the following types of performance testing to evaluate OpenShift capacity:

- **Performance Testing**: Baseline performance metrics
  - Establish normal CI/CD pipeline completion times
  - Identify optimal job sizes for the 4-server constraint

- **Scalability Testing**: How runners handle increasing workloads
  - Determine how build queues grow with increased demand
  - Find the point where 4 servers become insufficient

- **Load Testing**: Behavior under expected load conditions
  - Simulate typical daily CI/CD patterns
  - Measure performance during peak development hours

- **Spike Testing**: Response to sudden load increases
  - Test behavior during release rushes
  - Evaluate recovery time after spike events

- **Stress Testing**: Breaking point identification
  - Find maximum sustainable CI/CD load
  - Identify when to scale beyond 4 servers

- **Volume Testing**: Large-scale data processing capabilities
  - Test with varying build sizes and complexities
  - Determine optimal batch sizes for artifact processing

- **Capacity Testing**: Maximum concur2 jrent workflow handling
  - Establish hard limits for parallel builds
  - Define queue management strategies

### Implementation Strategy
1. **Phase 1 (Current)**: Develop test harness in AWS ECS environment
   - 4 ECS Fargate runners simulate OpenShift's 4-server constraint
   - Use sleep-based workflows to simulate CI/CD build times
   - Validate harness functionality and metrics collection

2. **Phase 2**: Deploy harness to OpenShift production environment
   - Run same test suite against actual OpenShift runners
   - Measure real CI/CD performance under various load conditions
   - Compare results with AWS baseline to validate simulation accuracy

3. **Testing Method**: Use `runner_test.yml` with configurable sleep durations
   - Sleep duration represents actual build/compile/scan times
   - Job count simulates concurrent CI/CD pipeline requests

4. **Metrics Collection**:
   - Queue time (how long builds wait)
   - Execution time (actual build duration)
   - Throughput (builds completed per hour)
   - Capacity utilization (% of runners busy)

### Portability Requirements

The test harness MUST be environment-agnostic to run in both AWS and OpenShift:

- **No Cloud-Specific Dependencies**: Use only GitHub API and standard Python
- **Configurable Endpoints**: Support different GitHub Enterprise instances
- **Environment Variables**: All environment-specific settings via config
- **Network Flexibility**: Support proxies and custom CA certificates
- **Workflow Compatibility**: Test workflows must run on any Linux runner

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
python main.py --owner xxx-sandbox --repo ghe-test --workflow k8s.yml --ref develop

# With workflow inputs (JSON format)
python main.py --owner xxx-sandbox --repo ghe-test --workflow deploy.yml --inputs '{"environment":"staging","version":"1.2.3"}'

# Using environment token instead of CLI arg
export GITHUB_TOKEN="your_pat_token"
python main.py --owner xxx-sandbox --repo ghe-test --workflow build.yml
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