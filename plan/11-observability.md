# Phase 11 — Observability

You can't operate what you can't see. Observability is the *third pillar* of system design alongside scalability and reliability — and the one most candidates underweight in interviews.

## Core questions

### The three pillars (and why they're now converging)
| Signal | What it answers | Volume | Cost |
|---|---|---|---|
| **Metrics** | "How is the system performing right now?" — aggregated time-series | Compact (millions of points/sec → MB) | Cheap |
| **Logs** | "What happened in this specific request / event?" — discrete records | Voluminous (TB/day) | Expensive |
| **Traces** | "What's the full path of this one request through N services?" — causally-linked spans | Sampled subset | Medium |

- [ ] **Convergence**: OpenTelemetry (OTel) standardizes all three under one SDK + protocol → you instrument once, ship to Datadog / Grafana / Honeycomb / New Relic / ...
- [ ] **Modern view**: traces are the structure; metrics are aggregations *over* spans; logs are events *attached to* spans. Honeycomb-style "wide events" subsume all three for some teams.

### Metrics — the fundamentals
- [ ] **Counter**: monotonic — only goes up. `requests_total`, `errors_total`. Rate via `rate(requests_total[5m])`.
- [ ] **Gauge**: arbitrary value — goes up and down. `memory_used_bytes`, `queue_depth`.
- [ ] **Histogram**: distribution of values. `request_duration_seconds`. Sum + count + buckets → derive percentiles (p50, p95, p99).
- [ ] **Summary**: pre-computed quantiles per instance. Less flexible than histogram (can't aggregate across instances). Generally avoid in favor of histograms.
- [ ] **Cardinality**: each unique label combination is a separate time series. `request_total{path,method,status,user_id}` with `user_id` → millions of series → bills explode. **Keep label cardinality bounded.** No user IDs, no request IDs, no email addresses as labels.

### The two diagnostic frameworks
#### RED method — for request-driven services
- [ ] **R**ate: requests per second.
- [ ] **E**rrors: errors per second (or error rate).
- [ ] **D**uration: latency distribution (p50, p99, p999).

#### USE method — for resource utilization
- [ ] **U**tilization: % time the resource is busy (CPU, disk, network).
- [ ] **S**aturation: backlog / queue / wait time when over-utilized.
- [ ] **E**rrors: device errors, dropped packets, etc.

#### Four golden signals (Google SRE)
- [ ] **Latency** — p50, p99, p999.
- [ ] **Traffic** — request rate.
- [ ] **Errors** — error rate.
- [ ] **Saturation** — how full the system is.

These all overlap. Pick a vocabulary; be consistent.

### Logging — done right
- [ ] **Structured logging** (JSON or key=value), not free-form prose. Machine-queryable, indexed.
- [ ] **Levels**: ERROR (something failed), WARN (recoverable), INFO (normal flow), DEBUG (verbose). Production runs INFO+ usually.
- [ ] **Correlation IDs** in every log line: `request_id`, `trace_id`, `user_id` (hashed). Lets you reconstruct one request's journey across services.
- [ ] **Don't log secrets, PII, full request bodies, full headers.** Regulatory + security risk.
- [ ] **Sampling**: at huge scale, log 10% of normal requests; 100% of errors.
- [ ] **Log aggregation**: Elasticsearch (ELK), Loki, Splunk, Datadog Logs. Centralized, searchable, retention-bounded.

### Distributed tracing
- [ ] **Trace** = the full journey of one request. **Span** = one operation within the trace (one service's work, one DB call). Spans have parent-child relationships → tree.
- [ ] **Trace ID** is generated at the entry point, propagated via headers (`traceparent` per W3C Trace Context) through every downstream call.
- [ ] **Each span records**: start time, duration, service name, operation, tags (HTTP method, status, etc.), events (logs attached to this span).
- [ ] **What you can answer**:
  - "Why was *this specific* request slow?" — see the span tree, find the long bar.
  - "Which downstream is contributing the most to my p99?" — aggregate over many traces.
  - "Did this user's request actually reach service X?" — find their trace.
- [ ] **Sampling**: 100% trace collection is expensive. **Head-based sampling** (decide at entry; e.g., 1%); **tail-based sampling** (collect all spans, decide after — keep all errors and slow ones, drop rest). Tail-based is more useful but harder to deploy.
- [ ] **Implementations**: Jaeger, Zipkin, Tempo, Datadog APM, Honeycomb, Lightstep, AWS X-Ray.
- [ ] **Standard**: OpenTelemetry (OTel) — the SDK + protocol. Use it.

### SLI / SLO / SLA — the language of reliability
- [ ] **SLI** (Service Level **Indicator**): a measurable property of the service. "% of requests served < 200ms." "% of requests not 5xx."
- [ ] **SLO** (Service Level **Objective**): a target on an SLI. "99.9% of requests served < 200ms over 30 days."
- [ ] **SLA** (Service Level **Agreement**): a contract with customers, with penalties. Usually looser than internal SLOs.
- [ ] **Error budget**: `1 - SLO`. For 99.9% SLO, you have 0.1% × 30d ≈ 43min of "allowed badness" per month.
- [ ] **Error budget policy**:
  - Burning slowly → ship features, take measured risks.
  - Burning fast / depleted → freeze risky deploys, prioritize reliability.
- [ ] **Pick SLOs that map to user happiness**, not just "is the service up." If the API is "up" but every request takes 30s, users are unhappy.

### Alerting — the rules
- [ ] **Alert on symptoms (user-visible), not causes** — "p99 latency exceeded SLO" beats "CPU > 80%". CPU at 80% might be totally fine.
- [ ] **Alerts must be actionable** — every page should have a clear "what to do." Otherwise → alert fatigue → ignored real alerts.
- [ ] **Multi-window, multi-burn-rate alerts** (Google SRE):
  - **Fast burn**: error budget burning at >14× normal rate over 1h → page immediately.
  - **Slow burn**: budget burning at 6× over 6h → ticket.
- [ ] **Tiering**:
  - **Page** — wake someone up.
  - **Ticket** — investigate next business day.
  - **Log/dashboard** — informational.
- [ ] **Runbooks** — every alert links to a runbook explaining diagnosis steps + common fixes.

### Dashboards
- [ ] **Top-level**: golden signals for each major service. One screen.
- [ ] **Service-level**: RED + USE for each service.
- [ ] **Per-component**: DB-specific (cache hit, replication lag, lock waits), queue-specific (depth, oldest message age), cache-specific (hit rate, eviction).
- [ ] **Build dashboards before you need them.** During an outage you don't have time to invent queries.

### Profiling and continuous profiling
- [ ] **CPU profiling**: which functions consume CPU? `py-spy` (Python), `perf` (Linux), `pprof` (Go), `async-profiler` (Java).
- [ ] **Heap profiling**: memory allocations / live objects.
- [ ] **Continuous profiling**: low-overhead profiling running in production all the time. Pyroscope, Parca, Datadog Profiling, Polar Signals. Lets you correlate latency spikes with code-level CPU/heap behavior.

### What to instrument (the practical checklist)
For every service:
- [ ] Inbound: requests/sec, error %, latency histogram (p50, p95, p99, p999), per endpoint.
- [ ] Outbound: same, per downstream.
- [ ] Pool depths: thread pool, connection pool — utilization + saturation.
- [ ] Queue depths: oldest message age, depth.
- [ ] Cache: hit rate, eviction rate.
- [ ] Resource: CPU, memory, FDs, GC pause time.
- [ ] Business metrics: orders/sec, signups/sec, payments/sec.

The last one is critical — pure technical metrics can be green while your business is broken.

## Hands-on (Python)

```python
# Prometheus client — record metrics
from prometheus_client import Counter, Histogram, Gauge, start_http_server

REQUEST_COUNT = Counter('http_requests_total', 'Total requests', ['method','path','status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'Request latency',
                            ['method','path'],
                            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])
QUEUE_DEPTH = Gauge('queue_depth', 'Pending jobs')

start_http_server(9000)         # /metrics endpoint

import time
def handle(request):
    start = time.time()
    try:
        response = serve(request)
        REQUEST_COUNT.labels(request.method, request.path, response.status).inc()
        return response
    finally:
        REQUEST_LATENCY.labels(request.method, request.path).observe(time.time() - start)
```

```python
# OpenTelemetry tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317"))
)
tracer = trace.get_tracer(__name__)

def process_order(order_id):
    with tracer.start_as_current_span("process_order", attributes={"order.id": order_id}):
        with tracer.start_as_current_span("fetch_order"):
            order = db.fetch(order_id)
        with tracer.start_as_current_span("charge_card"):
            charge_card(order)
```

```python
# Structured logging with correlation IDs
import logging, json
class JsonFormatter(logging.Formatter):
    def format(self, rec):
        d = {"ts": self.formatTime(rec), "lvl": rec.levelname, "msg": rec.getMessage(),
             "logger": rec.name, **getattr(rec, 'extra', {})}
        return json.dumps(d)

logger = logging.getLogger("svc")
logger.handlers = [logging.StreamHandler()]
logger.handlers[0].setFormatter(JsonFormatter())

# Inject request_id from middleware
def handler(request):
    req_id = request.headers.get('X-Request-Id') or new_uuid()
    logger.info("processing order", extra={'extra': {'request_id': req_id, 'user_id': hash(request.user.id)}})
```

## Self-check
> "Your service's p99 latency is 2 seconds; the SLO is 500ms. The team has been burning the error budget at 5× normal for 3 days. Walk me through: what dashboards you'd open first, what you'd look for in metrics vs logs vs traces, and how you'd decide whether to roll back, scale up, or open an incident."
