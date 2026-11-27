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

For an outgoing HTTP request, the conventions say:

| What | Convention |
|---|---|
| Span name | `GET`, `POST`… (or `GET /users/{id}` when a route template is known) |
| Span kind | `client` (the server side is `server`) |
| Method | `http.request.method` |
| Target | `url.full`, `server.address`, `server.port` |
| Result | `http.response.status_code` |

Backends key features off these names. Elastic APM builds its service map
from `client` spans and `server.address`, and error rates from status codes.

**Span kind** says what role the span plays: `server` (handling a request),
`client` (making one), `producer`/`consumer` (messaging) or `internal`.

> [!NOTE]
> Resource attributes such as `service.name` follow conventions too. The lab
> sets them through `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES`; see
> the Environment tab.

## Try it

This code fakes an HTTP call with home-made attribute names. Make it a
`client` span that follows the HTTP conventions. (In real code, the
`requests` or `httpx` instrumentation does this for you, as the next lesson shows.)
