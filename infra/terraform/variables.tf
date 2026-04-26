variable "aws_profile" {
  description = "Local AWS CLI profile used by terraform to authenticate."
  type        = string
  default     = "chatpop-dev"
}

variable "aws_region" {
  description = "AWS region for all resources in this stack."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project identifier used in resource naming and tagging."
  type        = string
  default     = "chatpop"
}

variable "environment" {
  description = "Environment name. One of: dev, staging, prod."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

# --- Tailscale -------------------------------------------------------------

variable "tailscale_auth_key" {
  description = "Tailscale reusable, pre-approved auth key for the EC2 subnet router. Provided via secrets.auto.tfvars (gitignored), populated by infra/bootstrap-tailscale.sh."
  type        = string
  sensitive   = true
}

variable "tailscale_router_instance_type" {
  description = "EC2 instance type for the Tailscale subnet router."
  type        = string
  default     = "t4g.nano"
}

# --- RDS -------------------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.small"
}

variable "db_engine_version" {
  description = "Postgres engine version on RDS. Must be a version supporting pgvector."
  type        = string
  default     = "16.13"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB (gp3)."
  type        = number
  default     = 20
}

variable "db_master_username" {
  description = "Master username for the RDS instance. Used by Terraform / admin scripts only; per-developer roles will be created separately."
  type        = string
  default     = "chatpop_admin"
}

variable "db_initial_database" {
  description = "Initial database created with the RDS instance. Will be used as the canonical clone source for per-dev databases."
  type        = string
  default     = "dev_seed"
}

variable "db_backup_retention_days" {
  description = "How many days of automated backups to retain (point-in-time recovery window)."
  type        = number
  default     = 7
}
