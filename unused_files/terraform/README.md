# ECS Fargate GitHub Runners - Terraform Deployment

## Quick Deploy (4 Runners on ECS Fargate)

### Prerequisites
- AWS CLI configured
- Terraform installed
- GitHub Personal Access Token

### Deploy Steps

```bash
# 1. Initialize Terraform
terraform init

# 2. Set your GitHub token
export TF_VAR_github_token="ghp_your_token_here"

# 3. Review plan
terraform plan

# 4. Deploy (creates exactly 4 runners)
terraform apply

# 5. Wait 2-3 minutes, then verify runners
# Check: GitHub > Settings > Actions > Runners
# You should see 4 runners: ecs-runner-1 through ecs-runner-4
```

### Configuration

The Terraform creates:
- **ECS Cluster**: `github-runners-cluster`
- **ECS Service**: 4 Fargate tasks (hard limit)
- **Task Size**: 1 vCPU, 2GB RAM each
- **Auto-scaling**: Disabled (fixed at 4)

### Cost Estimate

```
4 runners × 1 vCPU × $0.04048/hour = $0.162/hour
4 runners × 2 GB × $0.004445/hour = $0.036/hour
Total: ~$0.20/hour = ~$144/month (if running 24/7)
```

### Monitoring

```bash
# View running tasks
aws ecs list-tasks --cluster github-runners-cluster

# Check task status
aws ecs describe-tasks \
  --cluster github-runners-cluster \
  --tasks $(aws ecs list-tasks --cluster github-runners-cluster --query 'taskArns[0]' --output text)

# View logs
aws logs tail /ecs/github-runners --follow

# Check runners in GitHub
gh api repos/Devopulence/test-workflows/actions/runners
```

### Testing

Once deployed, run tests:

```bash
# Quick capacity check
make test-ecs

# Or run specific test
python test_ecs_simple.py
```

### Clean Up

```bash
# Destroy all resources
terraform destroy
```

## Customization Options

### Change Runner Count
```hcl
# In ecs-github-runners.tf
resource "aws_ecs_service" "github_runners" {
  desired_count = 4  # Change this to 2, 6, 8, etc.
}

# Also update auto-scaling limits
min_capacity = 4
max_capacity = 4
```

### Change Task Size
```hcl
# In task definition
cpu    = "2048"  # 2 vCPU
memory = "4096"  # 4 GB
```

### Use Private Subnet
```hcl
# Change subnet configuration
assign_public_ip = false  # Requires NAT Gateway
```

## Important Notes

1. **Manual Registration**: The runners auto-register using the token
2. **Labels**: Runners are labeled as `self-hosted,ecs-fargate,aws,linux`
3. **Persistence**: Runners stay registered (not ephemeral)
4. **Region**: Deploys to your default AWS region

## Troubleshooting

### Runners Not Appearing
- Check CloudWatch logs: `/ecs/github-runners`
- Verify token has correct permissions
- Ensure tasks are RUNNING: `aws ecs list-tasks --cluster github-runners-cluster`

### Tasks Failing
- Check security group allows outbound internet
- Verify IAM roles are correctly attached
- Check Secrets Manager has the token

### Cost Optimization
- Stop service when not testing: `aws ecs update-service --cluster github-runners-cluster --service github-runners-service --desired-count 0`
- Restart for testing: `aws ecs update-service --cluster github-runners-cluster --service github-runners-service --desired-count 4`