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
  # Project tag is hardcoded to "chatmie" (the company/brand) so the AWS
  # console shows the current brand. The infrastructure resource names below
  # still use ${var.project}-${var.environment} (= "chatpop-dev") because
  # AWS-side names on S3 buckets, RDS instances, and Secrets Manager secrets
  # are immutable — renaming them is a destroy/recreate that's deferred to a
  # planned migration window. End users never see the resource names; they
  # see the CDN domain (cdn-dev.chatmie.com) which is already on the new brand.
  common_tags = {
    Project     = "chatmie"
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Naming prefix for AWS-side resource identifiers (immutable). Stays as
  # "chatpop-dev" until a future migration renames the underlying resources.
  name_prefix = "${var.project}-${var.environment}"

  # Display prefix used in tags + console-visible descriptions only. Mutable;
  # change this freely without touching any resource identifiers.
  display_prefix = "chatmie-${var.environment}"

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
