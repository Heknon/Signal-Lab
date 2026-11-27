---
title: Metrics from spans
summary: Use the spanmetrics connector to turn traces into request-rate, error and duration metrics.
kind: collector
filename: collector.yaml
minutes: 9
concepts: [connectors, spanmetrics, RED metrics]
assumes: [Collector pipelines, Histograms]
runtime:
  service: catalog
collector:
  settle_s: 3
checks:
  - id: calls
    type: metric
    title: "A `traces.span.metrics.calls` counter, split by `span.name`"
    name: traces.span.metrics.calls
    instrument: counter
    attributes: [span.name, status.code]
  - id: duration
    type: metric
    title: "A `traces.span.metrics.duration` histogram"
    name: traces.span.metrics.duration
    instrument: histogram
  - id: traces-too
    type: span
    title: The spans themselves still reach the inspector
    where: {name: "~^GET "}
    count: {min: 10}
hints:
  - "A connector is listed as an *exporter* in one pipeline and a *receiver* in another."
  - "traces pipeline: `exporters: [otlphttp/lab, spanmetrics]`; a new metrics pipeline: `receivers: [spanmetrics]`, `exporters: [otlphttp/lab]`."
  - "Set `metrics_flush_interval: 1s` on the connector, or the run ends before it emits anything."
---

Every server span already holds what the **RED** method needs: a request
(**R**ate), its status (**E**rrors) and how long it took (**D**uration).
The **spanmetrics connector** counts and measures spans as they pass
through, and emits metrics.

A **connector** joins two pipelines. It's an exporter at the end of one and a
receiver at the start of another:

```yaml
connectors:
  spanmetrics:
    metrics_flush_interval: 1s
    histogram:
      explicit:
        buckets: [10ms, 50ms, 100ms, 250ms, 500ms, 1s]

service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [otlphttp/lab, spanmetrics]   # out of the traces pipeline…
    metrics/red:
      receivers: [spanmetrics]                 # …into a metrics pipeline
      exporters: [otlphttp/lab]
```

The metrics are split by `service.name`, `span.name`, `span.kind` and
`status.code`, plus any `dimensions` you add. The connector emits on an
interval (`metrics_flush_interval`, 60 s by default). This short-lived lab
needs `1s`.

> [!TIP]
> Derive metrics *before* sampling. If tail sampling drops 90% of traces
> first, your request rate is 90% too low.

## Try it

Add the connector and a second pipeline. The Metrics tab shows a counter and
a histogram that the Collector produced; your code never recorded them.
