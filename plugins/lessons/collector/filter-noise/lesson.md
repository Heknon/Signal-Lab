---
title: Dropping noise with the filter processor
summary: Stop health checks from reaching any backend, without touching the service.
kind: collector
filename: collector.yaml
minutes: 7
concepts: [filter processor, OTTL conditions]
assumes: [Collector pipelines]
runtime: {service: web-api}
collector: {settle_s: 2}
checks:
- id: dropped
  type: span
  title: No `GET /healthz` spans get through
  where: {name: GET /healthz}
  count: {max: 0}
- id: kept
  type: span
  title: The 25 real requests still arrive
  where: {name: ~^(GET /api/items|POST /api/orders)$}
  count: {min: 25}
hints: ['Add a processor named `filter/healthz` with `traces: span: [...]` conditions, and list it in the pipeline.', 'The
    condition is OTTL: `attributes["http.route"] == "/healthz"`.']
---

Load balancers and Kubernetes probe `/healthz` every few seconds. Those
requests are real spans, and they can outnumber user traffic many times over:
they cost storage and bury the requests you care about.

You could change every service, or drop them in one place: the Collector.

```yaml
processors:
  filter/healthz:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.route"] == "/healthz"'
```

Each condition is written in **OTTL**, the OpenTelemetry Transformation
Language. A span matching *any* condition is dropped. Defining a processor
does nothing on its own: it has to be listed in a pipeline.

## Try it

`traffic.py` sends 25 API requests and 30 health checks to your Collector.
The starter config forwards everything. Add the filter and run. The Traces tab
shows only what made it out of the Collector.

> [!TIP]
> If the config is invalid, the Console shows the Collector's own error message
> before anything runs, the same one you'd see when deploying it.
