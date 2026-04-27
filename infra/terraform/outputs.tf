output "aws_account_id" {
  description = "AWS account id used by this stack."
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region used by this stack."
  value       = var.aws_region
}

output "name_prefix" {
  description = "Resource naming prefix (project-environment)."
  value       = local.name_prefix
}

output "media_bucket_name" {
  description = "S3 bucket name for dev media."
  value       = aws_s3_bucket.media.id
}

output "media_bucket_arn" {
  description = "S3 bucket ARN for dev media (for use in IAM policies)."
  value       = aws_s3_bucket.media.arn
}

output "media_bucket_domain" {
  description = "Regional domain name of the media bucket."
  value       = aws_s3_bucket.media.bucket_regional_domain_name
}

# --- Tailscale router -----------------------------------------------------

output "tailscale_router_instance_id" {
  description = "EC2 instance id for the Tailscale subnet router."
  value       = aws_instance.tailscale_router.id
}

output "tailscale_router_private_ip" {
  description = "Private IP of the Tailscale router (also reachable via Tailscale)."
  value       = aws_instance.tailscale_router.private_ip
}

output "vpc_cidr" {
  description = "CIDR block advertised by the Tailscale router."
  value       = data.aws_vpc.default.cidr_block
}

# --- RDS ------------------------------------------------------------------

output "rds_endpoint" {
  description = "RDS connection endpoint (host:port style)."
  value       = aws_db_instance.dev.endpoint
}

output "rds_address" {
  description = "RDS hostname (no port)."
  value       = aws_db_instance.dev.address
}

output "rds_port" {
  description = "RDS port."
  value       = aws_db_instance.dev.port
}

output "rds_initial_database" {
  description = "The initial database created with the RDS instance."
  value       = aws_db_instance.dev.db_name
}

output "rds_master_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the master credentials."
  value       = aws_secretsmanager_secret.db_master.arn
}

output "rds_master_secret_name" {
  description = "Name of the Secrets Manager secret (use with `aws secretsmanager get-secret-value`)."
  value       = aws_secretsmanager_secret.db_master.name
}

output "api_keys_secret_arn" {
  description = "ARN of the shared API keys secret (third-party keys)."
  value       = aws_secretsmanager_secret.api_keys.arn
}

output "api_keys_secret_name" {
  description = "Name of the shared API keys secret."
  value       = aws_secretsmanager_secret.api_keys.name
}

# --- CDN -------------------------------------------------------------------

output "cdn_enabled" {
  description = "Whether the CDN (CloudFront) stack is provisioned."
  value       = local.cdn_enabled
}

output "cdn_domain" {
  description = "Custom domain for the CDN (e.g. cdn-dev.chatmie.com). Empty when CDN is disabled."
  value       = local.cdn_full_domain
}

output "cdn_distribution_id" {
  description = "CloudFront distribution ID for the media CDN."
  value       = local.cdn_enabled ? aws_cloudfront_distribution.media[0].id : ""
}

output "cdn_distribution_domain" {
  description = "AWS-assigned CloudFront domain (xxxxxx.cloudfront.net). Used internally by Route 53 alias."
  value       = local.cdn_enabled ? aws_cloudfront_distribution.media[0].domain_name : ""
}

output "cdn_signing_key_secret_name" {
  description = "Secrets Manager secret name holding the CloudFront private key + key ID."
  value       = local.cdn_enabled ? aws_secretsmanager_secret.cdn_signing_key[0].name : ""
}
