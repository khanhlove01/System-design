# Phase 12 — Classic Interview Problems Playbook

A walkthrough of the most-asked design problems. Each follows the methodology from [01-methodology.md](01-methodology.md): clarify → estimate → API + data model → architecture → deep dive → tradeoffs.

These are **patterns to internalize, not scripts to memorize.** The interviewer will twist the problem; your reasoning has to flex.

---

## 1. URL Shortener (TinyURL / bit.ly)

**Clarify**: 100M URLs/day created, 10× reads/write ratio (1B reads/day), p99 ≤ 100ms, 5 years retention.
**Estimate**: 365B URLs over 5y → ~2 TB at 50 bytes/row + indexes. Write QPS ≈ 1k avg, 5k peak. Read QPS ≈ 10k avg, 50k peak.

**API**:
- `POST /shorten` with `{url, custom_alias?, ttl?}` → returns `{short_url}`
- `GET /{code}` → 301/302 redirect to original

**Data model** (Postgres or DynamoDB):
- `links(code PK, long_url, created_at, expires_at, owner_id)`
- `code` is the short identifier (6-7 chars base62 → 56-3500 trillion combinations).

**Architecture**:
- Stateless API tier behind LB.
- **Code generation**:
  - **Hash-based** (`base62(SHA-256(url)[:6])`) → collision-prone; needs check-and-retry.
  - **Counter-based** (Snowflake or central sequence → encode in base62) → unique by construction; easy.
  - **Pre-allocated buckets**: each instance reserves a range of IDs, hands out from its bucket. Avoids per-write central call.
- **Write path**: API → check uniqueness → INSERT. Cache `code → URL` after creation.
- **Read path**: lookup cache → if miss → DB → cache → 301 redirect.
- **Cache**: Redis with TTL; LRU eviction. 90%+ hit rate target.
- **Analytics**: log every redirect (async to Kafka → ClickHouse); don't slow the redirect.

**Tradeoffs**: 301 (permanent, browser caches → no analytics on subsequent clicks) vs 302 (temporary, hits server every time). Most use 302.

---

## 2. Twitter / X Feed (fanout problem)

**Clarify**: 200M DAU, 5 tweets/day average, 100 followers median (with celebrity tail of 100M+), p99 home-timeline ≤ 200ms.
**Estimate**: 11k tweets/sec. Reads (timeline views) 100× → 1M reads/sec.

**Two strategies (the famous tradeoff)**:
1. **Fanout-on-read (pull)**: when user views their home timeline, query "tweets from people I follow" → merge → sort. Cheap writes, expensive reads. Bad with 1M followers.
2. **Fanout-on-write (push)**: when user posts, push the tweet ID into every follower's precomputed timeline (Redis list per user). Expensive writes, cheap reads. Bad for celebrities (1 tweet → 100M list inserts).

**Hybrid (real Twitter)**:
- For most users: **push** to followers' timelines.
- For celebrities (>X followers): **don't push**; followers read via **pull** at view time and merge with their pushed timeline.

**Data model**:
- `tweets(id PK, user_id, text, created_at, ...)` — sharded by `user_id`.
- `follows(follower_id, followee_id)` — sharded by `follower_id`.
- `timeline:user_id` — Redis list of tweet IDs (capped at ~800 entries per user).

**Read path**: fetch precomputed timeline → for celebrities the user follows, also fetch their recent tweets → merge → sort → page → hydrate full tweet bodies from a tweet cache.

**Tradeoffs**: hybrid is complex. Pure push would scale fanout costs unboundedly. Pure pull would scale read costs unboundedly. The hybrid is the price of working at Twitter scale.

---

## 3. WhatsApp / Messaging

**Clarify**: 2B users, ~100B messages/day, end-to-end encrypted, multi-device, p99 delivery ≤ 1s.
**Estimate**: 1M messages/sec average; 5M peak.

**API**:
- WebSocket connection per user (or device).
- `send(to, ciphertext, message_id, timestamp)`.
- Server: route, persist, deliver.

**Architecture**:
- **WebSocket gateway** terminates connections; horizontally scaled. Each gateway holds ~100k connections.
- **Routing**: gateway → message bus (per-user partition) → recipient's gateway.
- **Storage**: per-user inbox in a **wide-column store** (Cassandra-like). `inbox(user_id, message_id, ciphertext, sent_at, status)`.
- **Delivery state**: sent → delivered (recipient device acked) → read.
- **Multi-device**: each device has its own session and ack.
- **End-to-end encryption** (Signal protocol): server stores ciphertext only.

**Hard parts**: presence (who's online), typing indicators (low-latency, ephemeral), group messages (fanout up to 1000 members per group), delivery receipts.

---

## 4. Uber / Ride-Sharing

**Clarify**: 100M MAU, 20M rides/day, riders need driver in <30s, drivers update location every 4s.
**Estimate**: 500k driver location updates/sec; 230 ride-requests/sec.

**Components**:
- **Driver location service**: ingest 500k updates/sec → store recent positions → spatial index.
- **Matching service**: rider requests → find nearby drivers → contact them → assign.
- **Trip service**: track ride lifecycle (requested → accepted → in-progress → completed → paid).
- **Pricing service**: surge calculation per geographic cell.

**Spatial indexing**:
- **Geohash**: encode lat/lng into a string prefix; nearby points share prefix. Easy to shard.
- **S2 cells** (Google) / **H3 cells** (Uber's own): hierarchical hexagonal grid. Better than geohash for some queries.
- **Uber chose H3** because hexagons have uniform neighbors (vs. geohash's distorted boxes).

**Driver dispatch**: rider's geohash/H3 cell → query "drivers in this cell + neighbors" → rank by ETA → contact.

**Storage**: trip state in a relational DB (transactions matter); driver locations in a TTL'd Redis (Geo commands) or specialized geo store.

---

## 5. Video Streaming (YouTube / Netflix)

**Clarify**: 100M DAU, billions of hours/day watched, multiple resolutions, global CDN.
**Estimate**: bandwidth = stars. 1B hours/day at 5 Mbps avg = ~600 Tbps avg → CDN essential.

**Components**:
- **Upload pipeline**: user uploads → S3 → encoding service produces multiple bitrates (240p / 480p / 720p / 1080p / 4K) and HLS/DASH segments → manifest file → store in S3 → distribute to CDN.
- **Playback**: client requests manifest → fetches video segments (chunked HLS .ts files) from CDN → adapts bitrate based on bandwidth.
- **Metadata service**: title, description, recommendations, view count.
- **Recommendations**: ML pipeline; out of scope for the intro design.

**Why CDN is the design**:
- 99.9% of traffic is video segments which are static after encoding → cache at edge.
- Origin sees ≪ 1% of traffic.
- Netflix runs OpenConnect (their own CDN) inside ISPs.

**Adaptive bitrate streaming (ABR)**: client measures bandwidth → switches segment quality → HLS/DASH.

---

## 6. Distributed Cache (own your Redis cluster)

**Clarify**: 1M ops/sec, 1 TB working set, p99 < 5ms, multi-region, 5-9s availability.

**Architecture**:
- **Sharding**: consistent hashing across N nodes; 16k virtual slots (Redis Cluster).
- **Replication**: each shard has 1 primary + 2 replicas (3-way).
- **Client**: smart client knows the slot map; routes directly to the owning shard.
- **Failover**: replicas elect a new primary; clients refresh slot map.
- **Cross-region**: per-region cluster + async replication between regions (eventual).

**Hot key problem**: one celebrity → its single shard saturates. Mitigations:
- Local in-process cache for hot keys (read from Redis; cache locally for 1 second).
- Detect hot keys (Redis 4.0+ `redis-cli --hotkeys`); replicate them to many shards explicitly.

**Persistence**: snapshot to disk (RDB), AOF for durability, depending on usage. Backups to S3.

---

## 7. Rate Limiter as a Service

**Clarify**: 10M users, 100k req/sec to limiter, per-user limits, distributed across 10 services.

**Algorithm choice**: token bucket — allows bursts, predictable rate.

**Storage**: Redis cluster sharded by user/key. Atomic token-bucket via Lua script (see [09-api-design.md](09-api-design.md) for code).

**Distributed concern**: every API request hits Redis once → bound the latency overhead. Common: 0.5-2ms.

**Optimization for hot keys**: client-side "soft" counter → only sync to Redis every N requests or every 100ms. Eventually consistent → slightly over-allows.

**Tier system**: free tier 10/min, paid 1000/min, enterprise 10000/min. Different bucket configs per tenant.

---

## 8. News Feed (Facebook / Instagram)

Similar to Twitter feed but with **algorithmic ranking** (not chronological).

**Twist**: feed is a **scored selection** of posts from your network — not just the most recent.

**Architecture**:
- **Candidate generation**: for each user, gather candidate posts (from followed users, groups, ads).
- **Ranking**: ML model scores each candidate based on user history, post features, recency, etc.
- **Top-K selection**: return top 50 candidates for the page.
- **Caching**: precomputed feed per user, refreshed periodically; live updates push to active sessions.

**Scale levers**: candidate pruning (don't even score posts from people you haven't engaged with), feature stores for ML, online + offline ranking models.

---

## 9. Search Engine (mini-Google)

**Clarify**: index size, query rate, freshness requirements.

**Components**:
- **Crawler**: politely fetches web pages (robots.txt aware), follows links, queues new URLs. URL frontier with rate limiting per domain.
- **Indexer**: parses pages, extracts text, builds inverted index.
- **Index storage**: sharded by document ID hash; replicated for fault tolerance.
- **Query path**: parse query → fetch postings lists from index shards (scatter) → score (BM25 + click signals + ML) → merge top K (gather) → render.
- **Ranking signals**: PageRank-like graph signals + content quality + click logs → ML model.
- **Caching**: hot queries cached at edge; popular results re-ranked from query log.

See also [07-search.md](07-search.md).

---

## 10. Payment System

**Clarify**: 10M txns/day, 99.999% durability requirement, regulated (PCI), 100% audit trail.

**Components**:
- **Payment API**: idempotency-key required; never double-charge.
- **Ledger DB**: every txn is a row; immutable; accounts have running balance computed from journal entries.
  - Use **double-entry bookkeeping**: every txn has matched debit + credit entries; sum invariant.
- **PCI scope reduction**: card data lives only in tokenization vault (e.g., Stripe). Your services only see tokens.
- **Reconciliation**: nightly job compares your ledger to processor's report → flag discrepancies.

**Consistency**: ACID is non-negotiable. Use Postgres / Spanner / NewSQL. No NoSQL for the ledger.

**Saga for cross-service**: charge → fulfill → notify. Each step has compensation (refund, cancel order, send sorry email).

**Audit log**: append-only, immutable, replicate to S3 with object lock for compliance.

---

## 11. Recommendation System

**Out of scope** for most system-design interviews (more ML than systems). But know:
- **Two-stage**: candidate generation (collaborative filtering, content similarity) → ranking (deep learning model).
- **Feature store** holds precomputed user/item features.
- **Online vs offline**: offline batch generates candidates; online ranks at request time.
- **Latency budget**: ~50ms for the whole "give me 20 recs."

---

## 12. Ad Serving

Similar shape to recommendations but with auctions.

**Components**:
- **Ad inventory** + targeting rules + bids.
- **Real-time auction** (RTB): per impression, ~100ms budget to find the highest-bidding eligible ad.
- **Pacing**: spread daily budgets across the day.
- **Click + conversion tracking**: high-volume event ingestion (Kafka → ClickHouse).
- **Fraud detection**: detect bot clicks before they bill the advertiser.

---

## How to walk through any problem in an interview

1. **Restate the problem** in your own words. Confirm scope.
2. **List functional + non-functional requirements**. Ask about scale.
3. **Back-of-envelope** capacity ([01-methodology.md](01-methodology.md)).
4. **Sketch API** — 3-5 endpoints.
5. **Sketch data model** — 2-4 entities. SQL or NoSQL? Why?
6. **Draw HLD** — 5-8 boxes. Client → LB → service → cache → DB → queue → workers.
7. **Pick the deepest / hardest component** — go deep. Sharding, caching, fanout, ranking.
8. **Tradeoffs** — what your design doesn't handle well; alternatives you considered.
9. **Bottlenecks at scale** — what'll break at 10×? What's the next iteration?
10. **Reliability + observability** — health checks, retries, monitoring, SLO.

> **The interviewer is not testing whether you know "the answer."** They're testing whether you can structure a complex problem under time pressure, justify decisions, and recognize tradeoffs. Most strong designs admit weaknesses; weak designs claim perfection.

## Self-check
> "Pick three problems above. For each, time-box yourself to 45 minutes. Whiteboard end-to-end without notes. Then read your own design back: what's missing? What's over-engineered? What did the interviewer probably want you to discuss in the deep-dive that you skipped?"
