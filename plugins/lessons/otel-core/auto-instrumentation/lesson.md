---
title: Auto-instrumentation
summary: Get spans for HTTP calls, frameworks and databases without writing them, then add your own on top.
kind: code
minutes: 6
concepts: [auto-instrumentation, client spans, distributed trace]
assumes: [Nested spans]
runtime:
  service: catalog-browser
checks:
  - id: root
    type: span
    title: A root span `browse-catalog`
    where: {name: browse-catalog, parent: root}
  - id: client
    type: span
    title: The `requests` call appears as a `client` span inside it
    where: {kind: client, parent: browse-catalog, attributes: {http.request.method: GET}}
  - id: distributed
    type: trace
    title: The trace continues into the shop's `storefront` and `inventory` services
    services: {min: 3}
    includes_services: [storefront, inventory]
hints:
  - "You don't need to create the HTTP span yourself: `requests` is instrumented already."
  - "Wrap the call in `with tracer.start_as_current_span(\"browse-catalog\"):`."
---

`opentelemetry-instrument` doesn't only configure the SDK. It also finds
installed libraries and patches them: `requests`, `httpx`, FastAPI, Flask,
Django, database drivers and dozens more. Each call then produces spans that
already follow the semantic conventions, *and* propagates trace context to
the next service.

The **Signal Shop** scenario runs in this lab: a storefront, checkout,
inventory and payments service, all auto-instrumented. Its URL is in
`SHOP_URL`.

```python
import requests
requests.get(os.environ["SHOP_URL"] + "/api/products")   # ← a client span, for free
```

Auto-instrumentation covers the *plumbing*. Your **business** steps
(*browse the catalog*, *apply the discount*) still need manual spans. The
two mix naturally: a manual span becomes the parent of the automatic ones.

## Try it

Wrap the request in a `browse-catalog` span. Run it and look at the
waterfall: your span, the `GET` client span, then `storefront`'s server
span and the call it makes to `inventory`, all in **one trace**, across
three services.

> [!TIP]
> Open the trace in Kibana or Jaeger with the links in the span detail panel.
> The service map now includes your `catalog-browser` service.
