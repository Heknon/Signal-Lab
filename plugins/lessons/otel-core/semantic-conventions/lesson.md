---
title: Semantic conventions
summary: Name things the way every backend already understands.
kind: code
minutes: 6
concepts: [semantic conventions, span kind, resource]
assumes: [Span attributes]
runtime:
  service: price-fetcher
checks:
  - id: kind
    type: span
    title: "The outgoing call is a `client` span named `GET`"
    where: {name: GET, kind: client}
  - id: semconv
    type: span
    title: It uses the standard HTTP attribute names
    where:
      name: GET
      attributes: {http.request.method: GET, url.full: "*", server.address: "*", http.response.status_code: 200}
  - id: no-custom
    type: span
    title: No home-made duplicates (`method`, `url`, `status`)
    where: {name: GET, attributes_absent: [method, url, status]}
hints:
  - "Pass `kind=SpanKind.CLIENT` to `start_as_current_span`."
  - "The keys are `http.request.method`, `url.full`, `server.address` and `http.response.status_code`."
---

You could call an attribute `method`, `http_method` or `verb`. If every team
picks differently, no dashboard, alert or backend feature can rely on any of
them. **Semantic conventions** are OpenTelemetry's shared vocabulary for
common operations: HTTP, databases, messaging, RPC, cloud resources and more.
They cover two things: the span's **kind**, and the **names** of its attributes.

## Span kind

Every span has a kind: the role this piece of work plays in a conversation
between processes. You set it when the span starts, and it can't be changed later.

| Kind | The span is… | Example |
|---|---|---|
| `server` | handling a request that came in | the shop's checkout handling `POST /checkout` |
| `client` | making a request to something else, and waiting for the answer | checkout calling payments; inventory's database query |
| `producer` | sending a message without waiting for it to be handled | `orders publish` in the messaging lesson |
| `consumer` | handling a message someone sent earlier | `orders process` in the same lesson |
| `internal` | work inside one process, no one else involved | computing a cart total |

`internal` is the default: if you don't pass a kind, that's what you get. That
was fine for every span so far, because none of them talked to another process.

Kind matters because one remote call produces **two spans**: a `client` span in
the caller and a `server` span in the callee, with the same trace id. Backends
use the pair:

- **Service maps** draw an edge for each `client` → `server` pair. The **Map**
  tab next to Traces draws one from your run, the same way.
- **Network time** is the gap between them: the client span lasts as long as the
  caller waited, the server span only as long as the callee worked. A slow
  client span around a fast server span points at the network, DNS, a proxy or a
  queue, not at the service.
- **Calls to things that aren't instrumented** (a third-party API, a managed
  database) exist only as `client` spans. Backends group them by
  `server.address` and show them as external dependencies; with kind `internal`
  they disappear from those views.

Set it as an argument when you start the span:

```python
from opentelemetry.trace import SpanKind

with tracer.start_as_current_span("GET", kind=SpanKind.CLIENT) as span:
    ...
```

## Attribute names

For an outgoing HTTP request, the conventions say:

| What | Convention |
|---|---|
| Span name | `GET`, `POST`… (or `GET /users/{id}` when a route template is known) |
| Span kind | `client` (the side handling the request is `server`) |
| Method | `http.request.method` |
| Target | `url.full`, `server.address`, `server.port` |
| Result | `http.response.status_code` |

The span name stays short and low-cardinality: the method, not the full URL.
The URL goes in `url.full`, where it can be searched without turning every
query string into a separate operation.

> [!NOTE]
> Resource attributes such as `service.name` follow conventions too. The lab
> sets them through `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`; see
> the Environment tab.

## Try it

This code fakes an HTTP call with home-made attribute names. Make it a
`client` span named `GET` that follows the HTTP conventions.

Run the starter first and open the **Map** tab: `price-fetcher` stands alone,
because an `internal` span doesn't say it called anything. Run your fix and
the map gains an arrow to `api.prices.example`, drawn dashed because that API
isn't instrumented: it's known only from your client span's `server.address`.

In real code you rarely write this by hand: the `requests` and `httpx`
instrumentations create these client spans for you, as the auto-instrumentation
lesson shows.
