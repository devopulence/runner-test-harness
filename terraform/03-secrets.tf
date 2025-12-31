# 03-secrets.tf - AWS Secrets Manager for GitHub Token
# This securely stores the GitHub Personal Access Token for runners

# Variable for GitHub configuration
variable "github_owner" {
  description = "GitHub organization or user"
  type        = string
  default     = "Devopulence"
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "test-workflows"
}

# Variable for GitHub token (set via environment: export TF_VAR_github_token="ghp_...")
variable "github_token" {
  description = "GitHub Personal Access Token for runner registration"
  type        = string
  sensitive   = true
}

# Create secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "github_token" {
  name                    = "github-runner-token"
  description             = "GitHub PAT for self-hosted runner registration"
  recovery_window_in_days = 0  # Set to 0 for immediate deletion (be careful!)

  tags = {
    Name        = "github-runner-token"
    Environment = var.environment
    Purpose     = "GitHub Runner Authentication"
  }
}

# Store the actual token value
resource "aws_secretsmanager_secret_version" "github_token" {
  secret_id     = aws_secretsmanager_secret.github_token.id
  secret_string = jsonencode({
    github_token = var.github_token
    github_owner = var.github_owner
    github_repo  = var.github_repo
  })
}

# Optional: Create SSM parameters for non-sensitive config
resource "aws_ssm_parameter" "github_owner" {
  name  = "/github-runners/github-owner"
  type  = "String"
  value = var.github_owner

  tags = {
    Name        = "github-runners-owner"
    Environment = var.environment
  }
}

resource "aws_ssm_parameter" "github_repo" {
  name  = "/github-runners/github-repo"
  type  = "String"
  value = var.github_repo

  tags = {
    Name        = "github-runners-repo"
    Environment = var.environment
  }
}

# Outputs
output "secret_arn" {
  value       = aws_secretsmanager_secret.github_token.arn
  description = "ARN of the GitHub token secret"
  sensitive   = true
}

output "secret_name" {
  value       = aws_secretsmanager_secret.github_token.name
  description = "Name of the GitHub token secret"
}

output "secrets_summary" {
  value = <<EOT

Secrets Configuration:
=====================
Secret Name: ${aws_secretsmanager_secret.github_token.name}
GitHub Owner: ${var.github_owner}
GitHub Repo: ${var.github_repo}
SSM Parameters Created:
  - /github-runners/github-owner
  - /github-runners/github-repo

IMPORTANT: Set your GitHub token before applying:
  export TF_VAR_github_token="ghp_your_token_here"

Next Step: Apply 04-ecs.tf for ECS cluster and services
EOT
}