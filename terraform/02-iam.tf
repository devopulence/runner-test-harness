# 02-iam.tf - IAM Roles and Policies for ECS GitHub Runners
# This creates the IAM roles needed for ECS tasks to run

# ECS Task Execution Role - Used by ECS to pull images and write logs
resource "aws_iam_role" "ecs_task_execution" {
  name = "github-runners-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "github-runners-ecs-execution-role"
    Environment = var.environment
    Purpose     = "ECS Task Execution"
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for Secrets Manager access (for GitHub token)
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "github-runners-secrets-policy"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:github-runner-token*"
      }
    ]
  })
}

# ECS Task Role - Used by the actual container (GitHub runner)
resource "aws_iam_role" "ecs_task" {
  name = "github-runners-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "github-runners-ecs-task-role"
    Environment = var.environment
    Purpose     = "GitHub Runner Container"
  }
}

# Policy for the task role (minimal permissions for the runner itself)
resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "github-runners-task-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/github-runners/*"
      }
    ]
  })
}

# CloudWatch Log Group for ECS tasks
resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/github-runners"
  retention_in_days = 7  # Adjust as needed

  tags = {
    Name        = "github-runners-logs"
    Environment = var.environment
  }
}

# Outputs for use in other modules
output "ecs_task_execution_role_arn" {
  value       = aws_iam_role.ecs_task_execution.arn
  description = "ARN of the ECS task execution role"
}

output "ecs_task_role_arn" {
  value       = aws_iam_role.ecs_task.arn
  description = "ARN of the ECS task role"
}

output "cloudwatch_log_group_name" {
  value       = aws_cloudwatch_log_group.ecs_logs.name
  description = "Name of the CloudWatch log group"
}

output "iam_summary" {
  value = <<EOT

IAM Resources Created:
=====================
Execution Role: ${aws_iam_role.ecs_task_execution.name}
Task Role: ${aws_iam_role.ecs_task.name}
Log Group: ${aws_cloudwatch_log_group.ecs_logs.name}

Next Step: Apply 03-secrets.tf for GitHub token storage
EOT
}