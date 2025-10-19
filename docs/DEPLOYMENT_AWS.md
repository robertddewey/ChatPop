# AWS Deployment Guide (Fargate/ECS + ALB)

## Architecture Overview

```
Internet
    │
    ▼
┌────────────────────────────────────────┐
│  Route 53 (DNS)                        │
│  chatpop.app → ALB                     │
└────────────┬───────────────────────────┘
             │
             ▼
┌────────────────────────────────────────┐
│  Application Load Balancer             │
│  - SSL Termination (ACM Certificate)   │
│  - Path-based routing                  │
│  - WebSocket support enabled           │
└─────┬──────────────────────┬───────────┘
      │                      │
      │ /api/*               │ /*
      │ /media/*             │ (default)
      │ /ws/*                │
      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ Backend         │    │ Frontend        │
│ Target Group    │    │ Target Group    │
│                 │    │                 │
│ ECS Service     │    │ ECS Service     │
│ (Django/Daphne) │    │ (Next.js)       │
│                 │    │                 │
│ Task Count: 2+  │    │ Task Count: 2+  │
│ Port: 9000      │    │ Port: 4000      │
└─────────────────┘    └─────────────────┘
```

## Prerequisites

- AWS Account with ECS, Fargate, ALB, Route 53 access
- Docker Hub or AWS ECR for container images
- Domain name configured in Route 53
- ACM SSL certificate for your domain

## Container Configuration

### Backend Dockerfile (`backend/Dockerfile`)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run migrations and collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 9000

# Start Daphne (ASGI server with WebSocket support)
CMD ["daphne", "-b", "0.0.0.0", "-p", "9000", "chatpop.asgi:application"]
```

### Frontend Dockerfile (`frontend/Dockerfile`)

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build Next.js app
RUN npm run build

# Expose port
EXPOSE 4000

# Start production server
ENV NODE_ENV=production
CMD ["node", "server.js"]
```

## ECS Task Definitions

### Backend Task Definition

```json
{
  "family": "chatpop-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "your-registry/chatpop-backend:latest",
      "portMappings": [
        {
          "containerPort": 9000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DJANGO_SETTINGS_MODULE",
          "value": "chatpop.settings"
        },
        {
          "name": "DATABASE_URL",
          "value": "postgresql://user:pass@rds-endpoint:5432/chatpop"
        },
        {
          "name": "REDIS_URL",
          "value": "redis://elasticache-endpoint:6379/0"
        },
        {
          "name": "ALLOWED_HOSTS",
          "value": "chatpop.app,*.chatpop.app"
        },
        {
          "name": "CORS_ALLOWED_ORIGINS",
          "value": "https://chatpop.app"
        }
      ],
      "secrets": [
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:chatpop/django-secret"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:9000/api/health/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/chatpop-backend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Frontend Task Definition

```json
{
  "family": "chatpop-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "your-registry/chatpop-frontend:latest",
      "portMappings": [
        {
          "containerPort": 4000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:4000/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/chatpop-frontend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

## Application Load Balancer Configuration

### Target Groups

**Backend Target Group:**
- Name: `chatpop-backend-tg`
- Protocol: HTTP
- Port: 9000
- Target type: IP (for Fargate)
- Health check path: `/api/health/`
- Health check interval: 30 seconds
- Healthy threshold: 2
- Unhealthy threshold: 3

**Frontend Target Group:**
- Name: `chatpop-frontend-tg`
- Protocol: HTTP
- Port: 4000
- Target type: IP (for Fargate)
- Health check path: `/`
- Health check interval: 30 seconds
- Healthy threshold: 2
- Unhealthy threshold: 3

### Listener Rules (HTTPS:443)

**Priority 1:** Path pattern `/api/*`
- Forward to: `chatpop-backend-tg`

**Priority 2:** Path pattern `/media/*`
- Forward to: `chatpop-backend-tg`

**Priority 3:** Path pattern `/ws/*`
- Forward to: `chatpop-backend-tg`
- **Important:** Enable WebSocket support on this rule

**Default:** Path pattern `/*`
- Forward to: `chatpop-frontend-tg`

### ALB WebSocket Configuration

Enable WebSocket support on the ALB:
1. Target group settings → Attributes → Enable sticky sessions (for WebSocket connections)
2. Stickiness type: `lb_cookie`
3. Duration: 1 day (86400 seconds)

## Environment Variables

### Backend Required Variables

- `SECRET_KEY` - Django secret key (use AWS Secrets Manager)
- `DATABASE_URL` - PostgreSQL connection string (RDS)
- `REDIS_URL` - Redis connection string (ElastiCache)
- `ALLOWED_HOSTS` - Your domain(s)
- `CORS_ALLOWED_ORIGINS` - Frontend domain
- `AWS_STORAGE_BUCKET_NAME` - S3 bucket for media files
- `AWS_ACCESS_KEY_ID` - S3 access (use IAM role instead if possible)
- `AWS_SECRET_ACCESS_KEY` - S3 secret (use IAM role instead if possible)

### Frontend Required Variables

- `NODE_ENV=production` - Disables development proxy
- No other variables needed (uses relative URLs)

## Database & Cache

### RDS PostgreSQL
- Engine: PostgreSQL 15+
- Instance: db.t3.medium or larger
- Multi-AZ: Yes (for production)
- Automated backups: Yes
- Encryption: Yes

### ElastiCache Redis
- Engine: Redis 7.0+
- Node type: cache.t3.medium or larger
- Number of replicas: 1+ (for production)
- Multi-AZ: Yes
- Encryption: Yes (in-transit and at-rest)

## Media Storage (S3)

Create an S3 bucket for user-generated media:
- Bucket name: `chatpop-media-production`
- Region: Same as ECS cluster
- Public access: Block all (use CloudFront)
- Versioning: Enabled
- Encryption: AES-256

Configure Django to use S3:
```python
# settings.py (production)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'chatpop-media-production'
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
```

## Deployment Steps

### 1. Build and Push Docker Images

```bash
# Backend
cd backend
docker build -t your-registry/chatpop-backend:latest .
docker push your-registry/chatpop-backend:latest

# Frontend
cd ../frontend
docker build -t your-registry/chatpop-frontend:latest .
docker push your-registry/chatpop-frontend:latest
```

### 2. Create RDS and ElastiCache

Use AWS Console or Terraform to provision:
- RDS PostgreSQL instance
- ElastiCache Redis cluster
- Security groups allowing ECS tasks to connect

### 3. Run Database Migrations

Use ECS one-off task:
```bash
aws ecs run-task \
  --cluster chatpop-cluster \
  --task-definition chatpop-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}" \
  --overrides '{"containerOverrides":[{"name":"backend","command":["python","manage.py","migrate"]}]}'
```

### 4. Create ECS Services

```bash
# Backend service
aws ecs create-service \
  --cluster chatpop-cluster \
  --service-name chatpop-backend \
  --task-definition chatpop-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx]}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=backend,containerPort=9000"

# Frontend service
aws ecs create-service \
  --cluster chatpop-cluster \
  --service-name chatpop-frontend \
  --task-definition chatpop-frontend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx]}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=frontend,containerPort=4000"
```

### 5. Configure Route 53

Create A record:
- Name: `chatpop.app`
- Type: A (Alias)
- Alias target: Your ALB
- Routing policy: Simple

## Monitoring & Logging

### CloudWatch Logs
- Backend logs: `/ecs/chatpop-backend`
- Frontend logs: `/ecs/chatpop-frontend`

### CloudWatch Alarms
- Target group unhealthy hosts
- ECS service CPU/memory usage
- ALB 5xx errors
- RDS CPU/storage
- ElastiCache memory usage

### Application Performance Monitoring
Consider adding:
- AWS X-Ray for distributed tracing
- Sentry for error tracking
- DataDog/New Relic for APM

## Scaling Configuration

### Auto Scaling Policies

**Backend Service:**
```json
{
  "MinCapacity": 2,
  "MaxCapacity": 10,
  "TargetValue": 70.0,
  "ScaleInCooldown": 300,
  "ScaleOutCooldown": 60,
  "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
}
```

**Frontend Service:**
```json
{
  "MinCapacity": 2,
  "MaxCapacity": 10,
  "TargetValue": 70.0,
  "ScaleInCooldown": 300,
  "ScaleOutCooldown": 60,
  "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
}
```

## Cost Optimization

- Use Fargate Spot for non-critical workloads
- Right-size task CPU/memory after monitoring
- Use RDS reserved instances for predictable workloads
- Enable S3 lifecycle policies for old media
- Use CloudFront CDN to reduce ALB traffic

## Security Best Practices

1. **Use AWS Secrets Manager** for sensitive data (SECRET_KEY, DB passwords)
2. **Enable VPC Flow Logs** for network monitoring
3. **Use security groups** to restrict traffic between services
4. **Enable ALB access logs** for audit trail
5. **Use IAM roles** instead of hardcoded credentials
6. **Enable AWS WAF** on ALB for DDoS protection
7. **Encrypt data at rest** (RDS, ElastiCache, S3)
8. **Encrypt data in transit** (SSL/TLS everywhere)

## Disaster Recovery

- **Database backups:** Automated daily snapshots (RDS)
- **Point-in-time recovery:** Enabled on RDS
- **Multi-AZ deployment:** Yes for RDS and ElastiCache
- **Cross-region replication:** Consider for S3 media files
- **Infrastructure as Code:** Use Terraform/CloudFormation

## Summary: Development vs Production

| Feature | Development | Production |
|---------|-------------|------------|
| API Routing | Next.js proxy | ALB path-based routing |
| WebSocket | Next.js proxy | ALB WebSocket support |
| SSL | Self-signed cert | ACM certificate |
| Database | Local Docker | RDS PostgreSQL |
| Cache | Local Docker | ElastiCache Redis |
| Media Storage | Local filesystem | S3 + CloudFront |
| Scaling | Single instance | Auto-scaling (2-10 tasks) |

The changes we made today (relative URLs, dynamic WebSocket construction) are **production-ready** and will work seamlessly with ALB! 🚀
