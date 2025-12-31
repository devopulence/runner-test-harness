# 04-ecs.tf - ECS Cluster, Task Definition, and Service for GitHub Runners
# This creates the ECS infrastructure to run 4 GitHub runners on Fargate

# Variables for runner configuration
variable "runner_count" {
  description = "Number of GitHub runners to deploy"
  type        = number
  default     = 4
}

variable "runner_cpu" {
  description = "CPU units for each runner (1024 = 1 vCPU)"
  type        = string
  default     = "1024"
}

variable "runner_memory" {
  description = "Memory for each runner in MB"
  type        = string
  default     = "2048"
}

# ECS Cluster
resource "aws_ecs_cluster" "github_runners" {
  name = "github-runners-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "github-runners-cluster"
    Environment = var.environment
    Purpose     = "GitHub Self-Hosted Runners"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "github_runner" {
  family                   = "github-runner"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.runner_cpu
  memory                   = var.runner_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "github-runner"
      image = "myoung34/github-runner:latest"

      essential = true

      # Environment variables for the runner
      environment = [
        {
          name  = "RUNNER_NAME_PREFIX"
          value = "ecs-runner"
        },
        {
          name  = "RUNNER_WORKDIR"
          value = "/tmp/github-runner"
        },
        {
          name  = "DISABLE_AUTOMATIC_DEREGISTRATION"
          value = "true"  # Keep runners registered
        },
        {
          name  = "EPHEMERAL"
          value = "false"  # Persistent runners
        },
        {
          name  = "LABELS"
          value = "self-hosted,ecs-fargate,aws,linux"
        },
        {
          name  = "REPO_URL"
          value = "https://github.com/${var.github_owner}/${var.github_repo}"
        }
      ]

      # Pull GitHub token from Secrets Manager
      secrets = [
        {
          name      = "ACCESS_TOKEN"
          valueFrom = aws_secretsmanager_secret.github_token.arn
        }
      ]

      # Logging configuration
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "github-runner"
        }
      }

      # Resource limits (optional, but good practice)
      ulimits = [
        {
          name      = "nofile"
          softLimit = 65536
          hardLimit = 65536
        }
      ]
    }
  ])

  tags = {
    Name        = "github-runner-task"
    Environment = var.environment
  }
}

# ECS Service - Runs exactly 4 tasks
resource "aws_ecs_service" "github_runners" {
  name            = "github-runners-service"
  cluster         = aws_ecs_cluster.github_runners.id
  task_definition = aws_ecs_task_definition.github_runner.arn
  desired_count   = var.runner_count
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.ecs_tasks.id]
    subnets          = [aws_subnet.public.id]
    assign_public_ip = true  # Required for Fargate in public subnet
  }

  # Ensure service waits for dependencies
  depends_on = [
    aws_iam_role_policy.ecs_task_execution_secrets,
    aws_iam_role_policy_attachment.ecs_task_execution_policy
  ]

  # Deployment configuration
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  tags = {
    Name        = "github-runners-service"
    Environment = var.environment
    RunnerCount = tostring(var.runner_count)
  }
}

# Auto Scaling Target (optional - set to fixed 4 for now)
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = var.runner_count
  min_capacity       = var.runner_count  # Fixed at 4
  resource_id        = "service/${aws_ecs_cluster.github_runners.name}/${aws_ecs_service.github_runners.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"

  depends_on = [aws_ecs_service.github_runners]
}

# Outputs
output "ecs_cluster_name" {
  value       = aws_ecs_cluster.github_runners.name
  description = "Name of the ECS cluster"
}

output "ecs_service_name" {
  value       = aws_ecs_service.github_runners.name
  description = "Name of the ECS service"
}

output "task_definition_arn" {
  value       = aws_ecs_task_definition.github_runner.arn
  description = "ARN of the task definition"
}

output "deployment_summary" {
  value = <<EOT

ECS Deployment Complete!
=======================
Cluster: ${aws_ecs_cluster.github_runners.name}
Service: ${aws_ecs_service.github_runners.name}
Runner Count: ${var.runner_count}
Task Size: ${var.runner_cpu} CPU / ${var.runner_memory} MB

GitHub Configuration:
- Repository: ${var.github_owner}/${var.github_repo}
- Runner Labels: self-hosted,ecs-fargate,aws,linux

Monitoring Commands:
--------------------
# View running tasks
aws ecs list-tasks --cluster ${aws_ecs_cluster.github_runners.name}

# Check service status
aws ecs describe-services --cluster ${aws_ecs_cluster.github_runners.name} --services ${aws_ecs_service.github_runners.name}

# View logs
aws logs tail ${aws_cloudwatch_log_group.ecs_logs.name} --follow

# Check runners in GitHub
https://github.com/${var.github_owner}/${var.github_repo}/settings/actions/runners

Cost Estimate:
-------------
${var.runner_count} runners × ${var.runner_cpu}/1024 vCPU × $0.04048/hour = $${format("%.3f", var.runner_count * (tonumber(var.runner_cpu) / 1024) * 0.04048)}/hour
${var.runner_count} runners × ${var.runner_memory}/1024 GB × $0.004445/hour = $${format("%.3f", var.runner_count * (tonumber(var.runner_memory) / 1024) * 0.004445)}/hour
Total: ~$${format("%.2f", (var.runner_count * (tonumber(var.runner_cpu) / 1024) * 0.04048) + (var.runner_count * (tonumber(var.runner_memory) / 1024) * 0.004445))}/hour

EOT
}