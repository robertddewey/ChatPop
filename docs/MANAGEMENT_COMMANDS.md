# Management Commands

All commands are run from the `backend/` directory using `./venv/bin/python manage.py <command>`.

---

## Setup Commands

These commands are used during initial installation or when setting up a new environment.

### `create_system_user`

Creates the system user (`discover@chatpop.app`) that owns all AI-generated `/discover` rooms. This user cannot log in - it exists only as an owner record.

```bash
./venv/bin/python manage.py create_system_user
```

Idempotent - safe to run multiple times. The install script runs this automatically.

---

### `create_test_data`

Bootstraps a complete development environment with test users, chat rooms, and sample messages.

```bash
./venv/bin/python manage.py create_test_data
```

**Creates:**
- Superuser: `admin@chatpop.app` (password: `demo123`)
- 4 test users: `jane@chatpop.app`, `john@chatpop.app`, `alice@chatpop.app`, `bob@chatpop.app` (all password: `demo123`)
- User subscriptions (Alice subscribes to Jane and John, Bob subscribes to Jane)
- 2 chat rooms:
  - **Tech Talk Tuesday** - Public, hosted by Jane (voice + photo enabled)
  - **VIP Community** - Private, hosted by John (access code: `VIP2024`, all media enabled)
- 3 sample messages in Tech Talk Tuesday

Idempotent - skips existing records.

---

## Testing & Development Commands

These commands help populate chat rooms with realistic data and test media analysis features.

### `populate_chat`

Populates a chat room with realistic test messages. Supports batch mode (instant) and continuous mode (streamed over time with configurable rate).

**Batch mode** (creates ~30 messages instantly):
```bash
./venv/bin/python manage.py populate_chat jane/tech-talk-tuesday
```

**Continuous mode with WebSocket broadcasting** (messages appear live in the chat):
```bash
# Stream 50 messages at 10 msg/sec
./venv/bin/python manage.py populate_chat jane/tech-talk-tuesday --broadcast --count 50 --rate 10

# Stream for 60 seconds at 2 msg/sec
./venv/bin/python manage.py populate_chat jane/tech-talk-tuesday --broadcast --duration 60 --rate 2
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--broadcast` | off | Send messages via WebSocket (appear live in connected clients) |
| `--count N` | - | Total number of messages to send |
| `--duration N` | - | Duration in seconds to stream messages |
| `--rate N` | 1.0 | Messages per second |

**Message distribution:** 70% anonymous, 20% registered users, 8% host messages, 2% photo messages.

Chat path format is `username/chat-code` (e.g., `jane/tech-talk-tuesday`).

---

### `test_photo_upload`

Tests the photo analysis upload API end-to-end using real images from the test fixtures directory.

```bash
# List available test images
./venv/bin/python manage.py test_photo_upload --list

# Upload a test image
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg

# Force fresh API calls (skip cache)
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg --no-cache

# Use a specific fingerprint
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg --fingerprint my-test-fp
```

Displays the full API response including suggestions, similar rooms, token usage, and rate limit info.

---

### `batch_photo_upload`

Uploads multiple photos in sequence from a JSON config file. Wraps `test_photo_upload` for each photo.

```bash
# Basic batch upload
./venv/bin/python manage.py batch_photo_upload photo_sequence.json

# With 2-second delay between uploads and cache clearing
./venv/bin/python manage.py batch_photo_upload photo_sequence.json --delay 2 --no-cache
```

**JSON file format:**
```json
{
  "photos": [
    "test_coffee_mug.jpeg",
    "test_budweiser_can.jpeg",
    "test_glass_of_beer.png"
  ]
}
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--fingerprint` | `batch-test-fp` | Client fingerprint for all uploads |
| `--no-cache` | off | Clear cached analysis before each upload |
| `--delay N` | 0 | Seconds to wait between uploads |

---

### `generate_location_data`

Generates fake location data for stress testing the lightning strike map. Creates `LocationAnalysis` records with realistic US geographic distribution weighted toward major cities.

```bash
# Default: ~3 points/sec for 60 seconds (~180 points)
./venv/bin/python manage.py generate_location_data

# High volume: 10 points/sec for 5 minutes
./venv/bin/python manage.py generate_location_data --rate 10 --duration 300

# Custom variance and city bias
./venv/bin/python manage.py generate_location_data --rate 5 --duration 120 --variance 15 --city-bias 0.5

# Delete all test data
./venv/bin/python manage.py generate_location_data --delete
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--rate N` | 3.0 | Average points per second |
| `--duration N` | 60 | Duration in seconds |
| `--variance N` | same as rate | Max deviation from rate |
| `--city-bias N` | 0.7 | Probability of generating near a city (0.0-1.0) |
| `--delete` | - | Delete all test data instead of generating |

Test data is marked with a `TEST_DATA_` fingerprint prefix for easy cleanup. Press Ctrl+C to stop gracefully.

---

## Cache & Maintenance Commands

These commands inspect, sync, and manage the Redis cache layer.

### `inspect_redis`

Comprehensive debugging tool for the Redis message cache (hash + index architecture). Supports listing, inspecting, comparing, monitoring, and clearing caches. Shows timeline counts, filter index sizes, pinned messages, and reaction caches.

**List all cached chats:**
```bash
./venv/bin/python manage.py inspect_redis --list
```

**Inspect a specific chat's cache:**
```bash
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --show-messages
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --show-reactions
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --show-messages --limit 20
```

**Compare Redis cache with PostgreSQL:**
```bash
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --compare
```

**Inspect a specific message by UUID:**
```bash
./venv/bin/python manage.py inspect_redis --message 550e8400-e29b-41d4-a716-446655440000
```

**Monitor cache in real-time** (updates every 2 seconds, Ctrl+C to stop):
```bash
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --monitor
```

**Show overall Redis statistics:**
```bash
./venv/bin/python manage.py inspect_redis --stats
```

**Clear a chat's cache** (with confirmation prompt):
```bash
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --clear
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --clear --force
```

---

### `reset_all_chat_data`

Nuclear reset: deletes all messages, gifts, transactions, reactions from PostgreSQL and flushes the entire Redis cache. Useful during development when you want a clean slate.

```bash
# With confirmation prompt
./venv/bin/python manage.py reset_all_chat_data

# Skip confirmation
./venv/bin/python manage.py reset_all_chat_data --confirm
```

**Deletes (in dependency order):**
1. MessageReaction records
2. Gift records
3. Transaction records
4. Message records
5. Redis cache (full `FLUSHDB`)

**Warning:** This is irreversible. Chat rooms and participations are preserved — only message data is wiped.

---

### `sync_reaction_cache`

Syncs message reactions from PostgreSQL to Redis. Useful after database restores or if the cache gets out of sync. Caches the top 3 reactions per message.

```bash
# Sync all active chats
./venv/bin/python manage.py sync_reaction_cache

# Sync a specific chat by code
./venv/bin/python manage.py sync_reaction_cache --chat ABC123
```

---

### `cleanup_expired_photos`

Deletes expired `PhotoAnalysis` records and their associated image files from S3 or local storage.

```bash
# Preview what would be deleted
./venv/bin/python manage.py cleanup_expired_photos --dry-run

# Delete expired photos
./venv/bin/python manage.py cleanup_expired_photos

# Process in larger batches
./venv/bin/python manage.py cleanup_expired_photos --batch-size 500
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | off | Preview deletions without making changes |
| `--batch-size N` | 100 | Records to process per batch |

---

### `backfill_avatars`

Generates missing avatar URLs for registered users and `ChatParticipation` records. Handles three scenarios: proxy URLs for registered users using their reserved username, direct URLs for registered users using a different name, and direct URLs for anonymous users.

```bash
# Dry run (preview changes)
./venv/bin/python manage.py backfill_avatars

# Apply changes
./venv/bin/python manage.py backfill_avatars --apply
```

Always do a dry run first to review what will be changed.

---

## Media Analysis Diagnostic Commands

These commands help diagnose and tune the photo analysis suggestion matching system.

### `browse_suggestions`

Interactive browser for exploring the suggestion database and finding which photos matched each suggestion.

**Non-interactive listing:**
```bash
# List all suggestions
./venv/bin/python manage.py browse_suggestions --list

# Filter by type
./venv/bin/python manage.py browse_suggestions --list --proper-nouns
./venv/bin/python manage.py browse_suggestions --list --generic

# Filter by minimum usage
./venv/bin/python manage.py browse_suggestions --list --min-usage 5

# Search by name or key
./venv/bin/python manage.py browse_suggestions --list --search "coffee"
```

**View details for a specific suggestion:**
```bash
./venv/bin/python manage.py browse_suggestions --suggestion coffee-talk
```

**Interactive mode** (browse and filter with commands):
```bash
./venv/bin/python manage.py browse_suggestions
```

Interactive commands: enter a number to view details, `filter <term>` to search, `proper`/`generic` to filter by type, `reset` to clear filters, `quit` to exit.

---

### `inspect_suggestion_distances`

Diagnostic tool for analyzing cosine distances between suggestion embeddings. Helps determine if the similarity matching threshold is too strict or too loose.

```bash
# Analyze top 15 suggestions by usage
./venv/bin/python manage.py inspect_suggestion_distances

# Analyze more suggestions
./venv/bin/python manage.py inspect_suggestion_distances --top 30

# Query a specific suggestion's nearest neighbors
./venv/bin/python manage.py inspect_suggestion_distances --query "Cheers"

# Show more neighbors per suggestion
./venv/bin/python manage.py inspect_suggestion_distances --query "Coffee Talk" --neighbors 20
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--top N` | 15 | Number of top suggestions to analyze |
| `--query "name"` | - | Analyze a specific suggestion |
| `--neighbors N` | 10 | Nearest neighbors to show per suggestion |

Shows match/no-match status against the current threshold and recommends threshold adjustments for near-miss pairs.

---

### `generate_room_embeddings`

Generates name embeddings for AI-created chat rooms so they can participate in suggestion normalization during photo uploads. Only processes rooms where `source='ai'`.

```bash
# Generate missing embeddings
./venv/bin/python manage.py generate_room_embeddings

# Preview without changes
./venv/bin/python manage.py generate_room_embeddings --dry-run

# Regenerate all embeddings
./venv/bin/python manage.py generate_room_embeddings --force-refresh

# Limit number of rooms processed
./venv/bin/python manage.py generate_room_embeddings --limit 50

# Adjust batch size (for rate limiting)
./venv/bin/python manage.py generate_room_embeddings --batch-size 5
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--limit N` | all | Maximum rooms to process |
| `--force-refresh` | off | Regenerate existing embeddings |
| `--dry-run` | off | Preview without changes |
| `--batch-size N` | 10 | API calls per batch (pauses between batches) |

Requires an OpenAI API key (`OPENAI_API_KEY` in `backend/.env`) for the `text-embedding-3-small` model.

---

## Quick Reference

| Command | App | Category | Purpose |
|---------|-----|----------|---------|
| `create_system_user` | chats | Setup | Create discover@chatpop.app system user |
| `create_test_data` | chats | Setup | Bootstrap admin, test users, sample chats |
| `populate_chat` | chats | Testing | Add test messages to a chat room |
| `test_photo_upload` | media_analysis | Testing | End-to-end photo upload test |
| `batch_photo_upload` | media_analysis | Testing | Upload multiple test photos from JSON |
| `generate_location_data` | media_analysis | Testing | Stress test lightning strike map |
| `inspect_redis` | chats | Maintenance | Debug/monitor Redis message cache (hash + indexes) |
| `reset_all_chat_data` | chats | Maintenance | Delete all messages, gifts, transactions + flush Redis |
| `sync_reaction_cache` | chats | Maintenance | Sync reactions from PostgreSQL to Redis |
| `cleanup_expired_photos` | media_analysis | Maintenance | Delete expired photo records and files |
| `backfill_avatars` | chats | Maintenance | Generate missing avatar URLs |
| `browse_suggestions` | media_analysis | Diagnostics | Browse suggestion database |
| `inspect_suggestion_distances` | media_analysis | Diagnostics | Analyze embedding clustering thresholds |
| `generate_room_embeddings` | media_analysis | Diagnostics | Generate embeddings for AI rooms |
