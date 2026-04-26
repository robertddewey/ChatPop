# Per-developer IAM users with scoped permissions.
#
# Adds dev-<name> IAM users (one per developer) with policies allowing:
#   - Read/write S3 only under their own prefix (s3://bucket/<name>/*)
#   - Read-only S3 on dev_seed (so they can sync seed media on first cloud setup)
#   - Read the master DB password from Secrets Manager
#     (Postgres-level isolation is NOT enforced — see CLAUDE.md.)
#
# Add a developer:    chatpop admin add <name>
# Remove a developer: chatpop admin remove <name>
# List developers:    chatpop admin list
#
# Those commands edit infra/terraform/developers.auto.tfvars (which is
# auto-loaded by terraform). The list of developers is committed to git
# as the source of truth for "who's on the team"; their credentials are
# in terraform state (sensitive) and never in git.

variable "developers" {
  description = "List of developer identifiers (lowercase alphanumeric + underscore)."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for d in var.developers : can(regex("^[a-z][a-z0-9_]*$", d))])
    error_message = "Each developer name must start with a lowercase letter and contain only lowercase letters, digits, and underscores."
  }
}

resource "aws_iam_user" "developer" {
  for_each = toset(var.developers)
  name     = "dev-${each.key}"

  tags = {
    DeveloperName = each.key
  }
}

resource "aws_iam_access_key" "developer" {
  for_each = toset(var.developers)
  user     = aws_iam_user.developer[each.key].name
}

resource "aws_iam_user_policy" "developer" {
  for_each = toset(var.developers)
  name     = "${local.name_prefix}-dev-${each.key}"
  user     = aws_iam_user.developer[each.key].name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "OwnPrefixReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.media.arn}/${each.key}/*"
      },
      {
        Sid      = "DevSeedReadOnly"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.media.arn}/dev_seed/*"
      },
      {
        Sid      = "ListBucketScoped"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.media.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["${each.key}/*", "dev_seed/*", ""]
          }
        }
      },
      {
        Sid    = "ReadSharedSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = [
          aws_secretsmanager_secret.db_master.arn,
          aws_secretsmanager_secret.api_keys.arn,
        ]
      },
      # Note: PutSecretValue is intentionally not granted. Setting/rotating
      # secrets is an admin operation; admins use the chatpop-dev-deploy
      # AdministratorAccess profile via 'chatpop admin set-secret'.
      {
        Sid    = "ReadInfraOutputs"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeSecurityGroups",
        ]
        Resource = "*"
      },
    ]
  })
}

# Sensitive map of credentials. Use:
#   terraform output -json developer_credentials | jq '.<name>'
# Or, easier: chatpop admin add / chatpop admin list.
output "developer_credentials" {
  description = "Per-developer access keys. Sensitive — surfaced via 'chatpop admin'."
  sensitive   = true
  value = {
    for name in var.developers :
    name => {
      access_key_id     = aws_iam_access_key.developer[name].id
      secret_access_key = aws_iam_access_key.developer[name].secret
    }
  }
}
