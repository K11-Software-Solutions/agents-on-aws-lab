output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "app_role_arn" {
  description = "Put this in the Helm value serviceAccount.roleArn."
  value       = aws_iam_role.app.arn
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "ecr_repository_url" {
  value = aws_ecr_repository.agents.repository_url
}

output "api_key_secret_arn" {
  description = "Set its value once: aws secretsmanager put-secret-value --secret-id <arn> --secret-string ..."
  value       = aws_secretsmanager_secret.anthropic_api_key.arn
}
