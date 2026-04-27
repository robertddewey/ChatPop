# CDN configuration. Auto-loaded by terraform. Committed to git — none of
# these values are secrets.
#
# apex_domain enables the entire CDN stack (CloudFront + ACM + Route 53 alias
# + signing key pair). Set to empty to disable.
#
# cdn_subdomain controls the alias hostname:
#   dev:  cdn-dev.<apex_domain>  (e.g. cdn-dev.chatmie.com)
#   prod: cdn.<apex_domain>      (e.g. cdn.chatmie.com)

apex_domain   = "chatmie.com"
cdn_subdomain = "cdn-dev"
