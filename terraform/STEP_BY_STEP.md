# Step-by-Step AWS Infrastructure Setup for GitHub Runners

## Current Status: Network Foundation

We're building this infrastructure in layers:
1. **Network** (VPC, Subnet, IGW) ← We're here
2. **IAM** (Roles and Policies)
3. **Secrets** (GitHub Token)
4. **ECS** (Cluster, Task Definition, Service)

## Step 1: Set Up Network Foundation

### Prerequisites
- AWS CLI configured with credentials
- Terraform installed (1.0+)
- AWS account and region info ready

### Configure Your Environment

1. **Copy the example variables file:**
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. **Edit terraform.tfvars with your details:**
```hcl
aws_region = "us-east-1"  # Replace with your region
```

### Deploy Network Layer Only

```bash
# Initialize Terraform
terraform init

# Plan just the network resources
terraform plan -target=aws_vpc.main \
               -target=aws_internet_gateway.main \
               -target=aws_subnet.public \
               -target=aws_route_table.public \
               -target=aws_route.public_internet \
               -target=aws_route_table_association.public \
               -target=aws_security_group.ecs_tasks

# Review the plan - should create 7 resources:
# - 1 VPC
# - 1 Internet Gateway
# - 1 Public Subnet
# - 1 Route Table
# - 1 Route (to IGW)
# - 1 Route Table Association
# - 1 Security Group

# Apply if it looks good
terraform apply -target=aws_vpc.main \
                -target=aws_internet_gateway.main \
                -target=aws_subnet.public \
                -target=aws_route_table.public \
                -target=aws_route.public_internet \
                -target=aws_route_table_association.public \
                -target=aws_security_group.ecs_tasks
```

### Verify Network Creation

```bash
# Check VPC
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=github-runners-vpc"

# Check Subnet
aws ec2 describe-subnets --filters "Name=tag:Name,Values=github-runners-public-subnet"

# Check Internet Gateway
aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=github-runners-igw"
```

## What Gets Created in Step 1

### Network Resources:
```
VPC (10.0.0.0/16)
 ├── Internet Gateway (attached)
 ├── Public Subnet (10.0.1.0/24)
 │   └── Route Table
 │       └── Route (0.0.0.0/0 → IGW)
 └── Security Group (outbound only)
```

### Cost:
- VPC: Free
- Internet Gateway: Free (pay for data transfer)
- Public Subnet: Free
- Total: ~$0/month for infrastructure

## Next Steps (After Network is Ready)

### Step 2: IAM Roles (02-iam.tf)
```bash
# We'll create:
# - ECS Task Execution Role
# - ECS Task Role
# - Necessary policies
```

### Step 3: Secrets Manager (03-secrets.tf)
```bash
# We'll store:
# - GitHub Personal Access Token
```

### Step 4: ECS Resources (04-ecs.tf)
```bash
# We'll create:
# - ECS Cluster
# - Task Definition
# - Service with 4 tasks
# - CloudWatch Logs
```

## Troubleshooting

### Issue: AWS credentials not configured
```bash
aws configure
# Enter your Access Key ID, Secret Access Key, Region
```

### Issue: Terraform version too old
```bash
# Check version
terraform version

# Update if needed (macOS)
brew upgrade terraform
```

### Issue: Region not available
```bash
# List available regions
aws ec2 describe-regions
```

## Clean Up (If Needed)

To destroy just the network resources:
```bash
terraform destroy -target=aws_vpc.main \
                  -target=aws_internet_gateway.main \
                  -target=aws_subnet.public \
                  -target=aws_route_table.public \
                  -target=aws_route.public_internet \
                  -target=aws_route_table_association.public \
                  -target=aws_security_group.ecs_tasks
```

## Ready to Continue?

Once the network is created and verified, let me know:
1. Your AWS Account ID (from the terraform output)
2. The region you're using
3. If the network resources created successfully

Then we'll move to Step 2: IAM Roles!