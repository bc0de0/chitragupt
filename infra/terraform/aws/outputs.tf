output "ecr_registry" {
  description = "ECR registry URL — use as AWS_ECR_REGISTRY secret"
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

output "cd_role_arn" {
  description = "CD IAM role ARN — use as AWS_OIDC_ROLE_ARN secret"
  value       = aws_iam_role.cd_runner.arn
}

output "db_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "ElastiCache primary endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

data "aws_caller_identity" "current" {}
