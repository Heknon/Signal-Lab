---
title: Exemplars
summary: Link a point on a latency histogram to a real trace, so a spike leads straight to an example request.
kind: code
minutes: 7
concepts: [exemplars, metric-to-trace correlation]
assumes: [Histograms, Creating a span]
runtime: {service: search-api}
checks:
- id: hist
  type: metric
  title: '`search.duration` is a histogram in seconds'
  name: search.duration
  instrument: histogram
  unit: s
  max: {lte: 5}
  max_hint: 'With unit `s`, record seconds: `time.perf_counter()` differences already are.'
- {id: exemplars, type: metric, title: Its data points carry exemplars that point at traces, name: search.duration, exemplars: true}
- id: spans
  type: span
  title: Each search is a `search` span
  where: {name: search}
  count: {min: 20}
hints: ['Record the measurement *while the span is active*: move `duration.record(...)` inside the `with` block.']
---

A histogram tells you p99 latency jumped at 14:02. It can't tell you *which*
request was slow. A trace can, but which one, out of millions?

An **exemplar** is a sample measurement stored alongside a metric data
point, together with the trace and span id that were active when it was
recorded. Dashboards show exemplars as dots on the latency graph: click the
slow one and you're in its trace.

The Python SDK attaches exemplars automatically when a measurement is
recorded **inside a sampled span** (`OTEL_METRICS_EXEMPLAR_FILTER=trace_based`,
the default):

```python
with tracer.start_as_current_span("search"):
    ...
    duration.record(elapsed)      # inside the span → exemplar with its trace_id
duration.record(elapsed)          # outside → just a number
```

## Try it

The starter records each duration *after* its span has ended, so there's no
trace to point to. Move the measurement inside the span and run again. In
the Metrics tab, the card's **exemplar → trace** link jumps to the slowest
request's waterfall.

> [!NOTE]
> Backend support varies. Prometheus and Grafana display exemplars;
> VictoriaMetrics accepts them but doesn't store them. Here, the lab's
> inspector shows what the SDK actually exported.
