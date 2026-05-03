# Phase 6 — Message Queues & Event-Driven Architecture

## Core questions

### Why a queue between services?
- [ ] **Decoupling**: producer doesn't have to know consumer; consumer can be down and producer keeps working.
- [ ] **Asynchrony**: producer returns immediately; consumer processes when ready.
- [ ] **Buffering / smoothing**: spike of 10× traffic for 30 seconds → queue absorbs; consumer drains at steady rate.
- [ ] **Fan-out**: one event → many independent consumers (analytics, search index, notification, audit).
- [ ] **Reliability**: queue holds the message until ack → consumer crash mid-processing = redelivery, not loss.
- [ ] **Cost**: more moving parts; harder to reason about end-to-end latency; eventual consistency.

### The big choices: Kafka vs RabbitMQ vs SQS vs NATS
| | Kafka | RabbitMQ | AWS SQS | NATS / JetStream |
|---|---|---|---|---|
| Model | **Distributed log** — partitioned, ordered, replayable | Broker queue with routing logic (exchanges → queues) | Managed queue (no broker to run) | Lightweight pub/sub + (JetStream) durable log |
| Ordering | Per-partition strict | Per-queue FIFO (or FIFO queues) | Standard: best-effort; **FIFO** queues: strict | Per-subject |
| Throughput | Millions/sec/cluster | 10s of thousands/sec | Tens of thousands/sec (standard); 300/sec (FIFO) | Millions/sec |
| Latency | ms | ms | tens of ms | sub-ms |
| Retention | Days–years (replayable) | Until consumed | 14 days max | Configurable (JetStream) |
| Replay | Yes — consumers track offsets | No | No | Yes (JetStream) |
| Delivery | At-least-once (default) | At-least-once | At-least-once (Standard); **exactly-once-ish** (FIFO with dedup window) | At-least-once / at-most-once |
| Best for | Event streaming, log pipelines, high-throughput | Task queues, complex routing, RPC | Simple AWS-native pub/sub | Service-to-service messaging, IoT |

- [ ] **Common picks**:
  - **Event streaming, analytics pipeline**: Kafka.
  - **Background job queue (send email, render PDF)**: SQS / RabbitMQ / Redis-backed (Celery, BullMQ).
  - **Microservice events (user_signed_up, order_placed)**: Kafka or SNS/SQS fan-out.

### Topics, partitions, consumer groups (Kafka mental model)
- [ ] **Topic**: named stream. (`orders`, `user-signups`, `clicks`.)
- [ ] **Partition**: a topic is split into N partitions. Each partition is an ordered, append-only log. **Order is per-partition, not per-topic.**
- [ ] **Producer** writes to a partition (chosen by hash of key, or round-robin if no key).
- [ ] **Consumer group**: a logical subscriber. Each partition is consumed by exactly one consumer in the group. → parallelism = number of partitions, capped.
- [ ] **Multiple consumer groups**: same data, independent positions — fan-out for free.
- [ ] **Offsets**: each consumer records its position. Replay = reset offset to earlier point.
- [ ] **Replication factor**: each partition replicated to N brokers (typically 3) for durability.

### Delivery semantics — and the "exactly once" myth
- [ ] **At-most-once**: send, don't track ack. Possible loss; no duplicates. Logging metrics where rare loss is fine.
- [ ] **At-least-once**: send, retry until ack. Possible duplicates; no loss. **Most common.**
- [ ] **Exactly-once**: each message processed *exactly once*. **Generally impossible** end-to-end without extra machinery.
- [ ] **What people mean by "exactly once"**:
  - **Idempotent consumer**: consumer dedups via idempotency key. At-least-once delivery + idempotent processing = effectively-once outcome. **The right answer 99% of the time.**
  - **Transactional outbox**: producer atomically writes the message to a DB outbox table in the same transaction as the business write; a separate process reliably forwards from outbox to broker.
  - **Kafka transactions** (idempotent producer + read-process-write within one transaction) — gives effectively-once for Kafka-internal pipelines, *not* for external side effects.
- [ ] **Don't promise exactly-once**. Promise idempotent processing.

### Idempotency in practice
- [ ] **Idempotency key**: client-generated unique ID per intended action. Server stores `(key → result)` table; on duplicate, return cached result without re-executing.
- [ ] **Storage**: Redis with TTL (cheap, eventual cleanup) or DB table with retention policy.
- [ ] **Naturally idempotent operations**: PUT (set value), upsert, delete. Just pass through.
- [ ] **Naturally non-idempotent**: append, "send email," "charge card". Need explicit dedup.
- [ ] **For Kafka consumers**: store last processed offset + your application state in the same transaction; on crash recovery, replay from stored offset. (Single-DB systems can do this; cross-system requires the outbox pattern.)

### Ordering and partitioning
- [ ] **Order is preserved per partition.** Across partitions, ordering is concurrent → no global order.
- [ ] **Partition by entity** that requires ordering: `user_id`, `account_id`, `order_id`. All events for one user → one partition → ordered.
- [ ] **Hot partitions**: skewed partition keys → one partition saturates while others idle. Same problem as DB sharding.
- [ ] **Re-keying**: if you discover the wrong partition key after the fact, you need a migration (Kafka MirrorMaker / re-partitioning job).

### Pub/Sub patterns
- [ ] **Point-to-point**: one queue, one consumer group. Each message goes to one consumer.
- [ ] **Pub/sub fan-out**: one event → many independent processors. Done with multiple consumer groups (Kafka), topic + multiple subscribers (SNS), exchange + multiple queues (RabbitMQ).
- [ ] **Request/reply over a queue**: producer sends with a `reply_to` queue; consumer responds there. Used in RPC-over-queue systems (older RabbitMQ patterns); usually a smell — use HTTP/gRPC for sync calls.

### Dead-letter queue (DLQ)
- [ ] After N failed processing attempts, route the message to a DLQ instead of looping forever.
- [ ] **Why**: poison-pill messages (malformed, version mismatch) shouldn't block the queue.
- [ ] **Process**: monitor the DLQ; alerts; on-call investigates / fixes / replays.
- [ ] **Don't auto-replay DLQ blindly** — that just re-creates the original problem.

### Outbox pattern (the anti-dual-write trick)
- [ ] **Problem**: I want to (a) update DB and (b) publish event. If I do them as two separate ops, either can fail without the other (dual-write problem) → state inconsistency.
- [ ] **Solution**: in the same DB transaction, write the business change + write a row to an `outbox` table. Both succeed or both fail (one transaction).
- [ ] A separate process reads the outbox (via CDC like Debezium, or polling) and publishes to the broker, then marks the row as published.
- [ ] **Result**: at-least-once delivery to broker, atomic with the DB change. Foundation of reliable event-driven microservices.

### Backpressure in queue systems
- [ ] **Queue depth metric**: producers write faster than consumers drain → queue grows.
- [ ] **Mitigations**:
  - Scale consumers horizontally (Kafka: add more consumers up to partition count).
  - Slow producers (rate limiting, app-level circuit breaker).
  - Drop messages after a max age.
  - Reject at API edge (`429`).
- [ ] **Always alert** on queue depth growth and oldest message age. These are leading indicators.

### Stream processing (consumers that do non-trivial work)
- [ ] **Beyond simple consumers**: Kafka Streams, Flink, Spark Streaming, ksqlDB.
- [ ] **What they add**: stateful processing (windowing, aggregation, joins between streams), exactly-once-ish semantics within the framework, replayable computation.
- [ ] **Use cases**: real-time analytics, fraud detection, materialized views, leaderboards.

### Event sourcing & CQRS (advanced)
- [ ] **Event sourcing**: instead of mutating state, append events. Current state is computed by replaying events.
- [ ] **CQRS** (Command Query Responsibility Segregation): separate write model (commands → events → state) from read models (queries → projections optimized for each query).
- [ ] **Wins**: full audit log, replayability, can derive new read models without migration.
- [ ] **Costs**: higher complexity, eventual consistency between commands and projections, schema evolution is real work.
- [ ] **When**: domains with complex business rules and audit requirements (banking, healthcare, regulated). For most CRUD apps it's overkill.

## Hands-on (Python)

```python
# Kafka consumer with idempotent processing (effectively-once)
from kafka import KafkaConsumer
import redis
r = redis.Redis()

consumer = KafkaConsumer('orders', group_id='order-processor', enable_auto_commit=False)

for msg in consumer:
    event = json.loads(msg.value)
    key = f"processed:{event['idempotency_key']}"
    if r.set(key, '1', nx=True, ex=86400 * 7):    # SET if Not eXists, 7-day TTL
        process_order(event)
    consumer.commit()                              # only commit after success
```

```python
# Outbox pattern — write business + outbox in one transaction
def place_order(user_id, items):
    with db.transaction():
        order_id = db.execute("INSERT INTO orders ... RETURNING id", ...)
        db.execute(
            "INSERT INTO outbox (event_type, payload, created_at) VALUES (?, ?, NOW())",
            "order_placed", json.dumps({"order_id": order_id, "user_id": user_id, "items": items})
        )
    # No broker call here. A relay process polls the outbox and publishes.
```

```python
# DLQ-aware consumer
MAX_ATTEMPTS = 5
for msg in consumer:
    headers = dict(msg.headers or [])
    attempts = int(headers.get('x-attempts', 0))
    try:
        process(msg)
        consumer.commit()
    except Exception as e:
        if attempts >= MAX_ATTEMPTS:
            dlq_producer.send('orders.dlq', msg.value,
                              headers=[('x-original-error', str(e).encode())])
            consumer.commit()                       # remove from main topic
        else:
            retry_producer.send('orders.retry',
                                msg.value,
                                headers=[('x-attempts', str(attempts+1).encode())])
            consumer.commit()
```

## Self-check
> "Design the order-processing pipeline for an e-commerce site: customer clicks 'place order' → order is recorded → inventory is decremented → payment is charged → email is sent → shipping notified. What's sync vs async, what's the idempotency story for each step, what happens if the email service is down for 2 hours?"
