# Phase 1 — Methodology & Estimation

The thing most candidates miss: the interview tests **process**, not memorized solutions. Two strong candidates can give different valid designs — what separates them is reasoning, prioritization, and tradeoff awareness.

## The interview framework (45–60 min)

### Step 1 — Clarify requirements (5 min)
- [ ] **Functional**: what features must work? (post a tweet, follow users, view timeline). Pin down 3-5 core flows; punt the rest as "out of scope for this interview."
- [ ] **Non-functional**:
  - **Scale**: DAU/MAU, peak QPS, data volume, growth rate
  - **Latency**: p50, p99, p999 budgets
  - **Availability**: 99.9% (43 min/month down) vs 99.99% (4 min/month)
  - **Consistency**: strong, eventual, read-your-writes, monotonic?
  - **Durability**: can we lose any data? Acceptable RPO/RTO?
- [ ] **Constraints**: regions (single, multi, global)? On-prem? Specific compliance (HIPAA, PCI, GDPR)?
- [ ] **What's out of scope?** — explicitly. Auth, billing, admin tooling, mobile clients, ML — say "out of scope" and move on.

### Step 2 — Estimate capacity (5–10 min)
- [ ] Convert "200M DAU posting 5 tweets/day" into:
  - Writes/sec: 200M × 5 / 86400 ≈ **11k writes/sec** average; multiply by 3-5× for peak
  - Reads/sec: posts viewed N× more than written (typical 100:1 read:write) → **~1M reads/sec peak**
  - Storage growth: avg tweet size × tweets/day × 365 → **TB/year**
  - Bandwidth: requests/sec × avg payload × replication factor
- [ ] Pick **the right unit** for each: req/sec, MB/sec, GB total, TB/year. Convert deliberately, don't hand-wave.
- [ ] **Always estimate before designing.** "Storage = TBs" vs "PBs" vs "EBs" → completely different architectures.

### Step 3 — High-level design (10 min)
- [ ] **API surface**: 3-5 main endpoints. Methods, paths, payload shape, response. (See [09-api-design.md](09-api-design.md).)
- [ ] **Data model**: core entities, relationships, primary access patterns. SQL or NoSQL? (See [05-databases-storage.md](05-databases-storage.md).)
- [ ] **Boxes-and-arrows diagram**: client → LB → service → cache → DB; queue for async work; CDN; storage; search index. Whatever's relevant.
- [ ] **Don't over-design** here. Get something simple that meets requirements, then refine.

### Step 4 — Deep dive (15–20 min)
Pick the most interesting/risky component. Common targets:
- The hot path that the interviewer hinted at (timeline construction, payment flow, search ranking)
- Whichever piece would break first under scale
- The piece you have the strongest opinion on

For that component, go deep:
- Schema details
- Sharding key
- Caching strategy
- Failure modes
- Capacity at peak

### Step 5 — Tradeoffs & alternatives (5 min)
- [ ] "I chose X. The alternative is Y. X is better for our scale because Z, but if requirements were different we'd flip."
- [ ] Acknowledge **what your design doesn't handle well**. Showing self-awareness > pretending your design is perfect.

### Step 6 — Wrap (2 min)
- [ ] Recap: requirements → key decisions → known tradeoffs → what you'd build next.

## The capacity-planning toolkit

### Latency numbers everyone should know (Jeff Dean's table, modern values)
| Operation | Time | Mnemonic |
|---|---|---|
| L1 cache reference | ~1 ns | "1" |
| Branch mispredict | ~3 ns | |
| L2 cache reference | ~4 ns | |
| Mutex lock/unlock (uncontended) | ~17 ns | |
| Main memory reference | ~100 ns | "10²" |
| Compress 1 KB with Snappy | ~2 µs | |
| Read 1 MB sequentially from RAM | ~3 µs | |
| SSD random read | ~16 µs | |
| Read 1 MB sequentially from SSD | ~50 µs | |
| Round trip in same datacenter | ~500 µs | "0.5 ms" |
| Read 1 MB sequentially from disk (HDD) | ~5 ms | |
| Disk seek (HDD) | ~10 ms | |
| Round trip US East ↔ US West | ~70 ms | |
| Round trip Europe ↔ US | ~150 ms | |
| Round trip US ↔ Asia | ~150–200 ms | |

- [ ] **Rules of thumb derived from these**:
  - Memory access is ~100× slower than L1 cache.
  - SSD random read is ~150× slower than RAM.
  - Cross-region RPC is **a million times slower** than memory.
  - **Therefore**: keep working sets in RAM where possible; avoid cross-region trips on the hot path.

### Useful constants
| Quantity | Value |
|---|---|
| Seconds in a day | 86,400 (≈10⁵) |
| Seconds in a year | ~3.15 × 10⁷ |
| 1 KB | 10³ bytes (or 2¹⁰ = 1024) |
| 1 MB | 10⁶ |
| 1 GB | 10⁹ |
| 1 TB | 10¹² |
| 1 PB | 10¹⁵ |
| Typical SSD throughput | ~3 GB/s read, ~1 GB/s write |
| Typical NIC | 10 / 25 / 100 Gbps |
| Typical server | 64–256 cores, 256 GB – 2 TB RAM |
| Typical Redis throughput | ~100k ops/sec/instance |
| Typical Postgres write throughput | ~10k tx/sec on a beefy server |

### Math patterns to drill
- [ ] **Peak factor**: multiply average load by 3-5× for peak. Multiply by 10× for "internet event" spikes.
- [ ] **Read:write ratio**: assume 100:1 for content (reads 100× writes); 10:1 for active applications; 1:1 for analytics.
- [ ] **Replication factor**: 3 is industry standard for durability (loses 2 nodes, still has 1).
- [ ] **Compression**: text → 4-10× with gzip/brotli/zstd; logs → 10×; images/video → already compressed.

## Capacity planning template
For any design problem:

```
DAU: ___
QPS:  writes = DAU * writes/user/day / 86400
      reads  = writes * read:write ratio
      peak   = avg * 3-5
Storage:
      per record = ___ bytes
      records/year = writes/sec * 86400 * 365
      total = per_record * records * replication_factor
Bandwidth:
      egress = peak_reads * avg_response_size
      ingress = peak_writes * avg_request_size
Cache size:
      hot data = top-X% by access frequency
      typical = 10–20% of total → fits in RAM if cluster sized right
```

## Practice problems (from a senior interviewer's list)

Time-box: 5 minutes each, no notes.
- [ ] How much storage does YouTube need per year?
- [ ] How many servers serve Google search at p99 ≤ 200 ms globally?
- [ ] How many Redis instances cache 90% of all Twitter timeline reads?
- [ ] Bandwidth from Netflix during US prime time?
- [ ] How long does it take to copy 1 PB across continents?

Practice these until you're fluent. The interviewer doesn't grade exact numbers; they grade **whether you can think in orders of magnitude under pressure**.

## Common methodology mistakes

- [ ] **Jumping into architecture before estimating** — interviewer asks "design Twitter," candidate immediately draws a diagram with Kafka and Cassandra. Wrong move; clarify first.
- [ ] **Not asking clarifying questions** — assume nothing. The interviewer is *waiting* for you to ask scale, latency, geo distribution.
- [ ] **Designing for *every* requirement** instead of prioritizing — say "out of scope" liberally.
- [ ] **Not justifying choices** — "I'll use Cassandra." Why? Tradeoffs?
- [ ] **Pretending your design is perfect** — admit weaknesses. Senior interviewers value calibration over confidence.
- [ ] **Running out of time on the diagram** — diagrams are tools, not deliverables. 5 boxes → deep dive.

## Self-check
> "Walk me through the back-of-envelope estimate for designing a system that serves 100M DAU sending 50 messages/day with 1MB attachments at p99 = 200ms. Calculate: messages/sec, peak writes, total storage/year, bandwidth at peak. Then say which back-end choice (DB, message queue, cache) is sized by which number."
