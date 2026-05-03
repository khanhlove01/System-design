# Phase 8 — Distributed Systems Fundamentals

The theoretical underpinnings every distributed-system interview demands. Heavy overlap with [DB 01-sql-vs-nosql-cap.md](../../Database/Database/plan/01-sql-vs-nosql-cap.md), [DB 07-transactions.md](../../Database/Database/plan/07-transactions.md), [Concurrency 09-distributed-concurrency.md](../../Concurrency/plan/09-distributed-concurrency.md). This file consolidates and extends.

## Core questions

### CAP — recap
- [ ] **C**onsistency — every read sees the latest write (linearizability strictly).
- [ ] **A**vailability — every request gets a non-error response.
- [ ] **P**artition tolerance — system continues despite messages being dropped/delayed.
- [ ] **Pick two of three.** In real distributed systems, partitions *will* happen — so you really pick **CP (sacrifice availability under partition)** or **AP (sacrifice consistency)**.
- [ ] CAP is binary and pessimistic. Most production systems are **CP under partition, EC under normal operation** — see PACELC.

### PACELC — the honest extension
- [ ] **If P**artition: A vs C. **Else (E)**: L (latency) vs C (consistency).
- [ ] Real systems:
  - **Spanner = PC/EC**: consistent always; pays latency to achieve it.
  - **DynamoDB = PA/EL**: available + low latency; consistency tunable.
  - **Cassandra (default) = PA/EL**: same.
  - **Postgres single-node** doesn't really fit (no partition). With sync replication: PC/EC.

### Consistency models (from strongest to weakest)
| Model | Guarantee |
|---|---|
| **Linearizability** | Operations appear instantaneous in a single global order consistent with real time. The "as if it were a single server" model. |
| **Sequential consistency** | Some interleaving of operations exists, consistent with each thread's program order — but not necessarily real-time. |
| **Causal consistency** | If A causes B (e.g., reply to a comment), every observer sees A before B. Concurrent ops can be reordered. |
| **Read-your-writes** | A user always sees their own writes. Other users may see stale state. |
| **Monotonic reads** | A user never sees data go backward in time. |
| **Eventual consistency** | If no new writes, replicas converge eventually. No bound on when. |

- [ ] **Implementation**: linearizability requires consensus / quorum reads. Eventual is the cheapest. Most systems sit on **causal + read-your-writes** for the user-facing path.

### Consensus — Paxos, Raft, ZAB
- [ ] **Goal**: a set of nodes agree on a value (or sequence of values) despite crashes and message loss.
- [ ] **Survives** ⌊(N-1)/2⌋ node failures (majority quorum).
- [ ] **Doesn't survive Byzantine** (lying / malicious) failures — for that, BFT consensus (PBFT, HotStuff, Tendermint).
- [ ] **Costs ≥ 1 RTT** for a write; latency = slowest member of the majority.
- [ ] **Where it lives**: etcd (Raft), Consul (Raft), ZooKeeper (ZAB ≈ Paxos), CockroachDB (Raft), TiKV (Raft), Spanner (Paxos with TrueTime).
- [ ] **For interviews**: name the protocol, describe leader-based replication (write goes to leader → replicates to followers → committed when majority acks), and acknowledge "doesn't tolerate Byzantine."

### Vector clocks
- [ ] Each node maintains a vector of "what I've seen from each peer." `[A:5, B:2, C:7]` = "I've seen A's first 5, B's first 2, C's first 7 events."
- [ ] **Compare**: `V1 ≤ V2` iff every component of V1 ≤ corresponding component of V2. Otherwise concurrent.
- [ ] **Use**: detect concurrent updates so you can ask the application to merge (Riak, Dynamo).
- [ ] **Lamport clocks** are simpler — single counter, gives a partial order but can't detect concurrency directly.
- [ ] **Hybrid Logical Clocks (HLC)**: combine physical timestamp + logical counter. Used in CockroachDB, MongoDB. Approximates real time while preserving causality.

### Gossip protocols
- [ ] Each node periodically picks a random peer and exchanges state. Information spreads exponentially: O(log N) rounds to reach everyone.
- [ ] **Used for**: cluster membership (Cassandra, Consul), failure detection (Phi accrual), eventually-consistent state propagation.
- [ ] **Tradeoffs**: simple, robust to partitions, scales to thousands of nodes. Eventual; bandwidth grows with cluster size; convergence is probabilistic.

### Distributed locks (recap from Concurrency 09)
- [ ] **Naive Redis SETNX is dangerous** without fencing — GC pause / network partition can cause two clients to think they hold the lock.
- [ ] **Robust pattern**: lock service issues a monotonic **fencing token**; resource accepts only writes with token > last seen.
- [ ] **Implementations**: ZooKeeper ephemeral nodes + sequential IDs, etcd lease + version, RDBMS row lock + version column.
- [ ] **Question to ask**: do I really need a distributed lock, or can I make the operation idempotent and rely on at-least-once delivery?

### Leader election
- [ ] One node is "the leader"; failover if it dies. Built on consensus or simpler quorum schemes (etcd lease, ZK ephemeral seq).
- [ ] **Why**: singleton coordinator (one cron runner across the cluster), single-writer for a partition, sequencer for a global ID.
- [ ] **Lease-based**: leader holds a lease with TTL, renews periodically; if renewal fails (network partition, GC pause), lease expires and election re-runs.
- [ ] **Split-brain**: two nodes both think they're leader during partition. Quorum-based election prevents this — only the partition with a majority can elect.

### Idempotency
- [ ] **Idempotent operation**: applying it once = applying it many times. Examples: PUT, DELETE, set-counter-to-X.
- [ ] **Idempotent processing**: server dedups duplicate requests via a key. Different concept.
- [ ] **Idempotency keys** in APIs: client generates a UUID per intended action; server stores `(key → result)` for a retention window. Duplicates return cached result.
- [ ] **Why**: any network call can be retried. Without idempotency, retries cause double-charges / double-emails / double-anything.

### Sagas (distributed transactions)
- [ ] **Pattern**: split a distributed business transaction into a chain of local transactions, each with a **compensating action** to undo it.
- [ ] **Two flavors**:
  - **Choreography**: each service emits events; downstream services react. Decentralized.
  - **Orchestration**: a saga orchestrator service drives the chain explicitly. Easier to reason about; central failure point.
- [ ] **Key insight**: no global ACID; eventual consistency; compensations may not perfectly undo (you can email "your order is canceled" but you can't un-send the email).
- [ ] **When to use**: cross-service business txns where 2PC is too painful (most microservice scenarios).

### Two-Phase Commit (2PC)
- [ ] Coordinator asks each participant to **prepare** (durably persist the change but don't commit). If all say YES, coordinator says **commit**; otherwise **abort**.
- [ ] **Problem**: blocking on coordinator failure between phase 1 and phase 2 — participants stuck holding locks.
- [ ] **Used inside NewSQL** (Spanner, CockroachDB) with optimizations to handle coordinator failure gracefully. Don't roll your own 2PC across microservices.

### "Exactly once" myth
- [ ] **Exactly-once delivery** over an unreliable network is impossible (Two Generals' problem).
- [ ] **Achievable**: at-least-once delivery + idempotent processing = effectively-once outcome.
- [ ] When you read "exactly-once" in marketing, it usually means "we make the dedup easier" or "exactly-once within our internal pipeline" (Kafka transactions: only within Kafka).

### Time, clocks, and ordering
- [ ] **Wall-clock time can lie.** NTP drift, clock skew across nodes, leap seconds. Don't compare timestamps from different machines for ordering.
- [ ] **Logical clocks** (Lamport, vector) provide order without trusting wall-clock.
- [ ] **HLC** combines best of both — close-to-physical-time + causality.
- [ ] **TrueTime (Spanner)**: GPS + atomic clocks → bounded uncertainty (~7ms). Spanner's "external consistency" — the closest thing to global linearizability — is built on TrueTime.

### CRDTs (Conflict-Free Replicated Data Types)
- [ ] Data structures whose merge function is **commutative + associative + idempotent** → replicas converge regardless of order.
- [ ] **State-based (CvRDT)**: each replica holds full state; on merge, take the join (LWW set, G-Counter, OR-Set).
- [ ] **Operation-based (CmRDT)**: replicas exchange ops; ops must be commutative.
- [ ] **Used in**: Riak (selectable), Redis Enterprise CRDB, Yjs / Automerge (collaborative editing), some games.
- [ ] **Limitation**: data shapes are constrained — counters, sets, registers, ordered lists. Not relational.

### FLP impossibility (the deep theory)
- [ ] **Theorem**: no deterministic distributed consensus algorithm can guarantee progress in an asynchronous network with even a single faulty node.
- [ ] **In practice**: real systems use timeouts, randomization, or partial synchrony assumptions. Raft's election timeout is one example — it gives up perfect determinism for practical liveness.
- [ ] **For interviews**: you don't need to prove it; just acknowledge "FLP says deterministic asynchronous consensus is impossible without timing assumptions" and move on.

### Common patterns in distributed-system designs
- [ ] **Single-writer per partition** to avoid coordination on writes.
- [ ] **Read-your-writes via session pinning** (route a user's reads to where their writes went).
- [ ] **Hinted handoff** (Dynamo): if a replica is down, write to another node with a "hint" to forward when it returns.
- [ ] **Anti-entropy** (Merkle trees): nodes periodically compare hash trees of their state; only sync the differing branches.
- [ ] **Read repair**: on read, if replicas disagree, push the latest to the stale ones.

## Self-check
> "Walk me through what 'consistent' means in CAP, in ACID, in 'consistent hashing,' and in 'eventually consistent.' These are four different uses of the word — what's the precise definition of each?"
