# FUTURE.md

## Media Delivery Architecture Evolution

This document outlines the planned evolution of media delivery (voice, photos, videos) from MVP to global scale.

---

## Current Architecture (MVP)

### Phase 1: Django Proxy with S3 Backend

**Architecture:**
```
User → Django Server → S3 → Django → User
```

**Implementation:**
- All media stored in private S3 buckets
- Django validates permissions on every request
- Media streamed through Django server to client
- Clean URLs: `/api/chats/{code}/media/voice/{message_id}`

**Benefits:**
- ✅ Full access control (instant revocation)
- ✅ Audit trail (log every access)
- ✅ Clean URLs (no exposed S3 structure)
- ✅ Dynamic watermarking capability
- ✅ Rate limiting per user
- ✅ IP tracking for security

**Tradeoffs:**
- ⚠️ All bandwidth goes through Django server
- ⚠️ Single region (higher latency for distant users)
- ⚠️ Server load scales with concurrent streams

**When to use:**
- MVP to 1,000 users
- Small media files (voice <5MB, photos <10MB)
- Security/privacy is top priority

---

## Phase 2: CloudFront CDN (6-12 months)

### Adding Global Edge Caching

**Architecture:**
```
User → CloudFront Edge (400+ locations) → Django (origin) → S3 → Django → CloudFront → User
```

**Implementation:**
- CloudFront sits in front of Django
- First request: CloudFront → Django (cache miss)
- Subsequent requests: CloudFront serves from edge cache
- Cache private content with signed cookies
- Purge cache when access revoked

**Configuration:**
```python
# Django generates signed CloudFront URLs
from datetime import datetime, timedelta
import boto3

def get_media_url(message_id, user_session):
    # Validate user has access
    if not user_can_access(message_id, user_session):
        raise PermissionDenied

    # Generate short-lived CloudFront signed URL
    cloudfront_signer = boto3.client('cloudfront')
    url = cloudfront_signer.generate_presigned_url(
        f'/media/voice/{message_id}',
        expiration=datetime.now() + timedelta(minutes=15)
    )
    return url
```

**Benefits:**
- ✅ Fast global delivery (50-200+ edge locations)
- ✅ Reduced bandwidth costs (~$0.085/GB vs $0.09/GB direct)
- ✅ Django still validates permissions
- ✅ Caching reduces Django server load
- ✅ No code rewrite needed

**Configuration:**
- Cache TTL: 15 minutes (balance security vs performance)
- Signed cookies for auth
- Automatic cache invalidation on revocation
- Query string forwarding for access tokens

**When to use:**
- 1,000+ concurrent users
- International user base
- Bandwidth costs >$500/month

---

## Phase 3: Multi-Region Deployment (1-2 years)

### Regional Django Clusters

**Architecture:**
```
User (EU) → CloudFront (EU Edge) → Django (EU) → S3 (EU) → User
User (US) → CloudFront (US Edge) → Django (US) → S3 (US) → User
User (APAC) → CloudFront (APAC Edge) → Django (APAC) → S3 (APAC) → User
```

**Implementation:**
- Deploy Django to multiple AWS regions (us-east-1, eu-west-1, ap-southeast-1)
- S3 Cross-Region Replication for media files
- Route53 latency-based routing
- Regional PostgreSQL read replicas
- Shared Redis cluster or regional Redis

**Infrastructure:**
```yaml
Regions:
  - us-east-1 (N. Virginia)    # Americas
  - eu-west-1 (Ireland)        # Europe
  - ap-southeast-1 (Singapore) # Asia-Pacific

Per Region:
  - Django EC2/ECS cluster
  - S3 bucket (replicated)
  - PostgreSQL read replica
  - Redis cache (optional)
  - CloudFront distribution
```

**Benefits:**
- ✅ Low latency worldwide (<100ms)
- ✅ Redundancy (region failover)
- ✅ Compliance (data residency)
- ✅ Improved reliability

**Challenges:**
- 💰 Higher infrastructure costs (3x servers)
- 🔧 Complex deployment pipeline
- 🔄 Data consistency across regions
- 📊 Monitoring/debugging complexity

**When to use:**
- 10,000+ concurrent users globally
- Latency SLA requirements
- Regulatory compliance (GDPR, data residency)

---

## Phase 4: Facebook-Style Custom Edge (Future)

### Ultimate Scalability

**Architecture:**
```
User → Custom Edge Server (PoP) → Media Servers → Hot/Cold Storage → User
```

**Implementation:**
- Custom CDN infrastructure (400+ Points of Presence)
- Streaming-optimized edge servers
- In-memory caching at edge
- Hot/Cold storage tiers (SSD for recent, HDD for archive)
- Custom protocol optimizations

**Technologies:**
- Custom edge servers (Nginx/Varnish/custom)
- Facebook Haystack-style photo storage
- Memcached/Redis at edge
- BGP Anycast routing
- Custom video transcoding pipeline

**When to consider:**
- 100,000+ concurrent users
- Billions of media files
- Custom streaming requirements
- Budget for infrastructure team

**Reality Check:**
- This is years away
- Requires dedicated infrastructure team
- CloudFront Phase 2/3 handles 99% of use cases
- Only needed if you're the next Facebook/Instagram

---

## Why Not Direct S3 Pre-Signed URLs?

**Common Alternative:**
```
User → Request → Django (generates pre-signed URL) → User → S3 (direct download)
```

**Why we're NOT doing this:**

❌ **Security Issues:**
- Pre-signed URLs can be copied/shared
- URLs work until expiration (no instant revocation)
- Can't monitor who's actually accessing
- URLs reveal S3 bucket structure

❌ **Privacy Issues:**
- Anyone with URL can download (until expiry)
- No audit trail of actual downloads
- Can't implement dynamic watermarking
- Harder to detect/prevent abuse

❌ **UX Issues:**
- Long ugly URLs
- Breaks if URL expires mid-stream
- No range request support without complexity

✅ **Our Proxy Approach:**
- Check permissions on every request
- Instant access revocation
- Complete audit trail
- Clean URLs
- Future-proof for CloudFront

---

## Hybrid Approach (Optional)

### Smart Proxy Based on File Size

**Strategy:**
- Small files (<5MB): Proxy through Django
- Medium files (5-10MB): Proxy with aggressive caching
- Large files (>10MB): Short-lived pre-signed URLs

**Implementation:**
```python
def get_media_url(message):
    if message.file_size < 5_000_000:  # 5MB
        # Proxy through Django (full control)
        return f'/api/media/voice/{message.id}'
    else:
        # Generate 5-minute pre-signed URL for large files
        return s3_client.generate_presigned_url(
            message.s3_key,
            expires_in=300  # 5 minutes
        )
```

**When to use:**
- Supporting large video files (>50MB)
- Bandwidth costs are critical concern
- Willing to accept slight security tradeoff

---

## Cost Projections

### Phase 1: Django Proxy
- **Storage:** ~$0.023/GB/month (S3 Standard)
- **Bandwidth:** ~$0.09/GB (EC2 outbound)
- **Compute:** ~$50-200/month (EC2 t3.medium)
- **Total for 1TB transfer:** ~$90 + compute

### Phase 2: CloudFront CDN
- **Storage:** ~$0.023/GB/month (S3 Standard)
- **CloudFront:** ~$0.085/GB (first 10TB)
- **Compute:** ~$50-200/month (Django origin)
- **Total for 1TB transfer:** ~$85 + compute
- **Savings:** Reduced load on Django, better UX

### Phase 3: Multi-Region
- **Storage:** ~$0.069/GB/month (S3 + replication)
- **CloudFront:** ~$0.085/GB per region
- **Compute:** ~$150-600/month (3x regions)
- **Database:** ~$200-1000/month (RDS replicas)
- **Total:** ~3-4x Phase 2 costs

---

## Security Features to Add

### Current (Phase 1)
- [x] Permission validation on every request
- [x] Session token verification
- [x] IP address logging
- [x] Rate limiting per user

### Future Enhancements
- [ ] Dynamic watermarking (audio/video)
- [ ] Download attempt tracking
- [ ] Suspicious pattern detection
- [ ] Content encryption at rest
- [ ] DRM integration (for premium content)
- [ ] Forensic watermarking (trace leaks)

---

## Migration Path

### From Phase 1 → Phase 2 (CloudFront)
1. Set up CloudFront distribution
2. Point origin to Django
3. Configure signed cookies/URLs
4. Test with 10% traffic
5. Gradually increase to 100%
6. Monitor cache hit rates

**Zero downtime migration** ✅

### From Phase 2 → Phase 3 (Multi-Region)
1. Deploy Django to second region
2. Set up S3 replication
3. Configure Route53 routing
4. Test regional failover
5. Add third region
6. Monitor latency improvements

**Requires planning but achievable** ✅

---

## Decision Matrix

| Users | Concurrent | Regions | Recommended Phase | Est. Cost/Month |
|-------|-----------|---------|-------------------|-----------------|
| <1K | <100 | 1 | Phase 1: Django Proxy | $100-300 |
| 1-10K | 100-1K | 1-2 | Phase 2: CloudFront | $300-1,500 |
| 10-100K | 1K-10K | 3-5 | Phase 3: Multi-Region | $1,500-10,000 |
| 100K+ | 10K+ | Global | Phase 4: Custom | $10,000+ |

---

## Key Takeaways

1. **Start Simple:** Django proxy is the right choice for MVP
2. **Upgrade Path:** CloudFront is natural next step (no code rewrite)
3. **Scale Gradually:** Only add complexity when needed
4. **Security First:** Proxy architecture enables best security
5. **Future-Proof:** Built for global scale from day one

**Bottom Line:** The Django proxy architecture we're building now will serve you well through 10,000+ users, and seamlessly integrates with CloudFront when you need global scale.
