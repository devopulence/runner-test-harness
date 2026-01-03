# Makefile for GitHub Runner Performance Test Harness
# Portable testing for AWS ECS and OpenShift environments

.PHONY: help setup test-aws test-openshift interactive list dry-run clean

# Default target
help:
	@echo "GitHub Runner Performance Test Harness"
	@echo "======================================"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup           - Install dependencies"
	@echo "  make test-aws        - Run performance test on AWS ECS"
	@echo "  make test-openshift  - Run performance test on OpenShift"
	@echo "  make interactive     - Run in interactive mode"
	@echo "  make list           - List available tests"
	@echo "  make dry-run        - Validate configuration"
	@echo "  make clean          - Clean test results"
	@echo ""
	@echo "Test types:"
	@echo "  make test-performance - Run performance baseline test"
	@echo "  make test-capacity   - Run capacity test"
	@echo "  make test-stress     - Run stress test"
	@echo "  make test-load       - Run load test"
	@echo "  make test-spike      - Run spike test"
	@echo ""
	@echo "Environment variables:"
	@echo "  GITHUB_TOKEN        - Required for GitHub API access"
	@echo "  TEST_ENV           - Environment to use (aws_ecs or openshift_prod)"

# Check for required environment variables
check-token:
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN environment variable not set"; \
		echo "Please run: export GITHUB_TOKEN='your_github_pat_token'"; \
		exit 1; \
	fi

# Setup Python dependencies
setup:
	@echo "Installing Python dependencies..."
	@pip install requests urllib3 pyyaml

# Run performance test on AWS ECS
test-aws: check-token
	@echo "Running performance test on AWS ECS..."
	@python run_tests.py -e aws_ecs -t performance

# Run performance test on OpenShift
test-openshift: check-token
	@echo "Running performance test on OpenShift..."
	@python run_tests.py -e openshift_prod -t performance

# Run in interactive mode
interactive: check-token
	@python run_tests.py -i

# List available tests
list:
	@python run_tests.py -e $${TEST_ENV:-aws_ecs} -l

# Dry run - validate configuration
dry-run:
	@echo "Validating AWS ECS configuration..."
	@python run_tests.py -e aws_ecs --dry-run
	@echo ""
	@echo "Validating OpenShift configuration..."
	@python run_tests.py -e openshift_prod --dry-run

# Clean test results
clean:
	@echo "Cleaning test results..."
	@rm -rf test_results/
	@rm -f logs/*.log
	@echo "Test results cleaned"

# Quick test
test-quick: check-token
	@echo "Running quick performance test (5 minutes)..."
	@python run_tests.py -e aws_ecs -t performance
