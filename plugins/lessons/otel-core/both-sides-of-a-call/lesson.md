---
title: Both sides of a call
summary: Instrument the price API as its own service and carry the trace across the call, so its box on the map becomes real.
kind: code
minutes: 8
concepts: [server span, service.name, resource, TracerProvider, context propagation, service map]
assumes: [Publishing to a queue]
runtime:
  service: price-fetcher
checks:
  - id: solid
    type: map
    title: "`price-api` is an instrumented service: a solid arrow, called twice"
    edge: {from: price-fetcher, to: price-api, external: false, calls: 2}
  - id: server
    type: span
    title: "Each request is handled by a `server` span in `price-api`, under the caller's `GET`"
    where: {kind: server, service: price-api, parent: GET}
    count: {min: 2}
  - id: one-trace
    type: trace
    title: "One trace runs from `price-fetcher` into `price-api`"
    includes_services: [price-fetcher, price-api]
  - id: fx-still-external
    type: map
    title: "`fx-rates` stays an external dependency"
    edge: {from: price-fetcher, to: fx-rates, external: true}
hints:
  - "Client side: `propagate.inject(headers)` inside the `GET` span adds a `traceparent` header."
  - "Server side: `ctx = propagate.extract(headers)`, then `api_tracer.start_as_current_span(..., context=ctx, kind=SpanKind.SERVER)`."
  - "Use `api_tracer`, not `tracer`: a span's service comes from the provider that made it."
---

So far `price-api` is a dashed box: you know it exists only because your
client spans say so. In this lesson it becomes a service in its own right,
with its own spans, and the arrow turns solid.

Two things make a callee show up as a real service:

1. **Its spans come from its own provider.** A span's service is the
   `service.name` on the resource of the `TracerProvider` that created it, not
   the tracer's name or the span's kind. A server span made with `tracer`
   would belong to `price-fetcher`, and a service calling itself isn't a
   dependency. The starter already creates `api_provider` for `price-api`;
   in production the API is another process and gets this from
   `OTEL_SERVICE_NAME`.
2. **The trace crosses the call.** The client writes its context into the
   request headers, and the server reads it back. Without that, the server
   starts a new trace and nothing connects its span to your client span.

```python
# caller, inside its client span
headers = {}
propagate.inject(headers)          # {"traceparent": "00-<trace id>-<span id>-01"}

# callee
ctx = propagate.extract(headers)
with api_tracer.start_as_current_span("GET /v1/quotes", context=ctx, kind=SpanKind.SERVER):
    ...
```

A map pairs the two: a `client` span in one service with a `server` span,
in another service, whose parent it is. That pair is the solid arrow, and
the gap between their durations is the time spent between the services.

`peer.service` can stay on the client span. Now that `price-api` names
itself, the map uses the server side, and the two names agree.

## Try it

1. Run the starter: the map has a dashed `price-api`.
2. **TODO 1:** inject the trace context in `http_get`.
3. **TODO 2:** wrap the work in `price_api` in a `server` span from
   `api_tracer`, continuing the extracted context.
4. Run again: `price-fetcher → price-api` is solid, and each `GET` in Traces
   has a `GET /v1/quotes` from `price-api` inside it. `fx-rates` stays dashed:
   it's a third party.
5. Now break it on purpose: comment out `propagate.inject(headers)` and run.
   `price-api` still has spans, but each one starts its own trace, so the map
   can't pair them with your calls. That broken trace is what the next module,
   context propagation, is about.
