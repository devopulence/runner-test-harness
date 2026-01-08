#!/bin/bash
# Script to apply the persistent runner fix

echo "======================================"
echo "Applying Persistent Runner Fix"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the terraform directory
if [ ! -f "ecs-github-runners-fixed.tf" ]; then
    echo -e "${RED}Error: ecs-github-runners-fixed.tf not found!${NC}"
    echo "Please run this script from the terraform directory"
    exit 1
fi

echo -e "${YELLOW}Step 1: Backing up current configuration${NC}"
cp ecs-github-runners.tf.backup ecs-github-runners.tf.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null

echo -e "${YELLOW}Step 2: Replacing configuration with fixed version${NC}"
cp ecs-github-runners-fixed.tf ecs-github-runners.tf

echo -e "${YELLOW}Step 3: Initializing Terraform${NC}"
terraform init

echo -e "${YELLOW}Step 4: Planning changes${NC}"
terraform plan -out=runner-fix.tfplan

echo ""
echo -e "${YELLOW}Review the plan above. Do you want to apply these changes? (yes/no)${NC}"
read -r response

if [[ "$response" == "yes" ]]; then
    echo -e "${GREEN}Step 5: Applying Terraform changes${NC}"
    terraform apply runner-fix.tfplan

    echo -e "${GREEN}Step 6: Force new deployment to pick up changes${NC}"
    aws ecs update-service \
        --cluster github-runners-cluster \
        --service github-runners-service \
        --force-new-deployment

    echo ""
    echo -e "${GREEN}✓ Fix applied successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Wait 2-3 minutes for new tasks to start"
    echo "2. Monitor logs to verify runners stay persistent:"
    echo "   aws logs tail /ecs/github-runners --follow"
    echo ""
    echo "3. Run a test job and verify the runner doesn't restart after completion"
    echo ""
    echo "Look for:"
    echo "  ✓ 'Listening for Jobs' (runner stays alive)"
    echo "  ✗ 'Removed .credentials' (should NOT appear)"

else
    echo -e "${RED}Cancelled - no changes applied${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Script complete!${NC}"