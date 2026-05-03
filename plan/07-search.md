# Phase 7 — Search

## Core questions

### Why a separate search system?
- [ ] **Relational DBs are bad at full-text search.** `LIKE '%foo%'` doesn't use B+ tree indexes; full table scan. Even with Postgres `tsvector` / MySQL FULLTEXT, you cap out at modest scale.
- [ ] Search engines (Elasticsearch, OpenSearch, Vespa, Solr) provide:
  - Inverted index for fast text matching
  - Relevance scoring (BM25, learning-to-rank, vector similarity)
  - Faceting / aggregation
  - Distributed sharding tuned for read-heavy workloads
  - Query DSL richer than SQL for ranking

### The inverted index — the core data structure
- [ ] **Forward index** (what a normal DB has): `doc_id → contents`.
- [ ] **Inverted index**: `term → list of docs containing it` (with positions, frequencies).
  ```
  "rust"   → [doc1:[5,12], doc7:[2], doc42:[1]]
  "memory" → [doc7:[3], doc42:[2,8]]
  ```
- [ ] **Query for "rust memory"**: intersect the two postings lists → `[doc7, doc42]`. Score each. Return top K.
- [ ] **Tokenization** + **normalization** + **stemming** + **stopwords** happen at index time. "Running" / "ran" / "runs" → `run` token via stemming → matches a query for "ran."
- [ ] **Analyzers** are pluggable (per-language, per-domain) and you index and query through the same analyzer.

### Scoring (BM25)
- [ ] **TF-IDF** (older): `score = tf × log(N/df)` — frequent terms weigh less; doc with more matches wins.
- [ ] **BM25** (modern default): TF-IDF refined to handle term-frequency saturation and document length normalization. Default in Elasticsearch/Lucene since 2015.
- [ ] **Boosting**: amplify some fields (`title^3`, `body^1`) at query time.
- [ ] **Function queries**: blend in business signals (recency, popularity, click-through). `BM25 × log(views) × decay(age)`.
- [ ] **Learning to rank (LTR)**: train an ML model to re-rank top-K results. Used by every big search engine.

### Vector / semantic search (the 2024+ shift)
- [ ] Encode query + documents as embeddings (e.g., 768-dimensional vectors). Similarity = cosine or dot-product.
- [ ] Captures meaning beyond keyword overlap ("automobile" matches "car" without explicit synonym dictionary).
- [ ] **Approximate nearest-neighbor (ANN)**: HNSW, IVF, ScaNN. Sub-linear search over millions of vectors.
- [ ] **Hybrid search**: combine BM25 + vector with a weighted blend or RRF (Reciprocal Rank Fusion) — usually beats either alone.
- [ ] **Vector DBs**: Qdrant, Weaviate, Milvus, pgvector (Postgres extension), Pinecone (managed), Elasticsearch / OpenSearch (vector support added).

### Elasticsearch / OpenSearch architecture
- [ ] **Cluster** of nodes; each holds **shards** of indexes.
- [ ] **Index** is a logical namespace (often per-day for logs, per-tenant for SaaS).
- [ ] **Shard** is a Lucene index — physical unit of work; primary + replicas.
- [ ] **Default sharding**: hash on document `_id`. Customizable.
- [ ] **Query path**: client → coordinator node → fan out to all relevant shards → each returns top K → coordinator merges → return top K to client. **Scatter-gather.**
- [ ] **Index path**: client → coordinator → primary shard → replicate to replicas → ack.
- [ ] **Refresh interval**: ES is **near real-time**, not real-time. New documents become searchable after a refresh (default 1 second). Tune up for higher write throughput at the cost of staleness.
- [ ] **Bulk indexing**: batch document ingest; 5-10 MB batch sizes are typical. Single-doc indexing is wasteful.

### Sharding strategies for search
- [ ] **Default (hash on _id)**: even distribution, scatter-gather on every query.
- [ ] **Routing key**: pin all docs for one tenant to one shard → tenant queries hit one shard. Scales well for SaaS multi-tenant.
- [ ] **Time-based** (logs, events): one index per day → new writes hit only the latest index; old indexes can be moved to cheaper storage tiers.

### Faceting / aggregation
- [ ] After matching, ES can compute counts per field (filters): "show me top brands among matching products" → for free in one query.
- [ ] Implementation: post-filter aggregation, doc values (column-store-like layout for facet fields).

### Replication and HA
- [ ] **Replicas**: each primary shard has N replicas. Reads can serve from any. Writes go to primary, replicate.
- [ ] **Single-cluster gotcha**: ES doesn't do strict consensus across the cluster — split-brain has historically been a real problem (resolved largely with the 7.x voting-only nodes; still requires careful master-eligible node count).
- [ ] **Snapshot to S3** for backups; cross-cluster replication for DR.

### Indexing pipeline
- [ ] **Ingest from source**: DB CDC (Debezium → Kafka → indexer → ES); polling; app-direct writes; ETL job.
- [ ] **Idempotent**: use the source primary key as the ES `_id` so re-runs overwrite, don't duplicate.
- [ ] **Bulk + parallel**: a few indexer workers, batch 5-10MB, throughput in tens of thousands of docs/sec per cluster.
- [ ] **Reindex** when mapping changes — alias trick: query against an alias; reindex into a new index; flip the alias atomically.

### Mappings (the schema)
- [ ] Fields are typed: `text` (analyzed), `keyword` (exact), `long`, `date`, `geo_point`, etc.
- [ ] Strings analyzed for full-text become `text`; if you need exact matching / sorting / aggregation, also store as `keyword` (multi-field).
- [ ] **Mapping explosion**: dynamic mappings on user data can blow up the cluster. Disable dynamic mapping on production indexes.

### Query DSL highlights
- [ ] **Match query**: full-text `{ match: { title: "rust memory" }}` — analyzed and scored.
- [ ] **Term query**: exact `{ term: { status: "active" }}` — no analysis.
- [ ] **Bool query**: combine with `must`, `should`, `must_not`, `filter`.
- [ ] **Filter context** (cache-friendly, no scoring) vs **query context** (scored, more expensive).
- [ ] **Aggregations**: terms, range, histogram, cardinality, percentiles. Powerful — but expensive on huge datasets.

### Performance tuning
- [ ] **Refresh interval up** (e.g., 30s) for high-write workloads.
- [ ] **Disable `_source` selectively** if you only need to retrieve specific fields.
- [ ] **Filter context** for common filters (status=active, tenant=X) → cached.
- [ ] **Avoid deep pagination** (`from + size > 10_000` is rejected by default). Use `search_after` (cursor pagination) like in [DB 04](../../Database/Database/plan/04-query-optimization.md).
- [ ] **Doc values** for sort/aggregation fields; **fielddata** for `text` fields if you must aggregate (expensive).

### Trade: search vs DB consistency
- [ ] Search is **eventually consistent** with the source DB. The CDC/indexer pipeline is async.
- [ ] If users post → "where's my post?" — the post may not be searchable yet. UX: route the user's own recent posts via a different code path (DB query, not search), at least for the next N seconds.

## Hands-on (Python)

```python
# Index and search with elasticsearch-py
from elasticsearch import Elasticsearch
es = Elasticsearch(['https://es-host:9200'])

# Bulk index
docs = [
    {"_index": "products", "_id": p['sku'], "_source": p}
    for p in products
]
from elasticsearch.helpers import bulk
bulk(es, docs)

# Search with filter + match + aggregation
result = es.search(index="products", body={
    "query": {
        "bool": {
            "must":   [{"match": {"description": "noise cancelling headphones"}}],
            "filter": [{"term": {"in_stock": True}},
                       {"range": {"price": {"lte": 300}}}]
        }
    },
    "aggs": {
        "by_brand": {"terms": {"field": "brand.keyword", "size": 10}}
    },
    "size": 20
})
```

```python
# Hybrid search: BM25 + vector with reciprocal rank fusion
def hybrid_search(query, query_vec, k=20):
    bm25 = es.search(index="docs", body={
        "query": {"match": {"text": query}}, "size": k * 5
    })
    vec = es.search(index="docs", body={
        "knn": {"field": "embedding", "query_vector": query_vec, "k": k * 5, "num_candidates": 100}
    })
    # RRF: each document's rank in each list contributes 1/(60+rank)
    ranks = {}
    for i, hit in enumerate(bm25['hits']['hits']):
        ranks[hit['_id']] = ranks.get(hit['_id'], 0) + 1 / (60 + i)
    for i, hit in enumerate(vec['hits']['hits']):
        ranks[hit['_id']] = ranks.get(hit['_id'], 0) + 1 / (60 + i)
    return sorted(ranks.items(), key=lambda x: -x[1])[:k]
```

## Self-check
> "Design the search architecture for an e-commerce site: 100M products, 1M searches/min, < 200ms p99, supports faceted filters (brand, price range, in-stock) and full-text. Walk through: indexing pipeline from product DB, sharding choice, query path, hot-product caching, hybrid relevance scoring."
