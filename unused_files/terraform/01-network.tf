# 01-network.tf - VPC and Networking Foundation
# This creates the base networking infrastructure for ECS Fargate runners

# Variables for network configuration
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"  # UPDATE with your region
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "test"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

# Create VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "github-runners-vpc"
    Environment = var.environment
    Purpose     = "GitHub Runners on ECS Fargate"
  }
}

# Create Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "github-runners-igw"
    Environment = var.environment
  }
}

# Create Public Subnet (for ECS tasks)
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name        = "github-runners-public-subnet"
    Environment = var.environment
    Type        = "Public"
  }
}

# Get available AZs
data "aws_availability_zones" "available" {
  state = "available"
}

# Create Route Table for Public Subnet
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "github-runners-public-rt"
    Environment = var.environment
    Type        = "Public"
  }
}

# Add route to Internet Gateway
resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

# Associate Route Table with Public Subnet
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security Group for ECS Tasks (GitHub Runners)
resource "aws_security_group" "ecs_tasks" {
  name        = "github-runners-ecs-sg"
  description = "Security group for GitHub runner ECS tasks"
  vpc_id      = aws_vpc.main.id

  # Allow all outbound traffic (runners need to reach GitHub)
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # No inbound rules needed (runners pull jobs from GitHub)

  tags = {
    Name        = "github-runners-ecs-sg"
    Environment = var.environment
  }
}

# Outputs for use in other modules
output "vpc_id" {
  value       = aws_vpc.main.id
  description = "ID of the VPC"
}

output "public_subnet_id" {
  value       = aws_subnet.public.id
  description = "ID of the public subnet"
}

output "security_group_id" {
  value       = aws_security_group.ecs_tasks.id
  description = "ID of the ECS tasks security group"
}

output "network_summary" {
  value = <<EOT

Network Infrastructure Created:
==============================
VPC ID: ${aws_vpc.main.id}
VPC CIDR: ${var.vpc_cidr}
Public Subnet: ${aws_subnet.public.id}
Subnet CIDR: ${var.public_subnet_cidr}
Internet Gateway: ${aws_internet_gateway.main.id}
Security Group: ${aws_security_group.ecs_tasks.id}

Next Step: Apply 02-iam.tf for IAM roles
EOT
}