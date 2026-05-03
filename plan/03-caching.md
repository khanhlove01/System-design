# Phase 3 — Caching at Scale

The single most leveraged technique in scaling. A 95% cache hit rate turns 1M req/sec into 50k req/sec at the origin — a 20× scale gain for ~free.

## Core questions

### The cache hierarchy (from client to DB)
| Layer | Where | TTL | Notes |
|---|---|---|---|
| **Browser cache** | User's machine | minutes–years | Controlled by `Cache-Control`, `ETag`, `Last-Modified` |
| **CDN edge cache** | Cloudflare/Fastly/Akamai POPs | minutes–days | Static + semi-dynamic; key = URL + Vary headers |
| **Reverse proxy cache** | Nginx/Varnish in front of origin | seconds–minutes | Buffer + cache full HTTP responses |
| **Application cache** | Redis / Memcached | seconds–hours | Per-app, per-key, application-controlled |
| **Local in-process cache** | Python `functools.lru_cache`, Caffeine, etc. | seconds | Single-process; sized to memory |
| **Database query cache** | Removed from MySQL 8 / never in Postgres | n/a | Use app-tier caching instead |
| **CPU caches** | Hardware | nanoseconds | Free; just write cache-friendly code |

- [ ] **Multi-tier**: each layer absorbs traffic the next layer would have to handle. CDN absorbs 90%, app cache absorbs 9% of remainder, DB sees the last 1%.

### Redis vs Memcached (the canonical interview question)
| | Redis | Memcached |
|---|---|---|
| Data types | Rich (strings, lists, hashes, sets, sorted sets, streams, bitmaps, HLL) | Just key → opaque blob |
| Persistence | Optional (RDB snapshots, AOF log) | None — ephemeral |
| Replication | Yes (primary/replica, Sentinel for HA, Cluster for sharded) | No native (proxy layers like mcrouter) |
| Threading | Single-threaded core (multiplexed I/O) | Multi-threaded |
| Memory model | In-memory + can spill | Strictly in-memory |
| Atomic ops | Many (`INCR`, `LPUSH`, `ZADD`, transactions, Lua scripts) | `incr`/`decr` only |
| Best for | Sessions, leaderboards, queues, cache with structure | Pure cache, one core per instance, simple |

- [ ] **Default to Redis** in 2026 unless you have a specific reason. Richer feature set, ops parity is now equal.

### Cache patterns
- [ ] **Cache-aside (lazy loading)** — most common:
  ```
  GET key from cache
  if miss:
      val = read from DB
      write val to cache (with TTL)
  return val
  ```
  - Pros: cache only holds what's actually accessed.
  - Cons: first read is slow (cold start); stale data possible if updates bypass cache.
- [ ] **Read-through**: cache library does the DB read on miss; app talks only to cache.
  - Pros: cleaner app code.
  - Cons: cache and DB coupled; failure modes more complex.
- [ ] **Write-through**: writes go to cache + DB synchronously.
  - Pros: cache always consistent with DB on the keys it holds.
  - Cons: every write is two ops; you cache things that may never be read.
- [ ] **Write-behind (write-back)**: writes go to cache, async to DB.
  - Pros: very fast writes.
  - Cons: data loss if cache crashes before flush. Use with great care; usually for non-critical (counters, view counts).
- [ ] **Refresh-ahead**: predictively refresh hot keys before they expire.
  - Pros: bounded staleness, no cold path.
  - Cons: complexity; predicting hot keys.

### Invalidation strategies
- [ ] **TTL** — simplest. Cached value expires after N seconds. **Bounded staleness** == TTL. Good for content that updates infrequently.
- [ ] **Explicit invalidation on write**:
  ```
  write to DB
  delete (or update) cache key
  ```
  - Race: read between DB write and cache delete inserts stale value back. Mitigate: delete before AND after write, or use versioning.
- [ ] **Version stamping**: cache key includes a version (`user:123:v42`). Bump version on update; old cached values orphan and TTL out. Avoids the race.
- [ ] **Event-driven invalidation**: publish change event (Kafka) → all caches subscribe → invalidate. Used in big systems. Complexity is real.
- [ ] **Negative caching**: cache the fact that a key *doesn't exist* with short TTL → defeat repeated lookups for missing keys.

### Cache stampede (the classic disaster)
- [ ] A popular cached value expires → many concurrent reads all miss → all hit DB simultaneously → DB melts.
- [ ] **Mitigations** (from cheap to thorough):
  - **TTL jitter**: don't expire 10k keys at the same instant; add random ± 10% to each TTL.
  - **Single-flight / request coalescing**: only one request per key goes to the DB; others wait for the result. Use `singleflight` (Go), `cachetools.cached` with lock (Python), or in-process Future-per-key.
  - **Lock on miss**: first miss takes a Redis lock (`SETNX`); others wait, then re-check the cache. (Make sure to handle lock-holder crash with TTL on the lock.)
  - **Probabilistic early refresh** (XFetch): each read randomly decides whether to *also* refresh — probability rises as TTL approaches expiry. Spreads load.
  - **Stale-while-revalidate**: serve stale value while a single async refresh runs.
  - **Pre-compute / warm**: refresh popular keys on a schedule, never let them expire under load.

### Cache coherence with the DB
- [ ] Hard problem. Three approaches:
  1. **TTL only** — accept up to TTL of staleness. Simplest, often fine.
  2. **Invalidate on write** — best-effort. Race window during write.
  3. **CDC pipeline** (Debezium → Kafka → cache invalidator) — DB changes drive cache invalidation. Strong eventual consistency. Complex.
- [ ] **Pick based on staleness tolerance**, not based on what sounds rigorous.

### Distributed cache: consistent hashing
- [ ] Goal: map keys to N cache nodes. Adding/removing a node should remap **only ~1/N of keys**, not all of them.
- [ ] **Naive hash** `hash(key) % N`: change N → almost every key remaps → cache effectively wiped.
- [ ] **Consistent hashing**: arrange nodes on a logical ring at hash(node_id); a key is served by the next node clockwise from hash(key). Adding a node only displaces keys between it and its neighbor.
- [ ] **Virtual nodes**: each physical node gets ~150 virtual positions on the ring → smooth load distribution, less impact when one node dies.
- [ ] Used by: Redis Cluster (16384 slots, similar idea), Cassandra, DynamoDB, memcached client-side libraries (mcrouter, ketama).

### Cache sizing
- [ ] **Hot data**: typically follows Pareto — 80% of accesses hit 20% of keys; sometimes 95/5.
- [ ] **Working set**: enough RAM to hold the hot set comfortably. **If working set > RAM, hit rate collapses.**
- [ ] **Monitor**: hit rate, miss rate, eviction rate, memory used. A drop in hit rate = capacity problem or access pattern shift.

### Eviction policies
- [ ] **LRU (Least Recently Used)** — most common. ([OS 07-caching.md](../../OperatingSystem/Operating-System/07-caching.md) for O(1) impl.)
- [ ] **LFU (Least Frequently Used)** — favors items hit many times. Better under scan workloads.
- [ ] **TinyLFU + W-LFU (Caffeine)**: admission policy decides if a candidate is *worth* admitting. State of the art for app caches.
- [ ] **Approximate LRU**: Redis samples N keys and evicts oldest. Cheap, "good enough."

### When NOT to cache
- [ ] Data that's accessed once (cache miss + insert is wasted work).
- [ ] Data that changes more often than it's read.
- [ ] Tiny payloads where the cache lookup overhead is comparable to the source query.
- [ ] Heavily personalized data with low key reuse — cache size explodes.

### CDN-specific patterns
- [ ] **Cache key normalization**: don't include irrelevant query params in the key (`?utm_source=...` would create cache misses). Vary header for what *does* matter.
- [ ] **Origin shielding**: a "regional shield" cache between edge POPs and origin → reduces origin requests further.
- [ ] **Stale-if-error**: serve stale on origin errors. Massive availability win.
- [ ] **Cache-busting on deploy**: bump versioned URLs (`/static/app.v42.js`) so old caches don't serve old code.

## Hands-on (Python)

```python
# Cache-aside with Redis (sync)
import redis, json
r = redis.Redis()

def get_user(user_id):
    key = f"user:{user_id}"
    cached = r.get(key)
    if cached:
        return json.loads(cached)
    user = db.fetch_user(user_id)             # slow path
    r.set(key, json.dumps(user), ex=300)      # 5 min TTL
    return user
```

```python
# Single-flight: prevent stampede on cache miss
import threading
_inflight: dict[str, threading.Event] = {}
_results: dict[str, object] = {}
_lock = threading.Lock()

def get_with_singleflight(key, loader):
    with _lock:
        if key in _inflight:
            event = _inflight[key]
            owner = False
        else:
            event = _inflight[key] = threading.Event()
            owner = True
    if owner:
        try:
            _results[key] = loader()
        finally:
            event.set()
            with _lock:
                del _inflight[key]
    else:
        event.wait()
    return _results.pop(key, None) or loader()  # safety
```

```python
# TTL jitter to spread expiries
import random
TTL_BASE = 300
def cache_set(key, val):
    r.set(key, val, ex=TTL_BASE + random.randint(-30, 30))
```

## Self-check
> "Twitter user-profile cache: 200M users, 95% hit rate, 50k reads/sec at p99 ≤ 50ms. Walk through: cache layer choice, instance count + RAM, sharding strategy, invalidation on profile update, stampede protection for the celebrity-account problem (Elon Musk's profile read 100k times/sec)."
