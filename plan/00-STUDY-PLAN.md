# System Design & Distributed Systems — SWE Interview Study Plan

This is the *capstone* track. It builds on every other track you've studied:
- [Networking](../../Network/Network/00-STUDY-PLAN.md) — protocols, latency, load balancers
- [OS](../../OperatingSystem/Operating-System/00-STUDY-PLAN.md) — sockets, memory, syscalls
- [Database](../../Database/Database/plan/00-STUDY-PLAN.md) — replication, sharding, transactions
- [Security](../../Security/plan/00-STUDY-PLAN.md) — TLS, secrets, DDoS
- [Concurrency](../../Concurrency/plan/00-STUDY-PLAN.md) — async, locks, distributed primitives

In a system design interview, you draw on all of them at once. This plan organizes the design-level patterns + a playbook for famous interview problems.

## Why this order?
**Methodology first** — the interview is more about *process* than knowledge. Then the toolbox: scaling, caching, LB, DB choice, storage, queues, search. Then distributed-systems fundamentals (the theory). Then API, reliability, observability (the cross-cutting concerns). Then the famous-problem playbook to integrate everything.

---

## Phase 0 — Mental Model (½ day)
- [ ] **The four-questions framework** — every system design interview boils down to:
  1. What problem are we solving? (functional + non-functional requirements)
  2. How big is it? (back-of-envelope)
  3. What does a simple version look like? (data model + APIs + diagram)
  4. Where does it break and how do we fix it? (deep dive + tradeoffs)
- [ ] **There is no single right answer.** Interviewers want to see your reasoning, your awareness of tradeoffs, and your prioritization under constraints.

---

## Phase 1 — Methodology + Estimation (1 day)
File: [01-methodology.md](01-methodology.md)

Interview framework, requirements gathering (functional/non-functional/scale), back-of-envelope math, latency numbers everyone should know, capacity planning.

**Checkpoint:** estimate "how many servers does Twitter need to serve 200M DAU posting 5 tweets/day average" in 5 minutes.

---

## Phase 2 — Scaling Fundamentals (1 day)
File: [02-scaling.md](02-scaling.md)

Vertical vs horizontal, stateless services, sharding + replication recap, monolith vs microservices, autoscaling, the 12-factor app.

---

## Phase 3 — Caching at Scale (1 day)
File: [03-caching.md](03-caching.md)

Cache hierarchy (browser → CDN → edge → app → DB), Redis vs Memcached choice, patterns (cache-aside, read-through, write-through, write-behind), invalidation, stampede, consistent hashing.

---

## Phase 4 — Load Balancing & Service Discovery (½ day)
File: [04-load-balancing-discovery.md](04-load-balancing-discovery.md)

LB types (L4/L7) recap, algorithms, sticky sessions, health checks, service discovery (DNS, registry, mesh), API gateways, sidecars.

---

## Phase 5 — Databases & Storage at Scale (1.5 days)
File: [05-databases-storage.md](05-databases-storage.md)

Choosing a DB by access pattern, polyglot persistence, replication/sharding recap, blob/object storage (S3), block storage (EBS), file (NFS, EFS), CDN-on-object-storage.

---

## Phase 6 — Message Queues & Event-Driven (1 day)
File: [06-message-queues.md](06-message-queues.md)

Kafka vs RabbitMQ vs SQS vs NATS, ordering, partitioning, consumer groups, delivery semantics (at-most/at-least/effectively-once), pub/sub, outbox, dead-letter queues.

---

## Phase 7 — Search (½ day)
File: [07-search.md](07-search.md)

Inverted index, Elasticsearch architecture, sharding/replication, BM25 + vector search, faceted search, near-real-time indexing.

---

## Phase 8 — Distributed Systems Fundamentals (1.5 days)
File: [08-distributed-fundamentals.md](08-distributed-fundamentals.md)

CAP, PACELC, consensus (Paxos/Raft), vector clocks, gossip, distributed locks (with fencing), leases, idempotency, sagas, "exactly once" myth.

---

## Phase 9 — API Design (1 day)
File: [09-api-design.md](09-api-design.md)

REST vs GraphQL vs gRPC, versioning, idempotency keys, pagination (cursor vs offset), error models, rate limiting (token bucket, sliding window, distributed).

---

## Phase 10 — Reliability Patterns (1 day)
File: [10-reliability.md](10-reliability.md)

Circuit breaker, retry with backoff + jitter, timeout, bulkhead, hedging, backpressure, graceful degradation, chaos engineering.

---

## Phase 11 — Observability (½ day)
File: [11-observability.md](11-observability.md)

Three pillars (metrics, logs, traces) + their modern unification, RED/USE methods, OpenTelemetry, SLI/SLO/SLA, error budgets, alerting.

---

## Phase 12 — Classic Problems Playbook (2+ days)
File: [12-classic-problems.md](12-classic-problems.md)

Design walkthroughs for: URL shortener, Twitter feed (fan-out), chat (WhatsApp), Uber, video streaming (YouTube/Netflix), payment, distributed cache, rate limiter as a service, news feed, search engine, recommendation, ad-serving.

**Checkpoint:** pick three, time-box yourself to 45 minutes each, whiteboard end-to-end.

---

## How to use these files
- **Read in order** for the toolbox (phases 1–11). Each builds on the last.
- **For interview prep**, jump to phase 12 after the toolbox; cycle back to specific topics when a problem exposes a gap.
- **Don't memorize designs** — internalize tradeoffs. Two interviewers will ask "URL shortener" with different priorities; your answer should adapt.
- **Always lead with requirements.** The most common interview failure is jumping into architecture before clarifying scale.

## A word on numbers
Every design hangs on capacity estimates. If you can't do back-of-envelope math fluently, you can't size anything. Drill the latency numbers in [01-methodology.md](01-methodology.md) until they're reflexive.
