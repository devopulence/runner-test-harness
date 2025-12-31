# GitHub Runner Performance Testing Harness - Makefile
# Simplifies common operations

.PHONY: help setup test quick-test performance load stress validate clean install

# Default target
help:
	@echo "GitHub Runner Performance Testing Harness"
	@echo "========================================="
	@echo "Available commands:"
	@echo "  make install         - Install Python dependencies"
	@echo "  make setup           - Upload workflows to GitHub repository"
	@echo "  make quick-test      - Run a quick test (1 workflow)"
	@echo "  make performance     - Run performance test (5 workflows)"
	@echo "  make load           - Run load test (10 minutes)"
	@echo "  make stress         - Run stress test (find breaking point)"
	@echo "  make test           - Run full test suite"
	@echo "  make test-4-runners - Test 4-runner capacity (OpenShift simulation)"
	@echo "  make validate       - Validate configuration"
	@echo "  make clean          - Clean up metrics and results"
	@echo ""
	@echo "Environment Setup:"
	@echo "  export GITHUB_TOKEN='your_token_here'"
	@echo ""
	@echo "4-Runner OpenShift Testing:"
	@echo "  make test-4-runners - Simulates your 4-runner OpenShift environment"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Setup workflows in GitHub repository
setup:
	@echo "Setting up workflows in Devopulence/test-workflows..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	bash setup_workflows.sh

# Quick test - single workflow
quick-test:
	@echo "Running quick test..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python quick_test.py

# Performance test
performance:
	@echo "Running performance test..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_harness.py --test performance --environment development

# Load test
load:
	@echo "Running load test..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_harness.py --test load --environment development

# Stress test
stress:
	@echo "Running stress test..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_harness.py --test stress

# Full test suite
test:
	@echo "Running full test suite..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_harness.py

# Test 4-runner capacity (simulates OpenShift environment)
test-4-runners:
	@echo "Running 4-runner capacity test suite..."
	@echo "This simulates your OpenShift environment with exactly 4 runners"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_4_runners.py

# Test ECS Fargate runners with sleep workflows
test-ecs:
	@echo "Running ECS Fargate runner tests..."
	@echo "Testing with simple sleep-based workflows"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python test_ecs_simple.py

# Demonstrate 4-runner limit simulation
demo-4-runners:
	@echo "Demonstrating 4-runner limit simulation..."
	@echo "This shows how we simulate 4-runner limit on public GitHub"
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "Error: GITHUB_TOKEN not set"; \
		echo "Run: export GITHUB_TOKEN='your_token_here'"; \
		exit 1; \
	fi
	python demonstrate_4_runner_limit.py

# Validate configuration
validate:
	@echo "Validating configuration..."
	python test_harness.py --validate

# Clean up generated files
clean:
	@echo "Cleaning up generated files..."
	rm -rf metrics/*.json
	rm -rf results/*.json
	rm -rf reports/*
	@echo "Cleaned metrics, results, and reports directories"

# Check environment
check-env:
	@echo "Checking environment..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "❌ GITHUB_TOKEN not set"; \
	else \
		echo "✅ GITHUB_TOKEN is set"; \
	fi
	@if command -v python3 &> /dev/null; then \
		echo "✅ Python3 found: $$(python3 --version)"; \
	else \
		echo "❌ Python3 not found"; \
	fi
	@if [ -f "config.yaml" ]; then \
		echo "✅ config.yaml found"; \
		echo "   Repository: $$(grep -A1 'owner:' config.yaml | grep -v owner | head -1)"; \
	else \
		echo "❌ config.yaml not found"; \
	fi

# Run tests for development
dev: validate quick-test

# Run production tests
prod:
	python test_harness.py --environment production

# Show current configuration
show-config:
	@echo "Current Configuration:"
	@echo "====================="
	@grep "owner:" config.yaml
	@grep "repo:" config.yaml
	@grep "environment:" config.yaml
	@echo ""
	@echo "To change environment, use:"
	@echo "  python test_harness.py --environment [development|production|self-hosted]"