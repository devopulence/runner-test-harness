#!/bin/bash

# First test runner - Sets up everything and runs initial test
# This is the easiest way to get started

echo ""
echo "================================================"
echo "GitHub Runner Performance Testing - First Run"
echo "================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is required but not installed"
    echo "   Please install Python 3.8 or later"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Check for GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo ""
    echo "❌ GITHUB_TOKEN environment variable is not set"
    echo ""
    echo "Please set your GitHub Personal Access Token:"
    echo "  export GITHUB_TOKEN='ghp_...your_token_here...'"
    echo ""
    echo "Your token needs these permissions:"
    echo "  - repo (Full control of repositories)"
    echo "  - workflow (Update GitHub Action workflows)"
    echo ""
    echo "Get a token at: https://github.com/settings/tokens/new"
    exit 1
fi

echo "✅ GitHub token found"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "⚠️  Failed to install some dependencies, trying with pip3..."
    pip3 install -r requirements.txt
fi

echo "✅ Dependencies installed"

# Setup workflows
echo ""
echo "📤 Setting up workflows in Devopulence/test-workflows..."
bash setup_workflows.sh

if [ $? -ne 0 ]; then
    echo "❌ Failed to setup workflows"
    exit 1
fi

# Run quick test
echo ""
echo "🧪 Running quick test to verify everything works..."
echo "================================================"
python quick_test.py

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "🎉 SUCCESS! Your testing harness is ready!"
    echo "================================================"
    echo ""
    echo "Next steps:"
    echo "1. Run a performance test:  make performance"
    echo "2. Run a load test:         make load"
    echo "3. Run the full suite:      make test"
    echo ""
    echo "Or explore all options:      make help"
    echo ""
else
    echo ""
    echo "⚠️  Quick test failed. Please check:"
    echo "1. Your GitHub token has correct permissions"
    echo "2. You have access to create/modify Devopulence/test-workflows"
    echo "3. GitHub Actions is enabled for the repository"
    echo ""
    echo "For manual troubleshooting:"
    echo "  python quick_test.py"
fi