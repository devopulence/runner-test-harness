# 00-provider.tf - Provider Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Configure backend for state storage
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "github-runners/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "GitHub-Runners"
      ManagedBy   = "Terraform"
      Environment = var.environment
    }
  }
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}

# Data source for current region
data "aws_region" "current" {}

# Output account info for verification
output "account_info" {
  value = {
    account_id = data.aws_caller_identity.current.account_id
    region     = data.aws_region.current.name
  }
  description = "Current AWS account and region"
}