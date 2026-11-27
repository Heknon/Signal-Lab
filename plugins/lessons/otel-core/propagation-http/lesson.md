---
title: Propagating context over HTTP
summary: See how a trace breaks at a process boundary, then fix it with the traceparent header.
kind: code
minutes: 7
concepts: [context propagation, traceparent, W3C Trace Context]
assumes: [Nested spans, Span kind]
runtime:
  service: price-checker
checks:
  - id: client
    type: span
    title: A `client` span `GET` for the outgoing request
    where: {name: GET, kind: client}
  - id: one-trace
    type: trace
    title: "`storefront` continues the same trace"
    services: {min: 2}
    includes_services: [storefront]
hints:
  - "`from opentelemetry import propagate`, then `propagate.inject(headers)` inside the client span."
  - "Pass the filled `headers` dict to `urllib.request.Request(url, headers=headers)`."
---

A trace id lives in memory, in the current **context**. When your code calls
another service, that context has to travel *with the request*, or the
other side starts a brand-new trace and the story falls apart.

OpenTelemetry uses the W3C **Trace Context** standard, an HTTP header:

```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             ver  trace-id (16 bytes)              parent span id   flags (sampled)
```

Instrumented clients like `requests` add this header automatically. Python's
built-in `urllib` isn't instrumented here, which makes it a good way to see
the mechanism. A **propagator** writes the current context into any
dict-like **carrier**:

```python
from opentelemetry import propagate

headers = {}
propagate.inject(headers)   # → {"traceparent": "00-…-…-01"}
```

On the receiving side, the server's instrumentation calls
`propagate.extract(request.headers)` and parents its span to yours.

## Try it

Run the starter first. You'll get **two traces**: yours, and one started by
`storefront`. Then inject the context into the request headers and run again:
one trace, two services.

> [!NOTE]
> Which headers are used is configurable with `OTEL_PROPAGATORS`. The default
> is `tracecontext,baggage`; `b3` and Jaeger formats exist for older systems.
