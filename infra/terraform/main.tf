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
}
