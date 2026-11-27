---
title: Sampling
summary: Keep a representative fraction of traces, and keep whole traces, not fragments.
kind: code
minutes: 8
concepts: [head sampling, TraceIdRatioBased, ParentBased, tail sampling]
assumes: [Setting up the SDK yourself]
runtime:
  service: search-api
  auto_instrument: false
checks:
  - id: sampled
    type: span
    title: Roughly 1 in 5 of the 200 requests are kept (15 to 70 traces)
    where: {name: handle-search, parent: root}
    count: {min: 15, max: 70}
  - id: whole
    type: span
    title: Kept traces are whole; children follow their parent's decision
    where: {name: query-index, parent: handle-search}
    count: {min: 15, max: 70}
hints:
  - "`TracerProvider(resource=..., sampler=ParentBased(TraceIdRatioBased(0.2)))`"
  - "`ParentBased` makes child spans follow the root's decision instead of re-rolling the dice."
---

At high traffic, keeping every trace is expensive and rarely useful. A
**sampler** decides, when a span starts, whether it's recorded and exported.

```python
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

provider = TracerProvider(sampler=ParentBased(TraceIdRatioBased(0.2)))
```

- **TraceIdRatioBased(0.2)** keeps about 20% of traces, decided from the
  trace id. Every service that sees the same trace id makes the *same* decision.
- **ParentBased(...)** says: if there's a parent, do what it did. Use the
  ratio only for root spans. Without it you'd get traces with holes.
- The decision travels downstream in the `traceparent` flags (`…-01` = sampled).

This is **head sampling**: decided up front, before anyone knows whether the
request will be slow or fail. To keep *all* errors and slow traces, you need
**tail sampling**, done in the Collector after the whole trace has arrived
(the `tail_sampling` processor).

> [!NOTE]
> With `opentelemetry-instrument` you'd set the same thing with
> `OTEL_TRACES_SAMPLER=parentbased_traceidratio` and `OTEL_TRACES_SAMPLER_ARG=0.2`.

## Try it

The service handles 200 searches and exports every one of them. Add a sampler
that keeps about 20% of traces, whole.
