# AWS Deployment & Scaling Guide

## Architecture Overview

ChatPop uses a serverless compute architecture on AWS for production deployment:

```
Users (WebSocket)
    ↓
Application Load Balancer (ALB)
    ↓
ECS Fargate (Daphne ASGI containers)
    ↓
┌─────────────────┬──────────────────────┐
│                 │                      │
ElastiCache       RDS PostgreSQL    RDS Proxy
(Redis)           (Primary)         (Connection Pool)
    │                 │
    │                 └─ Read Replica (at scale)
    │
Django Channels
(WebSocket pub/sub)
```

**Key Components:**
- **ECS Fargate**: Serverless containers running Daphne (WebSocket server)
- **Application Load Balancer**: Routes WebSocket connections with sticky sessions
- **ElastiCache Redis**: Django Channels backend for WebSocket pub/sub
- **RDS PostgreSQL**: Primary database (messages, users, participation)
- **RDS Proxy**: Connection pooling (required at 1000+ rooms)
- **RDS Read Replica**: Query offloading (required at 5000+ rooms)

---

## Why ECS Fargate + ALB?

### Comparison: EC2 vs Fargate

| Factor | EC2 + ASG | ECS Fargate | Winner |
|--------|-----------|-------------|--------|
| **Management** | Patch OS, configure ASG, manage instances | Zero (AWS manages) | **Fargate** |
| **Auto-scaling speed** | 2-3 minutes (EC2 boot time) | 30 seconds (container start) | **Fargate** |
| **Cost (variable load)** | Pay 24/7 even if idle | Pay per vCPU-second | **Fargate** |
| **Cost (sustained load)** | ~30% cheaper | More expensive | **EC2** |
| **Deploy complexity** | AMI builds, ASG, health checks | Docker push → ECS deploy | **Fargate** |
| **Cold start** | Must keep instances warm | Tasks start in 30s | **Fargate** |

**For ChatPop:** Fargate is ideal because:
1. **Variable load** (not all rooms active 24/7)
2. **Faster scaling** for viral chats (30s vs 3min)
3. **Less DevOps overhead** (no OS patching, no ASG configuration)
4. **Only 10-20% more expensive** than EC2 at target scale
5. **Better for startup** (deploy Docker image, done)

---

## Scaling Targets & Infrastructure

### **Scale 1: Small (100 rooms × 10 users = 1,000 connections)**

**Infrastructure:**
- **ECS Fargate**: 1 task (0.5 vCPU, 1 GB RAM)
- **ALB**: 1 load balancer
- **ElastiCache**: 1x `cache.t3.micro` (0.5 GB RAM)
- **RDS**: 1x `db.t3.small` (2 vCPU, 2 GB RAM, 50 GB storage)

**Message throughput:** ~20 messages/second system-wide

**Monthly cost breakdown:**
- ECS Fargate (1 task): ~$22/month
- ALB: ~$20/month
- ElastiCache: ~$12/month
- RDS PostgreSQL: ~$40/month
- **Total: ~$94/month**

**Optimizations:**
- ✅ Basic indexes (required)
- ❌ RDS Proxy (not needed)
- ❌ Read replicas (not needed)
- ❌ Outbox pattern (optional)

**Deployment:**
- Single ECS service with 1 task
- Auto-scaling: 1-2 tasks (scale up on CPU > 70%)

---

### **Scale 2: Medium (1,000 rooms × 20 users = 20,000 connections)**

**Infrastructure:**
- **ECS Fargate**: 4 tasks (0.5 vCPU, 1 GB RAM each)
- **ALB**: 1 load balancer
- **ElastiCache**: 1x `cache.t3.small` (1.4 GB RAM)
- **RDS**: 1x `db.t3.medium` (2 vCPU, 4 GB RAM, 100 GB storage)
- **RDS Proxy**: 1 proxy (connection pooling)

**Message throughput:** ~200 messages/second system-wide

**Monthly cost breakdown:**
- ECS Fargate (4 tasks): ~$90/month
- ALB: ~$20/month
- ElastiCache: ~$25/month
- RDS PostgreSQL: ~$70/month
- RDS Proxy: ~$15/month
- **Total: ~$220/month**

**Optimizations:**
- ✅ Indexes (required)
- ✅ RDS Proxy (required for connection pooling)
- ❌ Read replicas (not needed yet)
- ✅ Outbox pattern (recommended for durability)

**Deployment:**
- Single ECS service with 4 tasks
- Auto-scaling: 2-6 tasks (scale on CPU > 70% or connection count)

---

### **Scale 3: Large (5,000 rooms × 50 users = 250,000 connections)**

**Infrastructure:**
- **ECS Fargate**: 25 tasks (0.5 vCPU, 1 GB RAM each)
- **ALB**: 1 load balancer
- **ElastiCache**: 1x `cache.m5.large` (6.4 GB RAM)
- **RDS Primary**: 1x `db.m5.large` (2 vCPU, 8 GB RAM, 200 GB storage)
- **RDS Read Replica**: 1x `db.m5.large` (for query offloading)
- **RDS Proxy**: 1 proxy

**Message throughput:** ~1,000 messages/second system-wide

**Monthly cost breakdown:**
- ECS Fargate (25 tasks): ~$550/month
- ALB: ~$20/month
- ElastiCache: ~$100/month
- RDS Primary: ~$180/month
- RDS Read Replica: ~$180/month
- RDS Proxy: ~$15/month
- **Total: ~$1,045/month**

**Optimizations:**
- ✅ Indexes (required)
- ✅ RDS Proxy (required)
- ✅ Read replicas (required for query load)
- ✅ Outbox pattern (required for durability)
- ⚠️ Table partitioning (if >10M messages)

**Deployment:**
- Single ECS service with 25 tasks
- Auto-scaling: 10-40 tasks (scale on CPU > 70% or connection count)

---

## Initial Setup: Deploying to ECS Fargate

### **Phase 1: Dockerize the Application**

#### **1.1: Create Dockerfile**

Create `Dockerfile` in project root:

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/

# Collect static files (if needed)
RUN python manage.py collectstatic --noinput || true

# Expose port
EXPOSE 9000

# Run Daphne ASGI server
CMD ["daphne", "-b", "0.0.0.0", "-p", "9000", "chatpop.asgi:application"]
```

#### **1.2: Create .dockerignore**

```
# .dockerignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
*.sqlite3
.env
.git
.gitignore
node_modules/
frontend/
docs/
*.md
.vscode/
.idea/
```

#### **1.3: Build and Test Locally**

```bash
# Build Docker image
docker build -t chatpop-backend:latest .

# Test locally (ensure Docker Compose is running for PostgreSQL + Redis)
docker run -p 9000:9000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e REDIS_HOST=host.docker.internal \
  -e DJANGO_SECRET_KEY=test \
  -e DEBUG=True \
  chatpop-backend:latest
```

**Verify:** Open browser to `http://localhost:9000/admin` (should see Django admin)

---

### **Phase 2: Push Docker Image to ECR**

#### **2.1: Create ECR Repository**

```bash
# Create ECR repository
aws ecr create-repository \
  --repository-name chatpop-backend \
  --region us-east-1

# Output: {"repository": {"repositoryUri": "123456789.dkr.ecr.us-east-1.amazonaws.com/chatpop-backend"}}
```

#### **2.2: Build and Push Image**

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com

# Build image with ECR tag
docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/chatpop-backend:latest .

# Push to ECR
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/chatpop-backend:latest
```

---

### **Phase 3: Set Up AWS Infrastructure**

#### **3.1: Create RDS PostgreSQL Database**

**Via AWS Console:**
1. Navigate to **RDS** → **Create database**
2. Choose **PostgreSQL 15.x**
3. Template: **Dev/Test** (or Production for prod)
4. Instance: `db.t3.small` (for small scale) or `db.t3.medium` (for medium scale)
5. Storage: 50 GB GP3 (auto-scaling enabled)
6. **IMPORTANT:** Note the master username, password, and endpoint

**Via AWS CLI:**
```bash
aws rds create-db-instance \
  --db-instance-identifier chatpop-db \
  --db-instance-class db.t3.small \
  --engine postgres \
  --master-username chatpop_admin \
  --master-user-password YOUR_PASSWORD \
  --allocated-storage 50 \
  --vpc-security-group-ids sg-xxxxxx \
  --db-subnet-group-name default \
  --publicly-accessible
```

**Run migrations:**
```bash
# Connect to RDS and run migrations
export DATABASE_URL="postgresql://chatpop_admin:PASSWORD@chatpop-db.xxx.us-east-1.rds.amazonaws.com:5432/postgres"
./venv/bin/python manage.py migrate
```

#### **3.2: Create ElastiCache Redis Cluster**

**Via AWS Console:**
1. Navigate to **ElastiCache** → **Create Redis cluster**
2. Cluster mode: **Disabled** (simpler)
3. Node type: `cache.t3.micro` (small) or `cache.t3.small` (medium)
4. Number of replicas: 0 (single node for now)
5. **IMPORTANT:** Note the primary endpoint

**Via AWS CLI:**
```bash
aws elasticache create-cache-cluster \
  --cache-cluster-id chatpop-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --security-group-ids sg-xxxxxx
```

#### **3.3: Create Application Load Balancer**

**Via AWS Console:**
1. Navigate to **EC2** → **Load Balancers** → **Create Load Balancer**
2. Type: **Application Load Balancer**
3. Scheme: **Internet-facing**
4. Listeners: HTTP (port 80), HTTPS (port 443, optional)
5. Availability Zones: Select at least 2 AZs
6. Security Group: Allow inbound 80, 443

**Create Target Group:**
1. Target type: **IP addresses** (for Fargate)
2. Protocol: **HTTP**
3. Port: **9000**
4. Health check path: `/admin/login/` (Django endpoint)
5. Health check interval: 30 seconds
6. **IMPORTANT:** Enable **stickiness** (required for WebSockets)
   - Type: **Application-based cookie**
   - Duration: 86400 seconds (24 hours)

---

### **Phase 4: Create ECS Fargate Service**

#### **4.1: Create ECS Cluster**

```bash
aws ecs create-cluster --cluster-name chatpop-cluster
```

#### **4.2: Create Task Definition**

Create `ecs-task-definition.json`:

```json
{
  "family": "chatpop-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::123456789:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "chatpop-backend",
      "image": "123456789.dkr.ecr.us-east-1.amazonaws.com/chatpop-backend:latest",
      "portMappings": [
        {
          "containerPort": 9000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "POSTGRES_HOST", "value": "chatpop-db.xxx.us-east-1.rds.amazonaws.com"},
        {"name": "POSTGRES_DB", "value": "postgres"},
        {"name": "POSTGRES_USER", "value": "chatpop_admin"},
        {"name": "POSTGRES_PORT", "value": "5432"},
        {"name": "REDIS_HOST", "value": "chatpop-redis.xxx.cache.amazonaws.com"},
        {"name": "REDIS_PORT", "value": "6379"},
        {"name": "DEBUG", "value": "False"},
        {"name": "ALLOWED_HOSTS", "value": "your-alb-dns.us-east-1.elb.amazonaws.com"}
      ],
      "secrets": [
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:chatpop-db-password"
        },
        {
          "name": "DJANGO_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:django-secret-key"
        }
      ],
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

**Register task definition:**
```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

#### **4.3: Create ECS Service**

```bash
aws ecs create-service \
  --cluster chatpop-cluster \
  --service-name chatpop-backend-service \
  --task-definition chatpop-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-zzz],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789:targetgroup/chatpop-tg/xxx,containerName=chatpop-backend,containerPort=9000"
```

---

### **Phase 5: Configure Auto-Scaling**

#### **5.1: Auto-Scaling Based on CPU**

```bash
# Register scalable target (min 2, max 10 tasks)
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-backend-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy (scale up if CPU > 70%)
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-backend-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'
```

#### **5.2: Auto-Scaling Based on ALB Request Count (Optional)**

```bash
# Scale based on requests per target (e.g., 1000 requests/target)
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-backend-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name alb-request-count-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 1000.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ALBRequestCountPerTarget",
      "ResourceLabel": "app/chatpop-alb/xxx/targetgroup/chatpop-tg/yyy"
    }
  }'
```

---

## Required Database Optimizations

### **Indexes (Required for ALL scales)**

Run these immediately after deploying to production:

```sql
-- Connect to RDS PostgreSQL
psql postgresql://chatpop_admin:PASSWORD@chatpop-db.xxx.us-east-1.rds.amazonaws.com:5432/postgres

-- Messages table indexes
CREATE INDEX CONCURRENTLY idx_messages_room_created
ON chats_message (chat_room_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_messages_room_active
ON chats_message (chat_room_id, is_deleted, created_at DESC)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY idx_messages_reply_to
ON chats_message (reply_to_id)
WHERE reply_to_id IS NOT NULL;

-- Chat participation indexes
CREATE INDEX CONCURRENTLY idx_participation_room_active
ON chats_chatparticipation (chat_room_id, is_active);

CREATE INDEX CONCURRENTLY idx_participation_user
ON chats_chatparticipation (user_id, chat_room_id);

CREATE INDEX CONCURRENTLY idx_participation_fingerprint
ON chats_chatparticipation (fingerprint, chat_room_id)
WHERE fingerprint IS NOT NULL;

-- Chat room code lookup (already has unique constraint, but add index for performance)
CREATE INDEX CONCURRENTLY idx_chatroom_code
ON chats_chatroom (code);

-- Outbox events (if using outbox pattern)
CREATE INDEX CONCURRENTLY idx_outbox_unprocessed
ON chats_outboxevent (processed, created_at)
WHERE processed = false;

CREATE INDEX CONCURRENTLY idx_outbox_room_created
ON chats_outboxevent (chat_code, created_at);
```

**Note:** `CREATE INDEX CONCURRENTLY` allows queries to continue during index creation (important for zero-downtime deployment).

**Verify indexes:**
```sql
-- Check index sizes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

### **RDS Parameter Group Tuning**

Create a custom RDS parameter group with these settings:

```ini
# Connection settings
max_connections = 200  # RDS Proxy will handle pooling

# Memory settings (for db.t3.medium with 4 GB RAM)
shared_buffers = 1GB  # 25% of RAM
effective_cache_size = 3GB  # 75% of RAM
work_mem = 4MB  # Per-query memory
maintenance_work_mem = 256MB  # For VACUUM, CREATE INDEX

# Checkpoint settings (reduce write spikes)
checkpoint_completion_target = 0.9
wal_buffers = 16MB
min_wal_size = 1GB
max_wal_size = 4GB

# Query planner settings (SSD-optimized)
random_page_cost = 1.1  # RDS uses SSDs (default is 4.0 for HDDs)
effective_io_concurrency = 200  # SSD parallelism

# Logging (for troubleshooting)
log_min_duration_statement = 500  # Log queries slower than 500ms
log_connections = on
log_disconnections = on
```

**Apply parameter group:**
```bash
# Create parameter group
aws rds create-db-parameter-group \
  --db-parameter-group-name chatpop-pg15 \
  --db-parameter-group-family postgres15 \
  --description "ChatPop optimized settings"

# Modify parameters (repeat for each setting above)
aws rds modify-db-parameter-group \
  --db-parameter-group-name chatpop-pg15 \
  --parameters "ParameterName=shared_buffers,ParameterValue=1048576,ApplyMethod=pending-reboot"

# Apply to RDS instance
aws rds modify-db-instance \
  --db-instance-identifier chatpop-db \
  --db-parameter-group-name chatpop-pg15 \
  --apply-immediately
```

---

## RDS Proxy Setup (Required at 1000+ rooms)

### **Why RDS Proxy?**

Without connection pooling, Django creates a new PostgreSQL connection for every request:
- ❌ **10,000 requests/sec** = 10,000 connections (PostgreSQL max is ~200)
- ❌ **Connection overhead** = ~10ms per connection
- ❌ **Memory exhaustion** on database (each connection uses ~10MB)

**RDS Proxy solves this:**
- ✅ Connection pooling (reuse connections)
- ✅ Automatic failover (switches to standby if primary fails)
- ✅ IAM authentication (no passwords in environment variables)
- ✅ ~$15/month per proxy

### **Create RDS Proxy**

```bash
# Create proxy
aws rds create-db-proxy \
  --db-proxy-name chatpop-proxy \
  --engine-family POSTGRESQL \
  --auth '[{"AuthScheme":"SECRETS","SecretArn":"arn:aws:secretsmanager:us-east-1:123456789:secret:chatpop-db-password","IAMAuth":"DISABLED"}]' \
  --role-arn arn:aws:iam::123456789:role/RDSProxyRole \
  --vpc-subnet-ids subnet-xxx subnet-yyy \
  --require-tls false

# Register RDS instance with proxy
aws rds register-db-proxy-targets \
  --db-proxy-name chatpop-proxy \
  --db-instance-identifiers chatpop-db
```

### **Update Django Settings to Use Proxy**

```python
# backend/chatpop/settings.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "chatpop-proxy.proxy-xxx.us-east-1.rds.amazonaws.com",  # Proxy endpoint
        "PORT": "5432",
        "NAME": os.getenv("POSTGRES_DB", "postgres"),
        "USER": os.getenv("POSTGRES_USER", "chatpop_admin"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "CONN_MAX_AGE": 0,  # Don't hold connections (let proxy pool)
    }
}
```

**Update ECS task definition** to use proxy endpoint instead of direct RDS endpoint.

---

## Read Replicas (Required at 5000+ rooms)

### **Why Read Replicas?**

At scale, **read queries** (initial page load, pagination) can overwhelm the primary database:
- 5,000 rooms × 50 users × 1 refresh/min = ~4,000 reads/minute
- Offload reads to replica → reduce primary load by 60-80%

### **Create Read Replica**

```bash
aws rds create-db-instance-read-replica \
  --db-instance-identifier chatpop-db-replica \
  --source-db-instance-identifier chatpop-db \
  --db-instance-class db.m5.large \
  --publicly-accessible
```

### **Configure Django Database Router**

```python
# backend/chats/db_router.py

class ChatReadReplicaRouter:
    """
    Route read queries to read replica, write queries to primary.
    """

    def db_for_read(self, model, **hints):
        """
        Reads go to replica if available.
        """
        if model._meta.app_label == 'chats':
            # Check if this is a readonly query
            if hints.get('readonly', False):
                return 'read_replica'
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Writes always go to primary.
        """
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations within the same database.
        """
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only migrate on primary database.
        """
        return db == 'default'
```

**Update settings.py:**

```python
# backend/chatpop/settings.py

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'chatpop-proxy.proxy-xxx.us-east-1.rds.amazonaws.com',  # Primary via proxy
        'PORT': '5432',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'CONN_MAX_AGE': 0,
    },
    'read_replica': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'chatpop-db-replica.xxx.us-east-1.rds.amazonaws.com',  # Read replica
        'PORT': '5432',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'CONN_MAX_AGE': 0,
    },
}

DATABASE_ROUTERS = ['chats.db_router.ChatReadReplicaRouter']
```

**Update views to use read replica:**

```python
# backend/chats/views.py (MessageListView)

def _fetch_from_db(self, chat_room, limit, before_timestamp=None, request=None):
    """
    Fetch messages from PostgreSQL (use read replica for performance).
    """
    queryset = Message.objects.using('read_replica').filter(  # ← Use read replica
        chat_room=chat_room,
        is_deleted=False
    ).select_related('user', 'reply_to').prefetch_related('reactions')

    # ... rest of query logic
```

---

## Monitoring & Alerts

### **CloudWatch Metrics to Monitor**

**ECS Fargate:**
- `CPUUtilization` > 70% (trigger scale-up)
- `MemoryUtilization` > 80% (increase task memory)
- `TargetConnectionErrorCount` (ALB → ECS errors)

**RDS PostgreSQL:**
- `CPUUtilization` > 80% (upgrade instance class)
- `DatabaseConnections` > 180 (add RDS Proxy or increase max_connections)
- `ReadLatency` / `WriteLatency` > 20ms (check slow queries)
- `FreeableMemory` < 500MB (increase RAM)

**ElastiCache Redis:**
- `CPUUtilization` > 70% (upgrade node type)
- `EngineCPUUtilization` > 80% (Redis-specific CPU)
- `DatabaseMemoryUsagePercentage` > 80% (upgrade node type)
- `CurrConnections` (monitor WebSocket connection count)

**ALB:**
- `TargetResponseTime` > 500ms (backend slow)
- `UnHealthyHostCount` > 0 (ECS tasks failing health checks)
- `HTTPCode_Target_5XX_Count` (application errors)

### **CloudWatch Alarms**

Example alarm for high RDS CPU:

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name chatpop-rds-high-cpu \
  --alarm-description "RDS CPU above 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/RDS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2 \
  --dimensions Name=DBInstanceIdentifier,Value=chatpop-db \
  --alarm-actions arn:aws:sns:us-east-1:123456789:chatpop-alerts
```

---

## Deployment Workflow (CI/CD)

### **GitHub Actions Example**

```yaml
# .github/workflows/deploy-ecs.yml

name: Deploy to ECS Fargate

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: chatpop-backend
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster chatpop-cluster \
            --service chatpop-backend-service \
            --force-new-deployment
```

---

## Scaling Limits & When to Upgrade

### **ECS Fargate Task Limits**

| Component | Soft Limit | Hard Limit | Action if Exceeded |
|-----------|------------|------------|-------------------|
| **Tasks per service** | 1,000 | 10,000 | Request limit increase |
| **vCPU per task** | 4 vCPU | 16 vCPU | Use larger tasks |
| **Memory per task** | 8 GB | 120 GB | Use larger tasks |
| **Tasks per cluster** | 10,000 | No limit | Create multiple clusters |

**When to upgrade task size:**
- CPU > 80% sustained → Increase from 0.5 vCPU to 1 vCPU
- Memory > 90% → Increase from 1 GB to 2 GB

### **RDS PostgreSQL Connection Limits**

| Instance Class | Max Connections | Recommended Tasks | Use RDS Proxy? |
|----------------|-----------------|-------------------|----------------|
| `db.t3.small` | 200 | <10 | Optional |
| `db.t3.medium` | 400 | 10-50 | **Yes** |
| `db.m5.large` | 800 | 50-200 | **Yes** |
| `db.m5.xlarge` | 1600 | 200-500 | **Yes** |

**Connection calculation:**
- Each Daphne task uses ~5-10 PostgreSQL connections
- 50 tasks × 10 connections = 500 connections → Need `db.m5.large` + RDS Proxy

### **ElastiCache Redis Memory Requirements**

| WebSocket Connections | Redis Memory Needed | Node Type | Cost/Month |
|----------------------|---------------------|-----------|------------|
| <5,000 | <500 MB | `cache.t3.micro` | $12 |
| 5,000-20,000 | 500 MB - 1.4 GB | `cache.t3.small` | $25 |
| 20,000-100,000 | 1.4 GB - 6 GB | `cache.m5.large` | $100 |
| 100,000-500,000 | 6 GB - 25 GB | `cache.m5.4xlarge` | $400 |

**Redis memory calculation:**
- ~1 KB per WebSocket connection (Django Channels metadata)
- 20,000 connections × 1 KB = ~20 MB (plus overhead = 100-200 MB total)

---

## Summary Checklist

### **Before Launch (All Scales)**
- [ ] Dockerize application (Dockerfile)
- [ ] Create ECR repository and push image
- [ ] Set up RDS PostgreSQL (db.t3.small minimum)
- [ ] Run database migrations
- [ ] Create required indexes (see SQL above)
- [ ] Set up ElastiCache Redis (cache.t3.micro minimum)
- [ ] Create Application Load Balancer with sticky sessions
- [ ] Create ECS Fargate task definition
- [ ] Deploy ECS service (1-2 tasks minimum)
- [ ] Configure auto-scaling (CPU-based)
- [ ] Set up CloudWatch alarms (RDS CPU, ECS CPU, ALB errors)

### **At 1000+ Rooms (Medium Scale)**
- [ ] Add RDS Proxy for connection pooling
- [ ] Update ECS task definition to use RDS Proxy endpoint
- [ ] Increase RDS instance to db.t3.medium
- [ ] Increase ElastiCache to cache.t3.small
- [ ] Scale ECS service to 4-6 tasks
- [ ] Consider implementing outbox pattern for durability

### **At 5000+ Rooms (Large Scale)**
- [ ] Create RDS Read Replica
- [ ] Implement database router for read/write splitting
- [ ] Update views to use read replica for queries
- [ ] Upgrade RDS to db.m5.large (primary + replica)
- [ ] Upgrade ElastiCache to cache.m5.large
- [ ] Scale ECS service to 20-30 tasks
- [ ] Implement outbox pattern (required for durability at this scale)
- [ ] Consider table partitioning if >10M messages

---

## Cost Optimization Tips

1. **Use Savings Plans**: Commit to 1-year Compute Savings Plan (30% discount on Fargate)
2. **Reserved Instances**: For RDS and ElastiCache (40-60% discount)
3. **Spot Instances**: Use for non-critical tasks (outbox relay, background jobs)
4. **Auto-scaling**: Scale down during off-peak hours (nights, weekends)
5. **S3 for voice messages**: Cheaper than EBS volumes ($0.023/GB vs $0.10/GB)
6. **CloudWatch Logs retention**: Set to 7-30 days (default is infinite)

---

## Next Steps

1. **Local testing**: Build and test Docker image locally
2. **AWS account setup**: Create ECR, RDS, ElastiCache, ALB
3. **Deploy to staging**: Test with 1 ECS task
4. **Load testing**: Use Locust or k6 to simulate 1000+ WebSocket connections
5. **Production deployment**: Scale up to target task count
6. **Monitoring**: Set up CloudWatch dashboards and alarms

For questions or issues, see:
- [AWS ECS Fargate Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [Django Channels Deployment](https://channels.readthedocs.io/en/stable/deploying.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
