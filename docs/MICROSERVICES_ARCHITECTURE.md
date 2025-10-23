# Microservices Architecture Guide

## Overview

This document describes how to split ChatPop from a monolith into microservices when scaling beyond Phase 1 (500+ concurrent users). It complements [AWS_DEPLOYMENT_SCALING.md](./AWS_DEPLOYMENT_SCALING.md) which covers monolithic deployment patterns.

**When to use this guide:**
- You're hitting 500+ concurrent WebSocket connections
- Photo analysis is causing WebSocket latency spikes
- You need independent scaling for different workloads
- You're approaching 1M+ messages/day

---

## Key Architectural Insight: Service Communication

**ChatPop's service architecture is simpler than typical microservices.**

### Communication Patterns

**Photo Analysis Service** (Pure Function - No Communication)
```
Frontend → Photo Service → Returns suggestions → Frontend
                ↓
           No outbound calls
           No events published
           Completely independent
```

**Chat Service** (One-Way Communication)
```
Frontend → Chat Service → Saves message to DB
                ↓
           Publishes event via Redis Pub/Sub
                ↓
         WebSocket Service → Broadcasts to clients
```

**Key Points:**
- ✅ **Photo Service is stateless** - Just input (image) → output (suggestions), no side effects
- ✅ **No Photo→Chat communication** - Frontend calls each service independently
- ⚠️ **Only Chat→WebSocket needs Redis Pub/Sub** - For broadcasting new messages to connected clients
- ✅ **85% ready for Phase 3** - Excellent app isolation, minimal refactoring needed

**User Flow:**
1. User uploads photo → `/api/photo-analysis/upload/` (Photo Service)
2. Returns suggestions
3. User picks suggestion → `/api/chats/create/` (Chat Service)
4. Chat created, no communication back to Photo Service needed

This makes splitting services **much simpler** than typical microservices architectures.

---

## Architecture Evolution Roadmap

### Phase 1: Monolith (Current - Up to 500 Concurrent Users)

**Status:** ✅ Current implementation

**Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│                     Django Monolith                      │
│                     (Daphne ASGI)                       │
│                                                           │
│  • HTTP APIs (photo analysis, chat CRUD)                │
│  • WebSocket connections (Django Channels)              │
│  • Admin panel                                          │
│  • All routes in one process                            │
└─────────────────────────────────────────────────────────┘
           ↓                           ↓
    ┌──────────────┐          ┌──────────────────┐
    │  PostgreSQL  │          │      Redis       │
    │  (Shared DB) │          │  (Shared Cache)  │
    └──────────────┘          └──────────────────┘
```

**Characteristics:**
- Single ECS Fargate service
- Simplest deployment and debugging
- Daphne handles both HTTP and WebSocket
- Good for 500+ concurrent users
- See [AWS_DEPLOYMENT_SCALING.md](./AWS_DEPLOYMENT_SCALING.md) for scaling details

**When to split:** Any of these triggers:
- 500+ concurrent WebSocket connections
- Photo uploads causing WebSocket latency >500ms
- CPU usage >70% sustained during photo processing
- Photo upload queue depth >10

---

### Phase 2: WebSocket Service Separation

**Trigger:** 500+ concurrent WebSocket connections OR photo analysis affecting WebSocket latency

**Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│                     AWS Application                      │
│                      Load Balancer                       │
│                                                           │
│  Path-based routing:                                     │
│  • /ws/* → WebSocket Service (Fargate)                  │
│  • /api/photo-analysis/* → Main Service (Fargate)       │
│  • /api/chats/* → Main Service (Fargate)                │
│  • /* → Main Service (Fargate)                          │
└─────────────────────────────────────────────────────────┘
           ↓                           ↓
    ┌──────────────┐          ┌──────────────────┐
    │  WebSocket   │          │   Main Service   │
    │   Service    │          │  (HTTP + Admin)  │
    │              │          │                  │
    │ • Daphne     │          │ • Photo Analysis │
    │ • Channels   │◄────────►│ • Chat CRUD      │
    │ • Redis      │  Redis   │ • REST APIs      │
    │   Layer      │  Pub/Sub │ • Admin Panel    │
    └──────────────┘          └──────────────────┘
           │                           │
           └───────────┬───────────────┘
                       ↓
              ┌─────────────────┐
              │   PostgreSQL    │
              │   (Shared DB)   │
              └─────────────────┘
              ┌─────────────────┐
              │      Redis      │
              │ (Shared Cache)  │
              └─────────────────┘
```

**Benefits:**
- Independent scaling: WebSocket service scales by connections, Main service scales by CPU
- Isolation: Photo processing doesn't affect WebSocket latency
- Sticky sessions only on WebSocket service (stateful)
- Main service can be stateless (easier to scale)

**Scaling characteristics:**
- WebSocket Service: Scale 2-50 tasks (connection-based)
- Main Service: Scale 2-20 tasks (CPU-based)
- Cost: ~$175-275/month at 500 concurrent users

---

### Phase 3: Full Microservices (Advanced)

**Trigger:** 1M+ messages/day, 10,000+ photos/day, or need independent teams per service

**Architecture:**
```
┌───────────────────────────────────────────────────────────┐
│                  AWS API Gateway / ALB                    │
│                                                             │
│  • /api/photo-analysis/* → Photo Service                  │
│  • /api/chats/* → Chat Service                            │
│  • /ws/* → WebSocket Service                              │
│  • /api/payments/* → Payment Service (future)             │
└───────────────────────────────────────────────────────────┘
        ↓              ↓              ↓              ↓
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  Photo   │  │   Chat   │  │WebSocket │  │ Payment  │
  │ Service  │  │ Service  │  │ Service  │  │ Service  │
  │          │  │          │  │          │  │          │
  │ • Vision │  │ • CRUD   │  │ • Daphne │  │ • Stripe │
  │ • OpenAI │  │ • Redis  │  │ • Pub/Sub│  │ • Billing│
  │ • S3     │  │ • Cache  │  │          │  │          │
  └──────────┘  └──────────┘  └──────────┘  └──────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                       ↓
              ┌─────────────────┐
              │   PostgreSQL    │
              │  (Shared or DB  │
              │   per service)  │
              └─────────────────┘
              ┌─────────────────┐
              │      Redis      │
              │  (Event Bus)    │
              └─────────────────┘
```

**Service boundaries:**
- **Photo Service:** Vision API, caption generation, S3 storage
- **Chat Service:** Chat CRUD, message history, user management
- **WebSocket Service:** Real-time connections, message broadcasting
- **Payment Service:** Stripe, Back Room, pinned messages (future)

**Note:** Phase 3 is unlikely to be needed unless you hit massive scale. Most applications stay in Phase 2.

---

## Implementation Guide: Phase 2 (WebSocket Separation)

### Step 1: Prepare Django Settings Structure

Create modular settings that support multiple service types.

#### Create Settings Directory

```bash
cd backend/chatpop
mkdir -p settings
touch settings/__init__.py
```

#### Settings Module Structure

**`settings/__init__.py`** - Dynamic service loader:
```python
"""
Settings module for ChatPop.
Dynamically loads appropriate settings based on SERVICE_TYPE environment variable.
"""
import os

SERVICE_TYPE = os.environ.get('SERVICE_TYPE', 'monolith')

if SERVICE_TYPE == 'websocket':
    from .websocket import *
elif SERVICE_TYPE == 'main':
    from .main import *
else:
    from .base import *
```

**`settings/base.py`** - Move current `settings.py` here:
```bash
mv chatpop/settings.py chatpop/settings/base.py
```

**`settings/websocket.py`** - WebSocket service configuration:
```python
"""
WebSocket service settings.
Minimal configuration for stateful WebSocket connections.
"""
from .base import *

# Disable unnecessary apps for WebSocket service
INSTALLED_APPS = [
    app for app in INSTALLED_APPS
    if app not in [
        'photo_analysis',  # No photo processing
        'django.contrib.admin',  # No admin panel
    ]
]

# WebSocket-specific optimizations
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('REDIS_HOST', 'localhost'), 6379)],
            "capacity": 5000,  # Higher capacity for WebSocket service
            "expiry": 60,
        },
    },
}

# Read-heavy service: use read replica for database queries
# (Writes still go to primary via Redis Pub/Sub from Main Service)
```

**`settings/main.py`** - Main HTTP service configuration:
```python
"""
Main service settings.
Handles HTTP APIs, photo analysis, and admin panel.
"""
from .base import *

# Keep all apps for main service
# This service handles photo analysis, chat CRUD, and admin

# Photo analysis optimizations
PHOTO_ANALYSIS_MAX_WORKERS = 10  # Higher for CPU-intensive work

# Optional: Disable WebSocket routing (ALB handles routing to WebSocket service)
# ASGI_APPLICATION remains enabled for async photo processing
```

### Step 2: Implement Cross-Service Communication (Redis Pub/Sub)

Create a message bus for services to communicate without direct HTTP calls.

#### Create Message Bus Utility

**`chats/services/message_bus.py`** (NEW FILE):
```python
"""
Message bus for cross-service communication via Redis Pub/Sub.
Allows services to communicate without direct HTTP calls.
"""
import json
import redis
from django.conf import settings

redis_client = redis.from_url(settings.REDIS_URL)

class MessageBus:
    """Publish/Subscribe message bus for inter-service communication."""

    # Channel names
    CHANNEL_NEW_MESSAGE = 'chat:new_message'
    CHANNEL_USER_JOINED = 'chat:user_joined'
    CHANNEL_USER_LEFT = 'chat:user_left'

    @classmethod
    def publish_new_message(cls, chat_code: str, message_data: dict):
        """
        Publish new message event to WebSocket service.
        WebSocket service listens and broadcasts to connected clients.

        Args:
            chat_code: Chat room code
            message_data: Serialized message data (from serializer)
        """
        payload = {
            'chat_code': chat_code,
            'message': message_data,
        }
        redis_client.publish(cls.CHANNEL_NEW_MESSAGE, json.dumps(payload))

    @classmethod
    def publish_user_joined(cls, chat_code: str, username: str):
        """Publish user join event."""
        payload = {
            'chat_code': chat_code,
            'username': username,
        }
        redis_client.publish(cls.CHANNEL_USER_JOINED, json.dumps(payload))

    @classmethod
    def publish_user_left(cls, chat_code: str, username: str):
        """Publish user left event."""
        payload = {
            'chat_code': chat_code,
            'username': username,
        }
        redis_client.publish(cls.CHANNEL_USER_LEFT, json.dumps(payload))

    @classmethod
    def subscribe_to_messages(cls, callback):
        """
        Subscribe to message events (WebSocket service only).

        Args:
            callback: Function to call when message received.
                     Receives parsed message data as argument.
        """
        pubsub = redis_client.pubsub()
        pubsub.subscribe(cls.CHANNEL_NEW_MESSAGE)

        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                callback(data)
```

#### Update Main Service to Publish Events

**`chats/views.py`** - Add message bus publishing:
```python
from .services.message_bus import MessageBus

@api_view(['POST'])
def send_message(request, code):
    """Send a message to a chat room."""
    # ... existing message creation logic ...

    # After saving message to database
    message_data = MessageSerializer(message).data

    # Publish to WebSocket service via Redis Pub/Sub
    MessageBus.publish_new_message(chat_code=code, message_data=message_data)

    return Response(message_data, status=201)
```

#### Update WebSocket Service to Subscribe to Events

**`chats/consumers.py`** - Add Redis Pub/Sub listener:
```python
import asyncio
from .services.message_bus import MessageBus

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # ... existing connect logic ...

        # Start Redis Pub/Sub listener in background
        asyncio.create_task(self.listen_to_message_bus())

    async def listen_to_message_bus(self):
        """
        Listen to Redis Pub/Sub for messages from Main Service.
        Forward messages to WebSocket clients in this chat.
        """
        def callback(data):
            # Forward to WebSocket clients in this chat
            if data['chat_code'] == self.chat_code:
                asyncio.create_task(self.send_json(data['message']))

        # This runs in background, forwarding messages to WebSocket
        await asyncio.to_thread(MessageBus.subscribe_to_messages, callback)
```

### Step 3: Docker Configuration for Phase 2

**`docker-compose.phase2.yml`**:
```yaml
version: '3.8'

services:
  # Shared database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: chatpop
      POSTGRES_USER: chatpop
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5435:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Shared Redis cache
  redis:
    image: redis:7-alpine
    ports:
      - "6381:6379"
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru

  # Main HTTP Service
  main-service:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      SERVICE_TYPE: main
      DATABASE_URL: postgresql://chatpop:${DB_PASSWORD}@postgres:5432/chatpop
      REDIS_URL: redis://redis:6379/0
      DJANGO_SETTINGS_MODULE: chatpop.settings
    ports:
      - "9000:9000"
    depends_on:
      - postgres
      - redis
    command: >
      daphne -b 0.0.0.0 -p 9000
      -e ssl:9000:privateKey=/certs/localhost+3-key.pem:certKey=/certs/localhost+3.pem
      chatpop.asgi:application

  # WebSocket Service
  websocket-service:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      SERVICE_TYPE: websocket
      DATABASE_URL: postgresql://chatpop:${DB_PASSWORD}@postgres:5432/chatpop
      REDIS_URL: redis://redis:6379/0
      DJANGO_SETTINGS_MODULE: chatpop.settings
    ports:
      - "9001:9001"
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 2  # Run multiple WebSocket instances
    command: >
      daphne -b 0.0.0.0 -p 9001
      -e ssl:9001:privateKey=/certs/localhost+3-key.pem:certKey=/certs/localhost+3.pem
      chatpop.asgi:application

volumes:
  postgres_data:
```

**Usage:**
```bash
# Start Phase 2 multi-service environment
docker-compose -f docker-compose.phase2.yml up -d

# Main Service: https://localhost:9000
# WebSocket Service: https://localhost:9001
```

### Step 4: AWS Fargate Configuration for Phase 2

#### ECS Task Definitions

**Main Service Task:**
```json
{
  "family": "chatpop-main",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "main-service",
      "image": "your-ecr-repo/chatpop:latest",
      "environment": [
        {"name": "SERVICE_TYPE", "value": "main"},
        {"name": "DJANGO_SETTINGS_MODULE", "value": "chatpop.settings"}
      ],
      "portMappings": [{"containerPort": 9000, "protocol": "tcp"}]
    }
  ]
}
```

**WebSocket Service Task:**
```json
{
  "family": "chatpop-websocket",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "websocket-service",
      "image": "your-ecr-repo/chatpop:latest",
      "environment": [
        {"name": "SERVICE_TYPE", "value": "websocket"},
        {"name": "DJANGO_SETTINGS_MODULE", "value": "chatpop.settings"}
      ],
      "portMappings": [{"containerPort": 9001, "protocol": "tcp"}]
    }
  ]
}
```

#### ALB Path-Based Routing

**WebSocket Target Group:**
- Enable sticky sessions (required for WebSocket)
- Stickiness type: `lb_cookie`
- Duration: 86400 seconds (24 hours)

**Listener Rules:**
1. Priority 1: `/ws/*` → WebSocket Service Target Group
2. Priority 2: `/api/*` → Main Service Target Group
3. Default: `/*` → Main Service Target Group

#### Auto-Scaling Configuration

**Main Service (CPU-based):**
```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-main-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 20

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-main-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name main-service-cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    }
  }'
```

**WebSocket Service (connection-based):**
```bash
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-websocket-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 50

# Scale based on active connections (custom CloudWatch metric)
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/chatpop-cluster/chatpop-websocket-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name websocket-service-connection-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 5000.0,
    "CustomizedMetricSpecification": {
      "MetricName": "WebSocketConnections",
      "Namespace": "ChatPop",
      "Statistic": "Average"
    }
  }'
```

---

## Phase 3: Full Microservices (Optional)

### Service Boundaries

#### 1. Photo Analysis Service

**Responsibilities:**
- Photo upload handling
- Vision API calls (suggestions)
- Caption generation (embeddings)
- Image storage (S3)

**APIs:**
- `POST /api/photo-analysis/upload/` - Upload and analyze photo
- `GET /api/photo-analysis/{id}/` - Retrieve analysis results

**Scaling:** CPU-based (0.5-1.0 CPU per container)

#### 2. Chat Service

**Responsibilities:**
- Chat CRUD operations
- Message history queries
- User management
- Participation tracking

**APIs:**
- `POST /api/chats/create/` - Create chat room
- `GET /api/chats/{code}/` - Get chat details
- `GET /api/chats/{code}/messages/` - Get message history
- `POST /api/chats/{code}/join/` - Join chat room

**Scaling:** Database connection pool based

#### 3. WebSocket Service

**Responsibilities:**
- Real-time WebSocket connections
- Message broadcasting
- Presence tracking

**APIs:**
- `WS /ws/chat/{code}/` - WebSocket connection

**Scaling:** Connection count based (sticky sessions required)

#### 4. Payment Service (Future)

**Responsibilities:**
- Stripe integration
- Back Room purchases
- Pinned message payments
- Host tipping

**APIs:**
- `POST /api/payments/checkout/` - Create checkout session
- `POST /api/payments/webhook/` - Stripe webhook handler

**Scaling:** Request-based

### Database Strategy

**Recommended:** Shared database (simpler, ACID transactions)

**Alternative:** Database per service (advanced, eventual consistency)

For ChatPop, **shared database** is recommended unless you hit 10,000+ concurrent users.

---

## Cost Comparison

### Phase 1: Monolith
- ECS Fargate: 2-10 tasks × $22/task/month = $44-220/month
- Total infrastructure: ~$150-275/month (including RDS, Redis, ALB)

### Phase 2: WebSocket Separation
- Main Service: 2-20 tasks × $22/task/month = $44-440/month
- WebSocket Service: 2-50 tasks × $10/task/month = $20-500/month
- Total infrastructure: ~$150-1,000/month

### Phase 3: Full Microservices
- Photo Service: 2-10 tasks × $22/task/month = $44-220/month
- Chat Service: 2-10 tasks × $22/task/month = $44-220/month
- WebSocket Service: 2-50 tasks × $10/task/month = $20-500/month
- Payment Service: 2-5 tasks × $10/task/month = $20-50/month
- Total infrastructure: ~$200-1,500/month

**Note:** Costs scale with usage. Phase 2/3 only needed at significant scale.

---

## Monitoring & Debugging

### CloudWatch Metrics

**Phase 2 Metrics:**
- Main Service: CPU, memory, request count
- WebSocket Service: Connection count, message throughput
- Redis: Pub/Sub message rate

**Custom Metrics:**
- WebSocket connections per service instance
- Redis Pub/Sub latency
- Cross-service message delivery time

### Logging Strategy

**Structured logging with service tags:**
```python
import logging

logger = logging.getLogger(__name__)
logger.info('Message published', extra={
    'service': 'main',
    'chat_code': chat_code,
    'message_id': message.id
})
```

**CloudWatch Logs Insights queries:**
```sql
# Find slow cross-service messages
fields @timestamp, service, chat_code, latency
| filter latency > 100
| sort @timestamp desc

# Count messages by service
stats count() by service
| sort count desc
```

---

## Testing Multi-Service Architecture

### Local Testing with Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.phase2.yml up -d

# Test Main Service
curl https://localhost:9000/api/health/

# Test WebSocket Service
wscat -c wss://localhost:9001/ws/chat/TEST123/

# Monitor Redis Pub/Sub
docker-compose exec redis redis-cli MONITOR

# Check logs
docker-compose logs -f main-service
docker-compose logs -f websocket-service
```

### Integration Testing

Create integration tests that verify cross-service communication:

```python
# tests/test_cross_service_communication.py
import pytest
from channels.testing import WebsocketCommunicator
from chats.services.message_bus import MessageBus

@pytest.mark.asyncio
async def test_message_published_to_websocket():
    """Test that messages from Main Service reach WebSocket service."""
    # Connect WebSocket client
    communicator = WebsocketCommunicator(
        application,
        "/ws/chat/TEST123/"
    )
    connected, _ = await communicator.connect()
    assert connected

    # Publish message via message bus (simulates Main Service)
    MessageBus.publish_new_message(
        chat_code='TEST123',
        message_data={'content': 'Hello from main service'}
    )

    # Verify WebSocket client receives message
    response = await communicator.receive_json_from(timeout=2)
    assert response['content'] == 'Hello from main service'

    await communicator.disconnect()
```

---

## Rollback Strategy

If Phase 2/3 causes issues, rollback to monolith:

1. Update ALB listener rules to route all traffic to Main Service
2. Set WebSocket Service desired count to 0
3. Redeploy Main Service with `SERVICE_TYPE=monolith`
4. Monitor for 15 minutes, verify no errors
5. Investigate issues, fix, and re-attempt split

**Rollback time:** <5 minutes (zero downtime)

---

## Summary: When to Split

### Stick with Monolith (Phase 1) if:
- <500 concurrent users
- <1000 photo uploads/day
- WebSocket latency <500ms
- CPU usage <70% sustained

### Move to Phase 2 (WebSocket Separation) if:
- 500+ concurrent WebSocket connections
- Photo processing causing WebSocket lag
- Need independent scaling for stateful vs stateless workloads

### Move to Phase 3 (Full Microservices) if:
- 1M+ messages/day
- 10,000+ photos/day
- Need independent teams per service
- Complex feature isolation required

---

## Related Documentation

- **[AWS_DEPLOYMENT_SCALING.md](./AWS_DEPLOYMENT_SCALING.md)** - Monolithic deployment and scaling guide
- **[DEPLOYMENT_AWS.md](./DEPLOYMENT_AWS.md)** - Practical AWS deployment steps
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Application-level architecture patterns
- **[CACHING.md](./CACHING.md)** - Redis caching architecture

---

**Last Updated:** 2025-01-23
