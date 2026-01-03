#!/bin/bash
# Script to verify runners are in persistent mode

echo "======================================"
echo "Verifying Persistent Runner Mode"
echo "======================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

CLUSTER="github-runners-cluster"
SERVICE="github-runners-service"
LOG_GROUP="/ecs/github-runners"

echo -e "${YELLOW}1. Checking running tasks...${NC}"
TASKS=$(aws ecs list-tasks --cluster $CLUSTER --query 'taskArns' --output text)

if [ -z "$TASKS" ]; then
    echo -e "${RED}No running tasks found!${NC}"
    exit 1
fi

TASK_COUNT=$(echo $TASKS | wc -w)
echo -e "${GREEN}Found $TASK_COUNT running tasks${NC}"

echo ""
echo -e "${YELLOW}2. Checking task configuration...${NC}"
for TASK in $TASKS; do
    echo "Checking task: $(basename $TASK)"

    # Get task details
    TASK_JSON=$(aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK --query 'tasks[0]')

    # Check if EPHEMERAL is set to false
    EPHEMERAL=$(echo $TASK_JSON | jq -r '.overrides.containerOverrides[0].environment[] | select(.name=="EPHEMERAL") | .value' 2>/dev/null)

    # Get container instance ARN for more details
    CREATED=$(echo $TASK_JSON | jq -r '.createdAt')
    echo "  Created: $CREATED"

    # Check the task definition
    TASK_DEF=$(echo $TASK_JSON | jq -r '.taskDefinitionArn')
    echo "  Task Definition: $(basename $TASK_DEF)"
done

echo ""
echo -e "${YELLOW}3. Checking recent logs for persistence indicators...${NC}"

# Get the most recent log stream
STREAM=$(aws logs describe-log-streams \
    --log-group-name $LOG_GROUP \
    --order-by LastEventTime \
    --descending \
    --limit 1 \
    --query 'logStreams[0].logStreamName' \
    --output text)

if [ -z "$STREAM" ]; then
    echo -e "${RED}No log streams found${NC}"
else
    echo "Checking log stream: $STREAM"
    echo ""

    # Look for key indicators in the last 100 log entries
    RECENT_LOGS=$(aws logs get-log-events \
        --log-group-name $LOG_GROUP \
        --log-stream-name "$STREAM" \
        --limit 100 \
        --query 'events[].message' \
        --output text)

    # Check for good indicators (persistent mode)
    if echo "$RECENT_LOGS" | grep -q "Listening for Jobs"; then
        echo -e "${GREEN}✓ Found: 'Listening for Jobs' - Runner stays alive after job${NC}"
    fi

    # Check for bad indicators (ephemeral mode)
    if echo "$RECENT_LOGS" | grep -q "Removed .credentials"; then
        echo -e "${RED}✗ Found: 'Removed .credentials' - Runner is removing itself (BAD)${NC}"
        echo -e "${RED}  This means runners are still in ephemeral mode!${NC}"
    else
        echo -e "${GREEN}✓ No credential removal found - Good sign${NC}"
    fi

    if echo "$RECENT_LOGS" | grep -q "Removed .runner"; then
        echo -e "${RED}✗ Found: 'Removed .runner' - Runner is cleaning up (BAD)${NC}"
    else
        echo -e "${GREEN}✓ No runner removal found - Good sign${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}4. Testing with a quick job...${NC}"
echo "Run this command to test:"
echo "  python debug_single_workflow.py"
echo ""
echo "Then monitor the logs:"
echo "  aws logs tail $LOG_GROUP --follow"
echo ""
echo "After the job completes, you should see:"
echo "  ✓ 'Job completed with result: Succeeded'"
echo "  ✓ 'Listening for Jobs' (runner waiting for next job)"
echo "  ✗ NOT 'Removed .credentials' or 'Removed .runner'"

echo ""
echo -e "${YELLOW}5. Current runner utilization:${NC}"
aws ecs describe-services \
    --cluster $CLUSTER \
    --services $SERVICE \
    --query 'services[0].{Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
    --output table

echo ""
echo "======================================"
echo -e "${GREEN}Verification complete!${NC}"
echo "======================================">