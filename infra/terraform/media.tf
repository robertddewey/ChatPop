# S3 bucket for development media (user uploads, avatars, etc).
#
# Per-developer isolation is achieved with key prefixes (e.g. "alice/",
# "bob/"). Branch-level isolation is *not* used — branches share media
# within a developer's prefix because media rarely diverges by branch.

# S3 bucket names are global; suffix prevents collisions across accounts.
resource "random_id" "media_bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "media" {
  bucket = "${local.name_prefix}-media-${random_id.media_bucket_suffix.hex}"

  # Allows `terraform destroy` to clean the bucket even if it contains
  # objects. Acceptable for dev; we'd set this to false for prod.
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all forms of public access. We'll grant access via IAM policies
# attached to specific users (developers, the Django app role).
resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CORS: the dev frontend (localhost:4000) uploads to S3 via presigned URLs
# and may render images directly. Permissive for dev; tighten for prod.
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  cors_rule {
    allowed_methods = ["GET", "PUT", "POST", "HEAD"]
    allowed_origins = ["*"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# Versioning intentionally NOT enabled (cost, and not needed for dev media).
