---
title: Metric views
summary: Reshape metrics in the SDK by dropping attributes and changing buckets, without touching the code that records them.
kind: code
minutes: 8
concepts: [View, MeterProvider, aggregation]
assumes: [Histograms, Cardinality]
runtime:
  service: api-gateway
  auto_instrument: false
checks:
  - id: dropped
    type: metric
    title: "`http.server.requests` keeps only `http.route`"
    name: http.server.requests
    attributes: [http.route]
    attributes_absent: [user.id, http.user_agent]
  - id: series
    type: metric
    title: That leaves at most 3 series
    name: http.server.requests
    series: {max: 3}
  - id: buckets
    type: metric
    title: "`http.server.latency` uses buckets [0.05, 0.1, 0.25, 0.5, 1]"
    name: http.server.latency
    bounds: [0.05, 0.1, 0.25, 0.5, 1]
hints:
  - "`View(instrument_name=\"http.server.requests\", attribute_keys={\"http.route\"})`"
  - "`View(instrument_name=\"http.server.latency\", aggregation=ExplicitBucketHistogramAggregation([0.05, 0.1, 0.25, 0.5, 1]))`"
  - "Pass both in `MeterProvider(metric_readers=[reader], resource=..., views=[...])`."
---

Sometimes the code recording a metric isn't yours (a library, or
auto-instrumentation), and it records attributes you don't want, or buckets
that don't fit. A **View** rewrites a metric stream inside the SDK, before
export:

```python
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation

views = [
    View(instrument_name="http.server.requests", attribute_keys={"http.route"}),     # allow-list attributes
    View(instrument_name="http.server.latency",
         aggregation=ExplicitBucketHistogramAggregation([0.05, 0.1, 0.25, 0.5, 1])),  # new buckets
]
provider = MeterProvider(metric_readers=[reader], views=views)
```

Views can also rename a metric (`name=`), drop it entirely
(`aggregation=DropAggregation()`), or match many instruments with wildcards.

> [!TIP]
> The Collector can do similar things (`attributes`, `transform`, `filter`
> processors). Fixing it in the SDK is cheaper: the data is never produced.

## Try it

The "library" code below records a user id and a user agent on every request,
which is a cardinality problem you can't fix at the call site. Add views to
keep only `http.route`, and give the latency histogram sensible buckets.
