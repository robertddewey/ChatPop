provider "aws" {
  profile = var.aws_profile
  region  = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Useful runtime data we tag onto resources for traceability.
data "aws_caller_identity" "current" {}

locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Naming prefix used by per-environment resources, e.g. "chatpop-dev".
  name_prefix = "${var.project}-${var.environment}"

  # CDN — disabled when apex_domain is empty.
  cdn_enabled     = var.apex_domain != ""
  cdn_full_domain = local.cdn_enabled ? "${var.cdn_subdomain}.${var.apex_domain}" : ""

  # All Secrets Manager secrets that developers need read access to. The
  # CDN signing-key secret only exists when the CDN is enabled.
  shared_secret_arns = concat(
    [
      aws_secretsmanager_secret.db_master.arn,
      aws_secretsmanager_secret.api_keys.arn,
    ],
    local.cdn_enabled ? [aws_secretsmanager_secret.cdn_signing_key[0].arn] : []
  )
}
