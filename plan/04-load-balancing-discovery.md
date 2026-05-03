# Phase 4 — Load Balancing & Service Discovery

Recap of [Network 07-router-lb-proxy.md](../../Network/Network/07-router-lb-proxy.md) plus the system-design-level questions: how services find each other, how requests get routed at API-gateway level, where service mesh fits.

## Core questions

### LB layers (recap)
- [ ] **L4 (TCP/UDP)**: routes by IP+port. Fast, opaque, doesn't terminate connections in pass-through modes. AWS NLB, HAProxy in TCP mode, IPVS, F5.
- [ ] **L7 (HTTP/HTTPS)**: terminates TCP/TLS, parses HTTP, routes by URL/header/cookie. NGINX, HAProxy in HTTP mode, AWS ALB, Envoy, Traefik.
- [ ] **DNS-based**: client resolves a hostname to one of N IPs. Cheap and global; client's DNS cache makes failover slow. Route 53 weighted routing.
- [ ] **Anycast**: same IP advertised from many locations; BGP routes traffic to nearest. Used by Cloudflare, Google, root DNS servers. Combine with L4/L7 inside each PoP.

### LB algorithms
- [ ] **Round-robin**: simple, equal distribution. Bad if backends have heterogeneous capacity or some requests are heavy.
- [ ] **Weighted round-robin**: weight by backend capacity.
- [ ] **Least connections**: send to backend with fewest in-flight. Better when request lengths vary.
- [ ] **Least response time**: backend with lowest p50/p99 latency. Adaptive.
- [ ] **IP hash / consistent hash**: same client → same backend. Useful for session affinity without sticky cookies; also for cache locality on backends.
- [ ] **Power of two choices**: pick two random backends, send to the less loaded. Surprisingly effective; near-optimal load distribution with minimal coordination.

### Sticky sessions
- [ ] Force a client to always hit the same backend (cookie or hash). Used when backend holds session state.
- [ ] **Antipattern in modern systems**: stateful backends defeat horizontal scaling. Push session into Redis / signed cookie / JWT instead.
- [ ] **Sometimes still needed**: WebSockets (the connection IS state), upload progress, in-process caches you don't want to invalidate too aggressively.

### Health checks
- [ ] LB periodically probes each backend; unhealthy backends removed from rotation.
- [ ] **Active**: LB sends `GET /health`. Backend returns 200 if everything's fine.
- [ ] **Passive**: LB watches actual request errors and removes backends that fail too often.
- [ ] **Two layers**:
  - **Liveness** ("am I alive?") — restart the pod if no
  - **Readiness** ("am I ready to serve traffic?") — pull from rotation if no
- [ ] **Pitfalls**:
  - Health check too shallow (returns 200 even when downstream is broken) → routes traffic to broken backends.
  - Health check too deep (touches all dependencies) → cascading failure: one downstream blip causes all backends to fail readiness simultaneously.
  - Solution: graded health (liveness shallow, readiness deeper, with hysteresis).

### Failover & redundancy
- [ ] **Multi-AZ**: at least one LB per AZ; client DNS resolves to a healthy AZ.
- [ ] **Multi-region**: DNS-based geo-routing or anycast.
- [ ] **The LB itself can be a SPOF** — run multiple, health-check the fleet.

## Service discovery

How does service A know where service B is? Three approaches:

### 1. DNS-based discovery
- [ ] Service B is registered as a DNS name (`service-b.internal`). Service A resolves and connects.
- [ ] **Pros**: simple, language-agnostic, just standard DNS.
- [ ] **Cons**: DNS caching is slow to react to topology change; clients may use stale entries for minutes; load balancing is up to whatever each client does (round-robin over A records).
- [ ] **Used by**: Kubernetes (CoreDNS), AWS Cloud Map, Consul DNS.

### 2. Server-side discovery (LB knows the backends)
- [ ] Clients send to a stable address (LB / API gateway). LB consults a service registry to pick a healthy backend.
- [ ] **Pros**: clients are dumb; routing logic lives in one place.
- [ ] **Cons**: LB is in every data path → another network hop → another component to scale and monitor.
- [ ] **Used by**: ELB/ALB/NLB, NGINX with consul-template, Kubernetes Services.

### 3. Client-side discovery (clients query a registry)
- [ ] Client asks the registry "give me healthy instances of service B," then load-balances itself.
- [ ] **Pros**: no LB hop; client can do smart things (locality preference, retries to other instances).
- [ ] **Cons**: every client implements load-balancing → duplicated logic; harder to upgrade; requires registry SDK.
- [ ] **Used by**: Eureka + Ribbon (Netflix OSS), Consul + smart proxies, gRPC built-in client-side LB.

### Service registries
- [ ] **Eureka**: Netflix; pure registry, no consensus.
- [ ] **Consul**: registry + health checks + KV store + DNS interface; uses Raft.
- [ ] **etcd**: KV store with watch; foundation of Kubernetes.
- [ ] **ZooKeeper**: registry + coordination; ephemeral nodes for liveness.
- [ ] **Kubernetes**: built-in via Service + Endpoints + EndpointSlices + (in newer versions) Gateway API.

### API gateway
- [ ] **Single front door** for external traffic. Responsibilities:
  - TLS termination
  - AuthN/AuthZ (validate JWT, OAuth)
  - Rate limiting per API key
  - Request transformation / aggregation (BFF — Backend for Frontend)
  - Routing to backend services
  - Logging / metrics
- [ ] **Examples**: AWS API Gateway, Kong, Apigee, Tyk, Envoy + custom config, Traefik.
- [ ] **Tradeoff**: convenient single place for cross-cutting concerns; can become bottleneck and SPOF if not horizontally scaled and replicated.
- [ ] **GraphQL gateway / federation** is a related pattern: gateway aggregates multiple GraphQL services.

### Service mesh (sidecar pattern)
- [ ] Inject a lightweight proxy (Envoy, Linkerd-proxy) as a sidecar next to every service.
- [ ] All inter-service traffic flows through sidecars → uniform place to enforce:
  - mTLS between services (zero-trust networking)
  - Retries, timeouts, circuit breakers, load balancing
  - Observability (metrics, traces) — automatically
  - Traffic shaping (canary, blue/green, mirror)
  - Authorization policy
- [ ] **Examples**: Istio (Envoy + control plane), Linkerd, Consul Connect, AWS App Mesh, Kuma.
- [ ] **Tradeoff**: ~1ms latency per hop, ~ doubles pod resource footprint; massive operational complexity. Big-org win; small-org overkill.
- [ ] **Newer trend (2024+)**: **ambient mesh** (Istio Ambient) — separate L4 (per-node ztunnel) from L7 (per-namespace waypoint) → reduce per-pod overhead.

### Sidecar vs library vs gateway
| Concern | Library in service | Sidecar | Gateway |
|---|---|---|---|
| Retries / timeouts / CB | Per-language SDK | Envoy config — language-agnostic | Per-API config |
| mTLS | Manual cert management per service | Auto-injected | At gateway only |
| Observability | Manual instrumentation | Free | At gateway only |
| Latency overhead | None | ~1ms per hop | ~1ms per request |
| Best for | Greenfield in one language | Heterogeneous fleet, security mandates | External-facing APIs |

### Connection pooling between services
- [ ] Don't open a new TCP/TLS connection per request. Reuse persistent connections via HTTP keep-alive / connection pool.
- [ ] **Sizing**: Little's Law again — `connections ≈ throughput × latency`.
- [ ] **Recycle**: even pools must rotate connections periodically — load balancers can't redistribute traffic if connections live forever.
- [ ] **HTTP/2 multiplexing**: many requests on one connection → fewer connections needed; but head-of-line blocking is at the TCP layer.
- [ ] **gRPC**: HTTP/2-based, generally one long-lived connection per pair; respect `MAX_CONNECTION_AGE` to allow LB rebalancing.

## Self-check
> "Behind your API gateway you have 200 service instances. The gateway uses round-robin. You add 50 more instances. They all start cold (empty caches, JIT not warmed). p99 latency spikes for 30 seconds. What's happening, and what three changes would you make?"
