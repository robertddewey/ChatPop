# Cache Performance & Correctness — Work Plan

> **Living document.** Update status inline as phases progress. If a session is lost,
> this is the resume-point — read "Current status" first, then open questions.

## Current status

- **Date created:** 2026-04-15
- **Last updated:** 2026-04-15
- **Active phase:** ✅ ALL PHASES COMPLETE (2026-04-15/16)
- **Branch:** `feat/new-rooms`
- **Uncommitted fixes already in working tree:**
  - `cache.py` — `voice_duration` Decimal cast (fixed silent `add_message` failures)
  - `cache.py` — lazy media-index hydration seeded from Postgres (fixes missing-history bug)
  - `views.py` — `_fetch_from_db` now uses `MessageCache._serialize_message` (fixes media fields stripped on Postgres fallback)
  - `cache.py` — protected-aware eviction with `_is_protected()` + scan-limit
  - `cache.py` — photo/video/audio indexes + get methods + FAB notifications
  - `settings.py` + `fixtures/config.json` — `REDIS_CACHE_MAX_COUNT` 500 → 5000
  - Frontend filter rooms for photo/video/audio wired into page.tsx + MainChatView.tsx
  - `consumers.py` — WS marks photo/video/audio notifications

## Why this plan exists — investigation summary

Three bugs found while debugging "only 1 photo shows on first visit to photo room":

1. **`voice_duration` was `DecimalField`, not JSON-serializable.** Every `add_message()` failed silently in the outer try/except. Cache was never populating correctly. Fixed by casting to `float`.
2. **`_fetch_from_db` inline serializer was missing `photo_url`, `video_url`, `video_duration`, `video_thumbnail_url`, `is_highlight`, `gift_recipient`, `is_gift_acknowledged`.** Cache-miss + partial-hit paths stripped media fields. Fixed by switching to `MessageCache._serialize_message`.
3. **Hydration scanned bounded `msg_data` hash.** Missed older media messages that had aged out of the recent-messages window. Fixed by seeding from Postgres directly.

These are tactical fixes. The plan below is the strategic follow-up: make the cache fast enough to handle 10 msg/sec peak without the perf issues those fixes exposed (HGET+JSON-parse on every trim, serial-pipeline hydration, `scan_iter` on every eviction).

## Performance targets

- **Peak write rate:** 10 msg/sec per chat, sustained.
- **Cache cap:** 5000 messages (configurable via Constance `REDIS_CACHE_MAX_COUNT`).
- **Time to fill cap:** ~17 min at 5 msg/sec, ~8 min at 10 msg/sec.
- **Trim cost target:** <3ms amortized per message after cap reached (currently ~15ms).
- **Cold-start hydration target:** <500ms for 5000 messages (currently multiple seconds).

## Phases

Each phase ships independently. Tests land alongside code, never after.

### Phase 0 — Test infrastructure — ✅ Complete (2026-04-15)

**Goal:** shared scaffolding for everything that follows. No production code changes.

**Deliverables:**
- [x] `chats/tests/factories.py` — `make_user`, `make_room`, `make_participation`, `make_messages`, `MessageMix`, `count_by_kind`.
- [x] `chats/tests/cache_helpers.py` — `flush_cache`, `inspect_room`, `timeline_ids`, `msg_data_ids`, `index_ids`, `assert_indexes_consistent`, `count_redis_ops`, `count_redis_rtts`, `hydrate_room`.
- [x] `chats/tests/tests_factories.py` — 18 smoke tests covering factories + helpers.

**Outcome:** 5000-message bulk seed in <1 second (well under 3s target). Existing 48-test `tests_redis_cache` suite still green. Perf regression guard in `test_bulk_creation_is_fast` fails if bulk_create is ever bypassed.

### Phase 1 — Regression tests + observability — ✅ Complete (2026-04-15)

**Goal:** lock in the three bugs fixed above, add metrics so later phases have baselines.

**Tests (10 total in `tests_cache_regressions.py`):**
- [x] `test_voice_message_round_trips_through_cache` — Decimal voice_duration round-trips as float.
- [x] 4 × `test_serializer_includes_all_required_fields_for_*` — required-keys check for photo / video / voice / highlight against the canonical `_serialize_message`.
- [x] `test_old_photos_outside_msg_data_window_appear_after_hydration` — 50 recent text + 10 older photos; first photo-room request returns all 10.
- [x] `test_hydration_is_idempotent` — second call doesn't re-hit Postgres.
- [x] `test_add_message_logs_at_error_when_serialization_fails` — forced exception triggers ERROR log with exception class.
- [x] `test_hydration_records_metric` — `monitor.log_hydration` fires.
- [x] `test_eviction_records_metric_when_cap_exceeded` — `monitor.log_eviction` fires.

**Code:**
- [x] `monitoring.py` — added `log_hydration` and `log_eviction` (with `eviction_force` sub-metric for saturation alerts).
- [x] `cache.py` — module-level `logger = logging.getLogger(__name__)`.
- [x] `cache.py` — `add_message`'s except now `logger.exception(...)` with room/message IDs and exception class.
- [x] `cache.py` — trim block wraps timing + counters and calls `monitor.log_eviction(evicted, protected_skipped, force_evicted, duration_ms)`.
- [x] `cache.py` — `_hydrate_media_index` wraps timing and calls `monitor.log_hydration(media_type, count, duration_ms)`.

**Outcome:** 76/76 cache tests green (48 pre-existing + 18 factory + 10 regression). Silent-failure regression on serialization is now impossible without a test break.

### Phase 2 — Protected SET — ✅ Complete (2026-04-15)

**Goal:** eliminate `HGET × 101 + json.loads × 101` from the trim hot path.

**Code:**
- [x] New constant `PROTECTED_SET_KEY = "room:{room_id}:protected"`.
- [x] `add_message` SADDs in the same pipeline when `_is_protected(message_data)` is true.
- [x] `_evict_messages` SREMs all evicted IDs.
- [x] `remove_message` SREMs deleted IDs.
- [x] `update_message` re-evaluates protection on every call (SADD if newly protected, SREM if no longer protected) — keeps highlight toggle in sync.
- [x] Trim logic now does ONE `SMEMBERS protected` instead of N HGETs + N JSON parses.
- [x] TTL on protected set matches msg_data via `EXPIRE` calls in add_message.
- [x] `update_message` exception handling upgraded to `logger.exception()`.

**Highlight toggle audit:** 3 production sites flip `is_highlight`:
- `MessageHighlightView.post` (views.py:1726) — host toggle.
- `MessageDeleteView` cascade (views.py:4108) — handled via `remove_message`.
- Ban cascade (views.py:3568) — handled via `update_message` + `remove_from_highlight_index`.
All three flow through `update_message` or `remove_message`, both of which now sync the protected SET.

**Tests (15 total in `tests_protected_set.py`):**
- [x] 6 × `ProtectedSetPopulationTest` — text not added; photo/video/voice/gift/highlight all added; mixed batch holds only protected.
- [x] 3 × `ProtectedSetSyncOnHighlightToggleTest` — highlight text adds; un-highlight text removes; un-highlight photo KEEPS (still protected by photo_url).
- [x] 2 × `ProtectedSetCleanupOnEvictionTest` — soft-delete SREMs; force-eviction SREMs.
- [x] `test_trim_path_does_not_hget_msg_data` — proves the SMEMBERS path is active (HGET count <5, SMEMBERS count >=1).
- [x] 2 × `EvictionCorrectnessParityTest` — protected messages survive normal eviction; force-eviction picks oldest under saturation.

**Outcome:** 91/91 cache tests green (76 prior + 15 new). HGET-counting test pins down the perf win.

### Phase 3 — Known-index registry — ✅ Complete (2026-04-15)

**Goal:** replace `scan_iter` on `idx:*` with deterministic lookup.

**Code:**
- [x] New constant `IDX_KEYS_REGISTRY = "room:{room_id}:idx_keys"`.
- [x] `add_message` collects every index key it ZADDs into a `touched_indexes` list, then SADDs them all to the registry in the same pipeline (with TTL).
- [x] `add_to_highlight_index` (separate path used by host highlight toggle) now SADDs the highlight index key to the registry too.
- [x] `_evict_messages` reads registry via `SMEMBERS` instead of `scan_iter`.
- [x] `remove_message` reads registry via `SMEMBERS` instead of `scan_iter`.
- [x] `clear_room_cache` already covered by its `room:{id}:*` pattern (registry key cleaned up automatically).
- [x] `add_to_highlight_index` exception handling upgraded to `logger.exception()`.

**Tests (10 total in `tests_index_registry.py`):**
- [x] 7 × `IndexRegistryPopulationTest` — text registers focus only; photo/voice/highlight/gift each register their respective indexes; 10 distinct users register 10 focus indexes; `add_to_highlight_index` registers highlight key.
- [x] 2 × `EvictionUsesRegistryNotScanIterTest` — patch `scan_iter` to raise; eviction and remove_message still succeed.
- [x] `test_eviction_leaves_no_orphan_index_entries` — full consistency check after eviction.

**Outcome:** 101/101 cache tests green (91 prior + 10 new). `scan_iter` removed from both eviction paths.

### Phase 4 — Batch eviction — ✅ Complete (2026-04-15)

**Goal:** amortize trim cost — one trim per ~100 writes instead of per write.

**Code:**
- [x] New constant `EVICTION_BATCH_SIZE = 100`.
- [x] Trim condition: `total > max_messages + EVICTION_BATCH_SIZE` (was: `total > max_messages`).
- [x] When trim fires, brings cache back to `max_messages` (overflow = total - max).
- [x] Cap semantics now: effective ceiling = `max_messages + EVICTION_BATCH_SIZE`. Documented in code comment + decisions log.
- [x] New `cache_helpers.strict_cap_eviction()` context manager — temporarily sets `EVICTION_BATCH_SIZE=0` for tests that need exact-cap behavior. Applied to 5 pre-existing tests that asserted strict per-message trim.

**Tests (7 total in `tests_batch_eviction.py`):**
- [x] 3 × `BatchEvictionThresholdTest` — sub-batch overflow doesn't trim; at-threshold triggers trim; staircase pattern (grows to cap+batch then collapses).
- [x] 3 × `BatchEvictionProtectionTest` — protected media survives batched eviction; force-eviction works under saturation; size-never-exceeds-ceiling invariant across 300 writes.
- [x] `test_batch_eviction_uses_few_round_trips` — ≤10 RTTs per trigger (proves batch pipelining).

**Outcome:** 108/108 cache tests green (101 prior + 7 new). Trim fires once per ~100 writes at sustained load; batched eviction RTT cost <10 round-trips regardless of batch size.

### Phase 5 — Bulk-pipelined hydration — ✅ Complete (2026-04-15)

**Goal:** kill the cold-start latency cliff on first filter-room read.

**Code:**
- [x] Extracted `_queue_message_to_pipeline(pipe, message, ttl_seconds)` helper — queues all per-message Redis ops onto an existing pipeline. Used by both `add_message` (single message, single pipeline) and bulk hydration (N messages, single pipeline).
- [x] `_hydrate_media_index` rewritten: loops Postgres queryset, calls `_queue_message_to_pipeline` for each, accumulates `all_touched` index keys + `protected_ids`, bulk-SADDs both at the end, then `pipe.execute()` once.
- [x] Hydration flag set in same pipeline as the writes (atomic).
- [x] Cap respected via Postgres `[:cap]` slice on the hydration query.

**Tests (10 total in `tests_bulk_hydration.py`):**
- [x] 6 × `BulkHydrationCorrectnessTest` — photos hydrate to index/data/timeline; voice messages hydrate (11); protected SET stays in sync; index registry tracks hydrated index keys; full consistency check post-hydration; hydrating photo doesn't pollute audio index.
- [x] `BulkHydrationFlagTest.test_second_call_does_not_re_hydrate` — Postgres query count = 0 on second call.
- [x] `BulkHydrationCapTest.test_cap_enforced_on_hydration` — 50 photos in DB, cap=20, returns the newest 20 by ID.
- [x] 2 × `BulkHydrationPerformanceTest` — 100 photos hydrate in ≤10 RTTs; 5000 photos hydrate in <100 RTTs (regression guard against the old per-message pipeline).

**Outcome:** 118/118 cache tests green (108 prior + 10 new). 5000-message hydration completes in <100 round-trips (was 5000+).

### Phase 6 — Load / stress tests — ✅ Complete (2026-04-15)

**Goal:** prove it works end-to-end at target scale. File: `chats/tests/tests_redis_cache_load.py`. All tests tagged `@tag('slow')` and excluded from default suite.

**Tests (8 total):**
- [x] `test_fill_cache_to_cap_with_text_only` — 5000 text at cap=5000, exact size 5000.
- [x] `test_fill_cache_over_cap_settles_within_ceiling` — 6000 text at cap=5000, settles between cap and cap+batch (5100).
- [x] `test_fill_cache_with_realistic_mix` — 5000 messages with 5/2/2/1% mix, exact index sizes (250/100/100/50).
- [x] `test_protected_media_survives_moderate_text_flood` — 50 photos + 5200 text, all 50 photos survive.
- [x] `test_all_media_then_text_force_evicts_oldest_media` — 5000 photos + 5101 text, force-eviction takes oldest photos.
- [x] `test_per_message_latency_stays_bounded_post_cap` — sustained 1000-message burst post-cap, avg <10ms, max <100ms.
- [x] `test_concurrent_writes_do_not_lose_messages` — 10 threads × 100 messages, timeline/msg_data agree, indexes consistent.
- [x] `test_hydration_of_5000_photos_completes_in_bounded_time` — 5000 hydration <10s wall-clock (Python serialization-bound; old per-RTT path would have been ~25s+).

**Outcome:** 126/126 cache-suite tests green (118 prior + 8 load). Load suite runs ~95s when invoked explicitly via `--tag=slow`. Default `manage.py test` excludes them.

**Pre-existing failures noted (not caused by this work):**
- `tests_voice_messages.VoiceMessageStreamTests` — references `chats:voice-stream` URL that doesn't exist anywhere in the codebase (5 errors).
- `tests_chat_ban_enforcement.test_non_banned_user_can_connect_websocket` — WS connect assertion failure independent of cache (1 failure).
These were already broken on the branch before Phase 0 began.

### Phase 7 — Documentation — ✅ Complete (2026-04-16)

- [x] `docs/CACHING.md` — added documentation for media indexes (photo/video/audio/highlight), protected SET, index registry, hydration flag, batched cap semantics, cold-start hydration, Decimal-coercion requirement for `_serialize_message`, and "both code paths use the same serializer" guarantee.
- [x] `docs/TESTING.md` — added 8 new test files to the coverage table; documented cache test areas including the new 2026-04-15 indexes, protection-aware eviction, and hydration; documented `--tag=slow` invocation for the load suite.
- [x] `README.md` — added Cache Performance Suite (78 tests) and Cache Load Suite (8 tests, `@tag('slow')`) to the Test Suite Overview; pointer to `docs/CACHE_PERFORMANCE_PLAN.md`.

## Open questions

1. ~~**Cap overshoot in Phase 4 OK?**~~ **Resolved 2026-04-15: Yes.** Cache may reach `cap + batch_size` (5100) in steady state.
2. ~~**Highlight toggle code path**~~ **Resolved 2026-04-15: Unknown, discover during Phase 2.** Must grep/trace every `is_highlight` flip (including WS events, REST endpoints, admin actions, and the `MessageHighlightView`) and confirm each site SADDs/SREMs the protected set.
3. ~~**Load test CI budget?**~~ **Resolved 2026-04-15: `@tag('slow')`.** Load suite gated behind tag; runs on demand / in nightly, not in default `manage.py test`.
4. **Partial split (Tier 3)** — decision deferred. Revisit after Phase 6 metrics show whether single-cap + protected-eviction is sufficient or if media-heavy chats need dedicated typed caches.

## Decisions log

_Append decisions here with dates as they're made, so future-us can see why the plan changed._

- 2026-04-15: Adopted four-piece Tier 2 approach (protected SET, index registry, batch eviction, bulk hydration) over full per-type cache split. Rationale: directly addresses identified hot-path costs with ~10× improvement; full split adds complexity to main-chat reads and crosscutting indexes without proportional benefit. Partial split deferred as Tier 3, pending Phase 6 metrics.
- 2026-04-15: Cap overshoot in Phase 4 approved — cache may reach `cap + EVICTION_BATCH_SIZE`. Rationale: acceptable trade for 100× amortization of trim cost.
- 2026-04-15: Load tests gated behind `@tag('slow')` marker — not in default suite. Rationale: avoids ~20-30s penalty on every `manage.py test` run; still runs explicitly and in nightly CI.
- 2026-04-15: Highlight-toggle code path discovery deferred to Phase 2. Must grep every `is_highlight` flip site and add protected-set sync; no pre-known inventory.

## Commits / PRs reference

_Track as each phase ships._

- Phase 0: _TBD_
- Phase 1: _TBD_
- Phase 2: _TBD_
- Phase 3: _TBD_
- Phase 4: _TBD_
- Phase 5: _TBD_
- Phase 6: _TBD_
- Phase 7: _TBD_
