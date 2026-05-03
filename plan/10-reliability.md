# Phase 10 — Reliability Patterns

How systems stay up when components don't. The patterns here all share a theme: **bound the blast radius of any single failure**.

## Core questions

### Timeout
- [ ] **Every** network call needs a timeout. Without one, a downstream that hangs takes you down too.
- [ ] **Tier the timeouts**: gateway timeout > service timeout > RPC timeout > DB query timeout. Each layer's timeout is shorter than the layer above so an inner timeout fires before the outer.
- [ ] **Connect timeout** vs **read timeout** — set both. Connect = "did we establish TCP?", read = "are bytes flowing?"
- [ ] **Default to short timeouts** (< 1s for most internal calls). Long timeouts = long tail latency under failure.
- [ ] **Don't increase timeouts to make a flake go away** — that just lengthens the outage when the flake becomes a real failure.

### Retry with exponential backoff + jitter
- [ ] **Naive retry**: failed → retry immediately → fail again → DDoS your own backend during a brownout.
- [ ] **Exponential backoff**: `wait = base × 2^attempt`. 100ms, 200ms, 400ms, ...
- [ ] **Jitter** (essential): add randomness so 1000 clients don't retry at the same instant.
  - **Full jitter**: `wait = random(0, base × 2^attempt)`. AWS architecture blog calls this "decorrelated."
  - **Equal jitter**: half-fixed + half-random. Slightly less spread, more bounded.
- [ ] **Cap the retries**: 3-5 attempts max. After that, fail fast and let the caller decide.
- [ ] **Retry budget**: cap the *fraction* of requests being retries (e.g., 20% max). Prevents retry storms during partial outages.
- [ ] **What's safe to retry**: GET, idempotent operations, operations with idempotency keys. **Don't retry POSTs without an idempotency key** — you may double-charge.

### Circuit breaker
- [ ] **Three states**: Closed (normal), Open (fail fast — don't even try the downstream), Half-open (let a few probe requests through to test recovery).
- [ ] **Why**: when downstream is broken, retrying just makes things worse — slow failures pile up, threads block, your service dies. Better to fail fast.
- [ ] **Implementation**: track recent error rate; on threshold (e.g., 50% errors over last 100 calls or 30s), open the circuit. Recover after a cooldown by entering half-open and probing.
- [ ] **Library**: Hystrix (deprecated but the name still gets dropped), resilience4j (Java), polly (.NET), opossum / cockatiel (JS), pyfailsafe / circuitbreaker (Python), gobreaker (Go).
- [ ] **Per-downstream circuit**: don't lump all downstreams together — one slow one shouldn't fail-fast the others.

### Bulkhead
- [ ] **Isolate resources** so a problem in one area can't drain everything.
- [ ] **Pattern**: separate thread pools / connection pools / quotas for different downstream services. If `slow-service` is hung, the threads waiting on it are bounded; calls to `fast-service` aren't affected.
- [ ] **Naming**: from ship hulls — sealed compartments stop one breach from sinking the ship.
- [ ] **In practice**:
  - Different `requests.Session` per downstream with its own connection pool.
  - Different thread/asyncio semaphore per downstream.
  - At the OS level: containers with cgroup limits per service.

### Hedging
- [ ] **Send the same request to two replicas; use whichever responds first; cancel the other.**
- [ ] **Win**: lowers tail latency dramatically. p99 of `min(A, B)` is much less than p99 of `A`.
- [ ] **Cost**: ~2× traffic on the (small) tail of slow requests. Implement as "send to A; if A hasn't responded in p95 ms, also send to B; take whichever wins."
- [ ] **Used by**: Google search, gRPC has built-in support.
- [ ] **Don't hedge** non-idempotent operations (you'd execute the action twice).

### Backpressure (recap from [02-scaling.md](02-scaling.md))
- [ ] When you can't keep up, push back instead of buffering or dropping silently.
- [ ] **Bounded queues**: producer blocks (or returns 429) when the queue is full.
- [ ] **`429 Too Many Requests`** at the edge.
- [ ] **Adaptive concurrency**: dynamically adjust max-concurrency based on observed latency (Netflix's adaptive concurrency limits / "concurrency-limits" library).

### Graceful degradation
- [ ] **When a feature can't fully work, do what you can.** A degraded experience > total outage.
- [ ] Examples:
  - **Search down** → show recent items / cached popular items.
  - **Recommendation service down** → show "trending" instead of personalized.
  - **Avatar service down** → show default avatar; don't fail the page.
  - **Comments service down** → render the article without comments, with "comments unavailable" notice.
- [ ] **Static fallbacks**: cached, possibly stale, content served when the dynamic source fails (`stale-if-error`).

### Failure injection (chaos engineering)
- [ ] **Plan for failure by causing it on purpose** — find weaknesses before they find you.
- [ ] **Practices**:
  - **Game days**: scheduled exercises where you take down a region or kill a service.
  - **Chaos Monkey** (Netflix): randomly terminate VMs in production. Forces apps to be resilient.
  - **Latency injection**: add 500ms to all DB calls; see what breaks.
  - **Failure injection at service mesh**: Istio fault injection — return errors / delays for X% of traffic to a service.
- [ ] **Start in staging**, build confidence, then carefully introduce in production.

### Health checks (recap from [04-load-balancing-discovery.md](04-load-balancing-discovery.md))
- [ ] **Liveness**: am I alive? (process running, basic state OK). Restart on failure.
- [ ] **Readiness**: am I ready for traffic? (warmup done, dependencies reachable). Pull from rotation on failure, don't restart.
- [ ] **Avoid**: health checks that depend on the whole world. One slow downstream shouldn't fail the entire fleet's readiness.

### The error budget
- [ ] **SLO**: Service Level Objective — your reliability target (e.g., 99.9% success rate over 30 days).
- [ ] **Error budget**: 100% - SLO. For 99.9%, you have 0.1% × 30 days = ~43 min of "allowed badness" per month.
- [ ] **Why useful**: when you have budget left, ship features fast; when you've burned it, **slow down**, focus on reliability work.
- [ ] **Connects reliability to the business** — execs understand "we have $X of error budget to spend on risky deploys."

### Failover patterns
- [ ] **Active-passive**: secondary stays warm; takes over on primary failure. Simple. Wasteful (idle resources).
- [ ] **Active-active**: both serve traffic; share load; tolerate one losing. More efficient but harder consistency.
- [ ] **Multi-AZ within a region**: cheap and almost mandatory. Requires async/sync replication of state.
- [ ] **Multi-region**: hard. Latency of sync replication = bad; async = data loss on failover. Used for DR (cold/warm standby) and global availability.
- [ ] **Read replicas in another region**: easy half-step. Reads served locally; writes still cross region.

### Bulkhead vs circuit breaker — they compose
- [ ] **Bulkhead** prevents one slow downstream from exhausting the shared pool.
- [ ] **Circuit breaker** prevents you from even trying the slow downstream.
- [ ] **Together**: separate pool per downstream + circuit breaker per downstream. State of the art for service-to-service calls.
- [ ] Service mesh (Envoy) handles all this for you with config — no code changes per service.

### What not to do
- [ ] **Retry on 4xx errors** — those are *your* problem. Retrying a 400 won't make it a 200.
- [ ] **Hard-coded sleep + retry** without backoff or jitter.
- [ ] **Catch-all `except`** that hides errors.
- [ ] **Health-check that's too deep** (touches every dependency) — first downstream blip → cluster-wide failure.
- [ ] **Treating availability as binary** — design for **gradual degradation**, not **up/down**.

## Hands-on (Python)

```python
# Retry with exponential backoff + full jitter
import random, time
from functools import wraps

def retry(max_attempts=5, base=0.1, cap=10):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kw):
            for attempt in range(max_attempts):
                try: return fn(*args, **kw)
                except RetryableError as e:
                    if attempt == max_attempts - 1: raise
                    sleep = random.uniform(0, min(cap, base * 2**attempt))
                    time.sleep(sleep)
        return wrapper
    return deco
```

```python
# Tiny circuit breaker
import time, threading
from contextlib import contextmanager

class CircuitBreaker:
    def __init__(self, threshold=5, cooldown=30):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures = 0
        self.opened_at = 0
        self.lock = threading.Lock()

    @contextmanager
    def call(self):
        with self.lock:
            if self.opened_at and time.time() - self.opened_at < self.cooldown:
                raise CircuitOpen()
        try:
            yield
            with self.lock:
                self.failures = 0
                self.opened_at = 0
        except Exception:
            with self.lock:
                self.failures += 1
                if self.failures >= self.threshold:
                    self.opened_at = time.time()
            raise

cb = CircuitBreaker()
def call_downstream():
    with cb.call():
        return requests.get("https://downstream/", timeout=1)
```

```python
# Hedged requests (cancellation-aware async version)
import asyncio
async def hedged(coro_factory, p95=0.05):
    primary = asyncio.create_task(coro_factory())
    try:
        result = await asyncio.wait_for(asyncio.shield(primary), timeout=p95)
        return result
    except asyncio.TimeoutError:
        backup = asyncio.create_task(coro_factory())
        done, pending = await asyncio.wait({primary, backup}, return_when=asyncio.FIRST_COMPLETED)
        for p in pending: p.cancel()
        return done.pop().result()
```

## Self-check
> "Service A calls service B which calls service C. C starts returning 50% errors. Walk through what happens (a) without any reliability patterns, (b) with timeouts only, (c) with timeouts + retries, (d) with timeouts + retries + circuit breakers. At what point does the system survive C's failure gracefully?"
