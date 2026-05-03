# Phase 5 — Databases & Storage at Scale

## Core questions

### Choosing a database — the cheat sheet
| Access pattern | DB type | Specific picks |
|---|---|---|
| Relational data, ACID, ad-hoc queries | RDBMS | Postgres (default), MySQL, Aurora, Cloud SQL |
| Massive horizontal scale + SQL | NewSQL / distributed SQL | CockroachDB, Spanner, TiDB, YugabyteDB, Vitess (MySQL-compatible sharding) |
| Key-value cache / session | KV store (in-mem) | Redis, Memcached |
| Key-value (durable, scale, low latency) | KV (managed) | DynamoDB, Cassandra, ScyllaDB, FoundationDB |
| Schema-flexible documents | Document | MongoDB, Couchbase, Firestore |
| Time-series metrics | TSDB | Prometheus (short-term), InfluxDB, TimescaleDB, VictoriaMetrics, Mimir |
| Logs / events / append-only | Log-structured | ClickHouse, Druid, Pinot, Kafka (as a log) |
| Analytics / OLAP | Column store | ClickHouse, BigQuery, Snowflake, Redshift, Druid |
| Full-text / vector search | Search | Elasticsearch, OpenSearch, Vespa, Qdrant (vector) |
| Graph traversal | Graph | Neo4j, JanusGraph, Neptune, ArangoDB |
| Object/blob storage | Object store | S3, GCS, Azure Blob (massive durable, cheap) |

- [ ] **Polyglot persistence**: don't force every workload onto one DB. Use the right tool for each access pattern.
- [ ] **But**: every additional DB is operational cost (backups, monitoring, on-call). Only add a new DB if the win is real.
- [ ] **Defaults**: Postgres + Redis covers ~80% of normal apps. Add specialized DBs only when these break.

### Recap: replication, sharding, transactions
See [DB 05](../../Database/Database/plan/05-replication.md), [DB 06](../../Database/Database/plan/06-sharding.md), [DB 07](../../Database/Database/plan/07-transactions.md). Memorize:
- Async vs sync replication tradeoffs
- Shard-key choice is forever (~) — pick wisely
- Isolation levels and the anomalies each prevents
- Distributed txn = 2PC (block-prone), Saga (eventual + compensation), TCC, or NewSQL hides it

### Storage classes (from fastest to cheapest)
| Type | Latency | Cost | Examples | Use |
|---|---|---|---|---|
| **CPU cache** | ns | free | L1/L2/L3 | Implicit |
| **RAM** | ~100 ns | $$$$/GB | Redis, in-mem DBs | Hot data, ~10-100GB working sets |
| **NVMe SSD** | ~10 µs | $$$/TB | Local SSD, EC2 i4i, GP3 EBS | DB pages, hot files |
| **SATA SSD** | ~100 µs | $$/TB | Cheaper SSD tiers | Older DBs, less hot data |
| **HDD** | ~10 ms | $/TB | Spinning rust | Archival writes, sequential workloads |
| **Object storage** | ~50–200 ms (request) | ¢/GB | S3, GCS | Blobs, images, video, backup, data lake |
| **Cold archive** | minutes–hours | ¢¢/TB | Glacier, Coldline | Compliance, long-term archival |

### Block vs File vs Object — when to use which
- [ ] **Block storage** (EBS, local SSD): looks like a raw disk. Format with a filesystem; mount; one machine at a time.
  - Best for: DB data files, OS disks, latency-sensitive single-node workloads.
  - Bad for: sharing across machines (one writer at a time without exotic clustering FS).
- [ ] **File storage** (NFS, EFS, FSx): networked file system; multiple machines mount the same path.
  - Best for: legacy apps that need POSIX file semantics across hosts; shared scratch space.
  - Bad for: extreme scale (NFS doesn't shine at PB scale); high-concurrency writes (locking is slow).
- [ ] **Object storage** (S3, GCS, Azure Blob): HTTP API, key → blob, immutable objects, massive scale.
  - Best for: media (images, video), backups, logs, data lake, anything > a few MB and not requiring file semantics.
  - Limitations: high request latency vs disk; no in-place modification (whole-object replacement); no rename (copy + delete).
  - **Cost model**: storage $/GB/month + per-request charges + egress charges. Egress is the killer — read 1 PB out of S3 to a different region = real money.

### S3-class object storage patterns
- [ ] **Direct upload from client**: presigned URLs let the client upload directly to S3 without round-tripping through your API. Massive bandwidth savings.
- [ ] **CDN in front of object storage**: serve static media via CloudFront/Cloudflare — first read warm-fills the CDN, subsequent reads hit edge. S3 origin barely sees traffic.
- [ ] **Storage tiers**: S3 Standard / Infrequent Access / One Zone-IA / Glacier Instant / Glacier Flexible / Glacier Deep Archive. **Lifecycle rules** auto-tier by age.
- [ ] **Versioning + MFA delete**: ransomware/accident protection.
- [ ] **Object Lock / WORM**: regulatory immutability.
- [ ] **Event notifications**: S3 → Lambda / SQS / SNS on `ObjectCreated:*` → process new uploads.
- [ ] **Multi-part upload**: for large objects (5GB+), upload in parallel chunks; supports resume.

### Blob in DB vs blob outside the DB
- [ ] **Don't put big blobs in your relational DB.** Replication, backup, query plans all suffer.
- [ ] Pattern: store the blob in S3, store the URL/key in the DB. DB row stays small.
- [ ] Exception: small blobs (< 100 KB) where atomic transactions with metadata matter — `bytea`/`BLOB` columns are fine.

### Data lake / lakehouse
- [ ] **Data lake**: object storage as the source of truth for all data. Files in Parquet/Avro/ORC, partitioned by day/hour.
- [ ] **Query engines on top**: Presto/Trino, Athena, Spark, BigQuery external tables.
- [ ] **Lakehouse format**: Delta Lake, Apache Iceberg, Apache Hudi — adds ACID + time travel + schema evolution to lake-style storage. Iceberg is winning the format war as of 2026.
- [ ] **Use case**: analytics on PB-scale append-only data; ML training feature stores.

### Database scaling: read replicas
- [ ] **Replicas absorb read traffic**; primary handles writes.
- [ ] Watch for **replication lag** — reads on replicas may be stale.
- [ ] **Read-after-write consistency** problem: user posts, hits replica, doesn't see their post. Mitigations: route same user's reads to primary for N seconds after a write; or version the user's session and "wait until replica caught up to vN."
- [ ] **Don't put all eggs in one replica** — replica chain (primary → replica1 → replica2) reduces fan-out from primary but multiplies lag.

### Database scaling: write sharding
- [ ] When write throughput > what one primary can do, you shard. See [DB 06](../../Database/Database/plan/06-sharding.md).
- [ ] **NewSQL** (CockroachDB, Spanner, TiDB) hides this: they auto-shard.
- [ ] **Vitess** does this for MySQL.
- [ ] **DynamoDB** is auto-sharded by partition key from day one.

### Polyglot persistence — typical stack
A real production app might have:
- Postgres for transactional/relational data (orders, users, products).
- DynamoDB or Redis for sessions / shopping carts / hot KV.
- Elasticsearch for product search.
- S3 for product images and user uploads.
- Snowflake/BigQuery for analytics.
- Kafka as the spine connecting them all (CDC pipelines).

That's six data systems. Each requires backups, monitoring, on-call. The complexity is real — but each is the *right tool* for its access pattern.

### Backup & disaster recovery
- [ ] **RPO** (Recovery Point Objective): how much data are we OK losing? (5 min? 1 hour? 0?)
- [ ] **RTO** (Recovery Time Objective): how fast must we recover? (5 min? 1 day?)
- [ ] **3-2-1 rule**: 3 copies, 2 different media, 1 off-site.
- [ ] **Test restores regularly** — backups that have never been restored are not backups.
- [ ] **Cross-region replication for the DB** + cross-region backup for the WAL/binlog → low RPO without manual ops.

### Capacity sizing
- [ ] **DB size**: rows × bytes/row × indexes × replication × growth headroom.
- [ ] **IOPS**: estimate based on read+write QPS; provisioned IOPS on cloud DBs is a real cost lever.
- [ ] **Connections**: each connection = ~10 MB on Postgres. Use a connection pooler (pgbouncer) — apps can have 1000s of connections, DB sees 100s.
- [ ] **Replication lag budget**: if your business tolerates 30s, async replication is fine; if 0s, sync replication or NewSQL.

## Hands-on (Python)

```python
# Direct-upload pattern: backend issues a presigned S3 URL
import boto3
s3 = boto3.client('s3')

def get_upload_url(key, content_type):
    return s3.generate_presigned_url(
        'put_object',
        Params={'Bucket': 'my-bucket', 'Key': key, 'ContentType': content_type},
        ExpiresIn=300,
    )

# Frontend: PUT directly to that URL with the file body. Backend never touches the bytes.
```

```python
# Read replica routing for read-after-write consistency
import time

class DB:
    def __init__(self, primary, replica): self.primary, self.replica = primary, replica
    def write(self, user_id, sql, params):
        self.primary.execute(sql, params)
        request.session['recent_write_until'] = time.time() + 5   # route reads to primary for 5s
    def read(self, user_id, sql, params):
        target = self.primary if request.session.get('recent_write_until', 0) > time.time() else self.replica
        return target.execute(sql, params)
```

## Self-check
> "Design the storage architecture for a photo-sharing app: 100M users, 10 photos/user/year average, 5MB/photo. Walk through: where photos live, how thumbnails are generated, how feeds load fast, how DB schema looks, how backups work. Justify each choice in cost + latency terms."
