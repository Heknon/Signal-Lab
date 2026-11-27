---
title: Reshaping data with OTTL
summary: Fix old attribute names, strip query strings, and stamp a resource attribute, all in the Collector.
kind: collector
filename: collector.yaml
minutes: 9
concepts: [transform processor, OTTL, semantic conventions]
assumes: [Collector pipelines, Semantic conventions]
runtime:
  service: legacy-api
collector:
  settle_s: 2
checks:
  - id: path
    type: span
    title: "Spans have `url.path` without the query string"
    where: {name: GET, attributes: {url.path: "~^/api/[a-z]+$"}}
    count: {min: 10}
  - id: old-gone
    type: span
    title: "The old `http.target` attribute is gone"
    where: {attributes: {http.target: "*"}}
    count: {max: 0}
  - id: namespace
    type: span
    title: "Every span's resource has `service.namespace = shop`"
    where: {name: GET, resource: {service.namespace: shop}}
    count: {min: 10}
hints:
  - "In `trace_statements`, use `context: span` for span attributes and `context: resource` for the resource."
  - "`replace_pattern(attributes[\"url.path\"], \"\\\\?.*\", \"\")` removes everything from `?` onwards."
  - "Copy first: `set(attributes[\"url.path\"], attributes[\"http.target\"])`, then `delete_key(attributes, \"http.target\")`."
---

An old service emits `http.target` (the pre-1.0 HTTP convention) with the
full query string, so `/api/items?id=42&session=…` produces a different value
for every request. You can't redeploy it this week, but you can fix its
telemetry on the way through.

The **transform** processor runs OTTL *statements*, not just conditions:

```yaml
processors:
  transform/legacy:
    error_mode: ignore
    trace_statements:
      - context: span
        statements:
          - set(attributes["url.path"], attributes["http.target"]) where attributes["http.target"] != nil
          - replace_pattern(attributes["url.path"], "\\?.*", "")
          - delete_key(attributes, "http.target")
      - context: resource
        statements:
          - set(attributes["service.namespace"], "shop")
```

Statements run in order, and the `where` clause guards each one. Contexts let
you edit the span, its resource, its scope, or its events.

## Try it

Rename `http.target` to `url.path`, drop the query string, and add
`service.namespace = shop` to the resource.
