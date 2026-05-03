# Phase 2 — Scaling Fundamentals

## Core questions

### Vertical vs horizontal scaling
- [ ] **Vertical (scale up)**: bigger machine. Cheap-and-easy lever first. Hardware ceiling: ~256 cores, ~2 TB RAM, ~100 Gbps NIC. After that, you're stuck.
- [ ] **Horizontal (scale out)**: more machines. Linear-ish if state is partitioned. Requires the system to be **distributed** (and to handle network partitions, replication, consensus, etc.).
- [ ] **Order of operations**: vertical scale first (cheap, no architectural change), profile + optimize, *then* horizontal scale only when you've hit the ceiling.
- [ ] **Stateless services** scale horizontally trivially — just add more replicas behind a load balancer. **Stateful services** require sharding or replication.

### Stateless services
- [ ] **Stateless** = the server holds no per-request state across requests. All state lives in:
  - Request itself (the auth token, user ID)
  - Shared external state (DB, cache, queue)
- [ ] **Why stateless wins**: any replica can serve any request → trivial horizontal scale + automatic failover. Lose a server, traffic just routes to others.
- [ ] **Common mistake**: storing session in process memory. → can't scale, can't restart cleanly. Move to Redis / sticky cookies / signed tokens.
- [ ] **Twelve-factor app**: principles for cloud-native services. Worth reading once. Key ones: stateless processes, config in env, port binding, disposability, dev/prod parity.

### Sharding / partitioning (recap)
- [ ] **Splitting one logical dataset across N nodes** so each holds a subset of the data.
- [ ] Strategies: **range**, **hash**, **directory**, **geo/tenant**. See [DB 06](../../Database/Database/plan/06-sharding.md) for full treatment.
- [ ] Choose the **shard key** carefully — it's the routing dimension. You usually can't change it later without a full migration.
- [ ] **Hot shards** are the failure mode: one celebrity, one popular tenant, one busy region overwhelms its shard while others are idle. Mitigate via finer hash, dedicated sub-shards, or random suffixing for super-hot keys.

### Replication (recap)
- [ ] **Multiple copies** of the data on different nodes for read scaling, HA, disaster recovery, geo proximity.
- [ ] **Sync vs async**: sync = strong consistency at higher latency; async = lower latency, possible data loss on failover.
- [ ] **Topologies**: single primary + replicas (most common); multi-primary (rare and painful); chain replication; consensus-based (Paxos/Raft for strong consistency).
- [ ] Don't conflate replication (HA + read scale) with sharding (write scale + storage). You usually need both.

### Monolith vs Microservices
- [ ] **Monolith**: single deployable unit, single process, one repo (typically), one database. Simple to develop, deploy, debug. Scales fine for many companies (Stack Overflow famously serves billions of pageviews per month from a small monolith).
- [ ] **Microservices**: decomposed by bounded context, each with its own DB, deployed independently, communicating over the network.
- [ ] **Why microservices?**
  - Independent deployment (different teams ship without coordination)
  - Independent scaling (the search service needs 100 instances; the admin service needs 2)
  - Polyglot persistence (the right DB for each domain)
  - Fault isolation (search fails, the rest survives)
- [ ] **What you give up:**
  - Distributed transactions become **hard** (see [DB 07](../../Database/Database/plan/07-transactions.md))
  - Latency increases (every call is a network hop)
  - Operational complexity explodes (every service needs deploy, monitor, alert, on-call)
  - Cross-service debugging requires tracing
- [ ] **Common mistake**: starting a green-field project with microservices. **Monolith first.** Split when you have evidence the split solves a real problem.

### Service decomposition (when you do split)
- [ ] **By bounded context** (DDD): one service per business domain. Order, Payment, Inventory, Shipping each owns its data.
- [ ] **Database-per-service** is a hard rule. If two services share a DB, they're not really separate — schema changes couple them.
- [ ] **Sync vs async communication**:
  - **Sync (REST, gRPC)**: simpler reasoning; tight coupling; cascading failures.
  - **Async (Kafka, SQS)**: looser coupling; better failure isolation; eventual consistency; debugging harder.
  - Most real systems mix both — sync for query, async for events.

### Autoscaling
- [ ] **Horizontal**: add/remove instances based on metrics (CPU, RPS, queue depth, custom).
- [ ] **Reactive lag**: scale-up takes time (minutes for VMs; seconds for containers; sub-second for Lambda). Plan for the lag — pre-scale before the spike.
- [ ] **Cooldowns**: prevent flapping. Don't scale down within N minutes of last scale-up.
- [ ] **What scales well**:
  - Stateless web/API servers — perfect target.
  - Worker pools reading from a queue — scale on queue depth.
- [ ] **What scales poorly**:
  - Stateful services (DB) — only scale during major events with planned migrations.
  - Caches — adding nodes invalidates a fraction; consistent hashing helps.
- [ ] **Cost discipline**: cap max instances. A bug + autoscale = unbounded bill (Economic Denial of Sustainability — see [Security 04](../../Security/plan/04-ddos.md)).

### Caching as a scaling tool
- [ ] **The cheapest way to scale reads** is to not do them. Aggressive caching at every layer ([03-caching.md](03-caching.md)).
- [ ] **Without caching**: 1M reads/sec hit the DB → DB melts.
- [ ] **With 95% cache hit rate**: only 50k reads/sec hit the DB → manageable.
- [ ] Engineers consistently underestimate how much caching changes the architecture.

### Async / queue-based decoupling
- [ ] If a step doesn't have to happen synchronously, **don't make it synchronous**.
- [ ] Pattern: API accepts request → enqueues work → returns 202 + status URL → client polls. Worker pool processes the queue.
- [ ] Benefits:
  - API stays responsive even when the work is slow.
  - Workers can scale independently of the API tier.
  - Retries are easy (queue holds the message until ack).
  - Spikes get absorbed by the queue (within size limits).

### Backpressure
- [ ] When upstream produces faster than downstream consumes, *something* must give: back-pressure (slow producer), buffer (delay), or drop (lose).
- [ ] **Bounded queues** between stages — queue full → producer waits or rejects. *Never* unbounded.
- [ ] At the network edge: rate limiting (see [09-api-design.md](09-api-design.md)).
- [ ] Application: `429 Too Many Requests` with `Retry-After` header.

### CDN as a horizontal-scale cheat code
- [ ] For static content (images, JS, CSS, videos), the CDN serves from edge POPs near the user. Origin barely sees traffic.
- [ ] For semi-dynamic (HTML pages with short TTL), CDN can still absorb most traffic.
- [ ] **Cloudflare/Fastly handle billions of requests at flat-ish price points** — leverage them.
- [ ] See [03-caching.md](03-caching.md) for cache hierarchy.

### Common scaling anti-patterns
- [ ] **Single big shared database** for every microservice — kills independent deployment.
- [ ] **Distributed monolith**: nominally microservices but every change requires coordinated deploy of N services.
- [ ] **Synchronous chains of >3 services** for one request — latency adds, failure rate adds.
- [ ] **No backpressure** anywhere — first slowness cascades into outage.
- [ ] **Premature sharding** — sharded too early, painful coordination forever.
- [ ] **Hot key problem ignored** — designing for evenly distributed load when reality has Pareto distribution.

## Self-check
> "Your monolith handles 10k QPS comfortably; growth projections say 100k QPS in 18 months. Walk me through the order of changes you'd make and why. Where does sharding come in? Where does microservices? What stays a monolith? What's your safety net for 'we got this wrong' at each step?"
