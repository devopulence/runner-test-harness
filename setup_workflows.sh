#!/bin/bash

# Setup script to create test workflows in the Devopulence/test-workflows repository
# This script will create the .github/workflows directory and copy all test workflows

echo "Setting up test workflows in Devopulence/test-workflows repository"
echo "===================================================================="

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN environment variable is not set"
    echo "Please set it with: export GITHUB_TOKEN='your_token_here'"
    exit 1
fi

# Configuration
OWNER="Devopulence"
REPO="test-workflows"
BRANCH="main"

echo "Target repository: $OWNER/$REPO"

# Check if repository exists and we have access
echo "Checking repository access..."
response=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$OWNER/$REPO")

if [ "$response" = "404" ]; then
    echo "Repository not found or no access. Creating repository..."

    # Create repository
    curl -X POST \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/user/repos" \
        -d '{
            "name": "test-workflows",
            "description": "GitHub Runner Performance Testing Workflows",
            "private": false,
            "auto_init": true
        }'

    echo "Repository created. Waiting for initialization..."
    sleep 5
elif [ "$response" = "200" ]; then
    echo "Repository exists and accessible."
else
    echo "Unexpected response: $response"
    exit 1
fi

# Function to upload file to GitHub
upload_workflow() {
    local file_path=$1
    local file_name=$(basename "$file_path")
    local github_path=".github/workflows/$file_name"

    echo "Uploading $file_name..."

    # Read file content and base64 encode
    content=$(base64 < "$file_path")

    # Check if file exists first
    existing=$(curl -s \
        -H "Authorization: Bearer $GITHUB_TOKEN" \
        -H "Accept: application/vnd.github.v3+json" \
        "https://api.github.com/repos/$OWNER/$REPO/contents/$github_path")

    sha=$(echo "$existing" | grep '"sha"' | cut -d'"' -f4)

    # Create or update file
    if [ -z "$sha" ]; then
        # Create new file
        curl -X PUT \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github.v3+json" \
            "https://api.github.com/repos/$OWNER/$REPO/contents/$github_path" \
            -d "{
                \"message\": \"Add $file_name test workflow\",
                \"content\": \"$content\",
                \"branch\": \"$BRANCH\"
            }" > /dev/null 2>&1
    else
        # Update existing file
        curl -X PUT \
            -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github.v3+json" \
            "https://api.github.com/repos/$OWNER/$REPO/contents/$github_path" \
            -d "{
                \"message\": \"Update $file_name test workflow\",
                \"content\": \"$content\",
                \"sha\": \"$sha\",
                \"branch\": \"$BRANCH\"
            }" > /dev/null 2>&1
    fi

    echo "✅ $file_name uploaded"
}

# Upload all workflow files
echo ""
echo "Uploading workflow files..."
echo "---------------------------"

for workflow in test_workflows/*.yml; do
    if [ -f "$workflow" ]; then
        upload_workflow "$workflow"
    fi
done

echo ""
echo "✅ All workflows uploaded successfully!"
echo ""
echo "Repository URL: https://github.com/$OWNER/$REPO"
echo "Workflows URL: https://github.com/$OWNER/$REPO/tree/$BRANCH/.github/workflows"
echo ""
echo "You can now run tests with:"
echo "  python test_harness.py --test performance"
echo ""