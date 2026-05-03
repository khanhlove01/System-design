# Phase 9 — API Design

## Core questions

### REST vs GraphQL vs gRPC — when each
| | REST | GraphQL | gRPC |
|---|---|---|---|
| Wire format | JSON over HTTP/1 or 2 | JSON over HTTP/1 or 2 | Protobuf over HTTP/2 |
| Schema | Optional (OpenAPI) | Required (SDL) | Required (.proto) |
| Endpoint shape | One per resource (`/users/{id}`) | One endpoint, queries describe what to fetch | Generated client + server stubs |
| Over-fetching | Common (`/users/123` returns everything) | Solved (client picks fields) | Solved (msg shape is exact) |
| Under-fetching / N+1 | Common (need to call /users + /orders) | Solved (one query, multiple resources) | Solved (one RPC) |
| Browser-friendly | Yes | Yes | Needs grpc-web proxy |
| Streaming | SSE / chunked transfer | Subscriptions | First-class (server / client / bidi) |
| Caching (HTTP) | Native (URL-based) | POST defeats HTTP cache | Not natively (RPC has no URLs) |
| Best for | Public APIs, simple CRUD | Aggregating multiple backends, mobile/web with varied needs | Internal microservice-to-microservice |
| Default in 2026 | Public-facing | When clients have varied data needs | Service mesh internal |

- [ ] **Public API → REST.** Hard to beat for ecosystem reasons (curl, browser, every SDK).
- [ ] **Aggregating BFF for mobile/web → GraphQL.** Reduces over-fetching and round-trips.
- [ ] **Service-to-service → gRPC.** Performance (binary proto, HTTP/2 multiplexing), generated typed clients, deadlines built-in.
- [ ] **Don't dogmatically pick one** — large systems use all three (gRPC internal + REST public + maybe GraphQL gateway).

### REST design principles
- [ ] **Resource-oriented**: nouns, not verbs. `POST /orders` (create), `GET /orders/123`, `DELETE /orders/123`.
- [ ] **Verb meanings**:
  - `GET` — read, safe, **idempotent**, cacheable.
  - `POST` — create / non-idempotent action.
  - `PUT` — replace (idempotent).
  - `PATCH` — partial update.
  - `DELETE` — idempotent (deleting an already-deleted thing is OK; return 204 / 404 — be consistent).
- [ ] **Status codes**: use them precisely.
  - `200 OK` — success with body
  - `201 Created` — POST that created (include `Location` header)
  - `204 No Content` — success, no body
  - `400 Bad Request` — client error (validation)
  - `401 Unauthorized` — not authenticated
  - `403 Forbidden` — authenticated but not allowed
  - `404 Not Found` — resource doesn't exist
  - `409 Conflict` — state conflict (concurrent update, duplicate)
  - `422 Unprocessable Entity` — semantically invalid
  - `429 Too Many Requests` — rate-limited (include `Retry-After`)
  - `500 Internal Server Error` — server bug
  - `502/503/504` — upstream / unavailable / timeout
- [ ] **Versioning**: URL (`/v1/users`) is the most common. Header (`Accept: application/vnd.example.v2+json`) is purer but operationally annoying.
- [ ] **Hypermedia / HATEOAS**: include links to related resources in responses. Theoretical purity wins; practical adoption is rare.

### Idempotency keys (the production must-have)
- [ ] **Problem**: any network call can be retried — by the client, by the load balancer, by the SDK. Without idempotency, retries cause duplicates (double charges, double emails).
- [ ] **Solution**: client generates a UUID per logical action; sends as `Idempotency-Key` header. Server stores `(key → response)` for a retention window (24-48h typical).
- [ ] **On replay**: server returns the cached response without re-executing.
- [ ] **Stripe API** is the canonical example — every POST that creates state takes an idempotency key.

### Pagination
- [ ] **Offset-based** (`?page=5&size=20`): convenient for UIs that show page numbers; **terrible** at scale (`OFFSET 1000000` walks 1M rows — see [DB 04](../../Database/Database/plan/04-query-optimization.md)).
- [ ] **Cursor-based** (`?after=<opaque-cursor>&limit=20`): server emits an opaque cursor in each response; client passes it back. O(log N + limit). The right answer.
- [ ] **Infinite scroll** UIs map naturally to cursors.
- [ ] Cursors should encode `(sort_key_value, primary_key)` for stable ordering through deletes/inserts.

### Error model
- [ ] **Consistent envelope** for errors:
  ```json
  {
    "error": {
      "code": "INSUFFICIENT_FUNDS",
      "message": "Account balance is insufficient for this withdrawal.",
      "request_id": "req_abc123",
      "details": {...}
    }
  }
  ```
- [ ] **Stable error codes** (not just messages) — clients can switch on them.
- [ ] **`request_id`** in every error → support can correlate with logs.
- [ ] Don't leak internals (stack traces, SQL, internal hostnames) in 5xx responses.

### Versioning strategies
- [ ] **Backward-compatible changes** (additive — new fields, new endpoints, new optional params): **don't break existing clients**, no version bump needed.
- [ ] **Breaking changes**: new version. Deprecate old gracefully (announce, sunset header, finally remove). Aim for 6-12 month deprecation windows on public APIs.
- [ ] **Internal services** (gRPC + your own clients): you own all the clients → coordinated upgrades, faster deprecations.
- [ ] **Don't break clients silently** — return `Sunset` header / explicit error.

### Security headers (recap from [Security 05](../../Security/plan/05-web-security.md))
- [ ] CORS, HSTS, CSP, X-Frame-Options, X-Content-Type-Options.
- [ ] Authentication: bearer tokens (JWT, opaque session IDs), OAuth, mTLS for service-to-service.
- [ ] Always over HTTPS. Always.

## Rate limiting

### Why
- [ ] Protect upstreams from abuse (intentional or accidental).
- [ ] Enforce fair use across tenants (multi-tenant SaaS).
- [ ] Stop bots / brute force / scraping.
- [ ] Cost control on metered downstreams.

### Algorithms
- [ ] **Fixed window**: `requests per minute = N`. Counts reset on the minute boundary. Simple, but burst on minute boundaries.
- [ ] **Sliding window log**: store timestamp of each request; count those in the last N seconds. Accurate; storage grows with traffic.
- [ ] **Sliding window counter**: approximation — weighted blend of current + previous window counts. Cheap and good enough for most.
- [ ] **Token bucket** (most common):
  - Bucket holds up to `B` tokens; tokens added at rate `R/sec`.
  - Each request consumes one token; if empty, reject (or queue).
  - **Allows bursts** up to bucket size; smooths to rate `R` over time. Used by AWS, Stripe, Cloudflare.
- [ ] **Leaky bucket**: requests fill bucket; bucket drains at constant rate `R`. Smooths bursts; rejects when full.
- [ ] **Concurrency limit**: max `N` in-flight requests at once (semaphore). Different axis — bounds resource use rather than rate.

### Distributed rate limiting (the hard part)
- [ ] If your service has 100 instances behind a load balancer, each with its own counter → effective rate = 100× nominal limit.
- [ ] **Fix**: shared state.
  - **Redis** with `INCR` + `EXPIRE` for fixed-window counts.
  - **Redis Lua script** for atomic token-bucket math.
  - **Per-tenant key** (`rl:user:123`); reject when over limit.
- [ ] **Cost**: every request now does a Redis call. Mitigations: local "shadow" counter that syncs to Redis periodically (eventually consistent — slightly over-allow for fairness).
- [ ] **Distributed token bucket** is a published pattern: SCRIPT in Redis maintains `(tokens, last_refill)`; client SCRIPT calls atomic.

### Where to enforce
- [ ] **Edge / CDN / WAF**: cheap, blocks attackers before they hit your infra. Cloudflare/Fastly/AWS WAF can do thousands of rules.
- [ ] **API gateway**: per-API-key, per-tenant. The natural enforcement point.
- [ ] **Per-service**: defense in depth. Especially for downstream-cost limits ("max 10 req/sec to the expensive vendor API").
- [ ] **Per-DB-pool / per-resource**: connection pool acts as an implicit rate limit.

### Returning the 429
- [ ] `429 Too Many Requests` + `Retry-After: <seconds>` header (or HTTP-date).
- [ ] Body: explain the limit ("100 req/min reached, retry in 23 seconds").
- [ ] Optionally include rate-limit headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

## Hands-on (Python)

```python
# Token bucket in Redis (atomic via Lua script)
import redis, time

LUA = """
local tokens_key = KEYS[1]
local refill_rate = tonumber(ARGV[1])  -- tokens/sec
local capacity   = tonumber(ARGV[2])
local now        = tonumber(ARGV[3])
local cost       = tonumber(ARGV[4])

local tokens, last = redis.call('HMGET', tokens_key, 'tokens', 'last')
tokens = tonumber(tokens) or capacity
last   = tonumber(last) or now

local elapsed = now - last
tokens = math.min(capacity, tokens + elapsed * refill_rate)
local allowed = 0
if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
end
redis.call('HMSET', tokens_key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', tokens_key, 3600)
return {allowed, tokens}
"""
r = redis.Redis()
script = r.register_script(LUA)

def allow(key, rate=10, capacity=20):
    allowed, _ = script(keys=[key], args=[rate, capacity, time.time(), 1])
    return bool(allowed)

if not allow(f"user:{user_id}", rate=10, capacity=20):
    return 429, {"Retry-After": "1"}
```

```python
# Idempotency key handling
import hashlib, json
def handle_post(request, body):
    key = request.headers.get("Idempotency-Key")
    if key:
        cached = r.get(f"idem:{key}")
        if cached:
            return json.loads(cached)         # replay
        # take a short-lived lock so we don't double-execute under high concurrency
        with redis_lock(f"idem-lock:{key}", timeout=30):
            cached = r.get(f"idem:{key}")     # double-check after lock
            if cached: return json.loads(cached)
            response = create_resource(body)
            r.set(f"idem:{key}", json.dumps(response), ex=86400)
            return response
    else:
        return create_resource(body)
```

## Self-check
> "Design the public REST API for a payments service: charge a card, refund a charge, list charges. Include error model, idempotency, pagination, rate limiting (per-API-key tier), versioning, and what makes a good 5xx response. What changes if the same API also has a gRPC variant for internal services?"
