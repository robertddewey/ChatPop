# CloudFront CDN in front of the S3 media bucket.
#
# What this gives you:
#   - HTTPS via custom domain (cdn-dev.chatmie.com → cdn.chatmie.com later)
#   - Edge caching at PoPs near viewers (sub-50ms vs ~70-150ms direct from
#     us-east-1)
#   - Signed URLs replacing S3 presigned URLs. Django generates URLs signed
#     with the CloudFront RSA private key; URLs expire after a configurable
#     TTL (default 1 hour). After expiry, the URL gets 403 — bounded
#     URL-sharing window without breaking browsers / range requests.
#
# Disabled by default. Enable by setting var.apex_domain (e.g. via
# secrets.auto.tfvars or `-var apex_domain=chatmie.com`). All resources
# in this file are gated behind local.cdn_enabled.
#
# Naming: this dev env uses cdn-dev.chatmie.com. Production should set
# var.cdn_subdomain = "cdn" so prod gets cdn.chatmie.com.

# --- Hosted zone (auto-created when domain was registered via Route 53) ---
data "aws_route53_zone" "apex" {
  count = local.cdn_enabled ? 1 : 0
  name  = var.apex_domain
}

# --- ACM cert (must be in us-east-1 for CloudFront) -----------------------
# The default provider in this stack is us-east-1, so no aliased provider
# needed. If aws_region is ever changed, add a us-east-1 aliased provider
# and reference it from this resource.
resource "aws_acm_certificate" "cdn" {
  count             = local.cdn_enabled ? 1 : 0
  domain_name       = local.cdn_full_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${local.display_prefix}-cdn-cert"
  }
}

resource "aws_route53_record" "cdn_cert_validation" {
  for_each = local.cdn_enabled ? {
    for dvo in aws_acm_certificate.cdn[0].domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  } : {}

  zone_id         = data.aws_route53_zone.apex[0].zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "cdn" {
  count                   = local.cdn_enabled ? 1 : 0
  certificate_arn         = aws_acm_certificate.cdn[0].arn
  validation_record_fqdns = [for r in aws_route53_record.cdn_cert_validation : r.fqdn]
}

# --- Origin Access Control (OAC) — locks the bucket to CloudFront --------
# OAC is the modern replacement for OAI. CloudFront authenticates to S3
# with SigV4 using the distribution's identity; the bucket policy below
# only trusts requests bearing this distribution's ARN as SourceArn.
resource "aws_cloudfront_origin_access_control" "media" {
  count                             = local.cdn_enabled ? 1 : 0
  name                              = "${local.name_prefix}-media-oac"
  description                       = "OAC for ${local.display_prefix} media bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# --- Signed URL key pair --------------------------------------------------
# CloudFront signed URLs are RSA 2048 (NOT 4096 — CloudFront rejects
# anything else). Public key registers with CloudFront; private key goes
# to Secrets Manager so Django can read it.
resource "tls_private_key" "cdn_signer" {
  count     = local.cdn_enabled ? 1 : 0
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_cloudfront_public_key" "cdn_signer" {
  count       = local.cdn_enabled ? 1 : 0
  name        = "${local.name_prefix}-cdn-signer"
  comment     = "Public key for signing ${local.display_prefix} media URLs"
  encoded_key = tls_private_key.cdn_signer[0].public_key_pem
}

resource "aws_cloudfront_key_group" "cdn_signers" {
  count   = local.cdn_enabled ? 1 : 0
  name    = "${local.name_prefix}-cdn-signers"
  comment = "Trusted signers for ${local.display_prefix} media"
  items   = [aws_cloudfront_public_key.cdn_signer[0].id]
}

# --- Secrets Manager: private key + CloudFront key ID --------------------
# Django (or anyone authorized) reads this to sign URLs.
resource "aws_secretsmanager_secret" "cdn_signing_key" {
  count       = local.cdn_enabled ? 1 : 0
  name        = "${local.name_prefix}/cdn/signing-key"
  description = "RSA private key + CloudFront public-key ID for signing media URLs."

  # 0 = allow immediate destroy + re-create (useful during dev iteration).
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cdn_signing_key" {
  count     = local.cdn_enabled ? 1 : 0
  secret_id = aws_secretsmanager_secret.cdn_signing_key[0].id
  secret_string = jsonencode({
    key_id      = aws_cloudfront_public_key.cdn_signer[0].id
    private_key = tls_private_key.cdn_signer[0].private_key_pem
  })
}

# --- CloudFront distribution ----------------------------------------------
resource "aws_cloudfront_distribution" "media" {
  count           = local.cdn_enabled ? 1 : 0
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.display_prefix} media CDN"
  aliases         = [local.cdn_full_domain]
  price_class     = "PriceClass_100" # US, Canada, Europe (cheapest)

  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "s3-${aws_s3_bucket.media.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.media[0].id
  }

  default_cache_behavior {
    target_origin_id       = "s3-${aws_s3_bucket.media.id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # AWS-managed CachingOptimized policy — sensible defaults for static
    # assets (long TTL, gzip/brotli, common headers forwarded).
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    # Require signed URLs. Anything unsigned (or expired) gets 403.
    trusted_key_groups = [aws_cloudfront_key_group.cdn_signers[0].id]
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.cdn[0].certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${local.display_prefix}-media-cdn"
  }
}

# --- S3 bucket policy: allow CloudFront via OAC ---------------------------
# This is additive to existing IAM grants on the bucket — devs still upload
# directly via boto3 with their per-dev IAM keys. CloudFront just gets read
# access.
resource "aws_s3_bucket_policy" "media_cloudfront" {
  count  = local.cdn_enabled ? 1 : 0
  bucket = aws_s3_bucket.media.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.media.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.media[0].arn
          }
        }
      },
    ]
  })
}

# --- Route 53 alias: cdn-<env>.<apex> → CloudFront ------------------------
resource "aws_route53_record" "cdn" {
  count   = local.cdn_enabled ? 1 : 0
  zone_id = data.aws_route53_zone.apex[0].zone_id
  name    = local.cdn_full_domain
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.media[0].domain_name
    zone_id                = aws_cloudfront_distribution.media[0].hosted_zone_id
    evaluate_target_health = false
  }
}
