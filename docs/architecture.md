# Architecture

```mermaid
flowchart LR
    G[GitLab merge request] --> H[Authenticated webhook]
    H --> D[Bounded raw diff fetch]
    D --> O[Async review orchestrator]
    O --> S[Security]
    O --> T[Test gaps]
    O --> U[Summary]
    S --> V[Added-line verification]
    V --> J[Judge]
    T --> J
    U --> J
    J --> N[Advisory GitLab note]
    P[OpenAI-compatible provider] -.-> O
    O --> M[Prometheus]
    M --> F[Grafana]
```

The webhook uses a configured origin and project ID. The diff and scanner summary have no authority to issue tool calls. The local review endpoint accepts scanner summaries from trusted callers. GitLab delivery deduplication, durable queueing, scanner artifact ingestion, and revision-aware posting are required before production use.

The gateway liveness probe measures the API process. The optional GPU service has its own model readiness probe. Pin image digests and set workload-specific timeouts for a real deployment.
