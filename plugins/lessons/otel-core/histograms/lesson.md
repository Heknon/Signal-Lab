---
title: Histograms
summary: Record durations and sizes as distributions, and choose buckets that answer your questions.
kind: code
minutes: 8
concepts: [histogram, buckets, percentiles]
assumes: [Counters]
runtime:
  service: order-service
checks:
  - id: hist
    type: metric
    title: "`order.processing.duration` is a histogram in seconds"
    name: order.processing.duration
    instrument: histogram
    unit: s
  - id: buckets
    type: metric
    title: It uses buckets that fit this workload
    name: order.processing.duration
    bounds: [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1]
  - id: count
    type: metric
    title: All 200 orders are recorded
    name: order.processing.duration
    value: 200
hints:
  - "`meter.create_histogram(name, unit=\"s\", explicit_bucket_boundaries_advisory=[...])`."
  - "Record seconds, not milliseconds: `duration.record(elapsed)`."
---

"Average latency" hides the slow requests that users actually complain about.
A **histogram** keeps the *distribution*: for each **bucket** boundary, how
many measurements fell at or below it, plus the total `count` and `sum`.

```python
duration = meter.create_histogram(
    "order.processing.duration",
    unit="s",
    explicit_bucket_boundaries_advisory=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
)
duration.record(0.042)
```

From buckets, a backend can estimate percentiles like p95 with
`histogram_quantile()`. The estimate is only as good as your buckets:

- The SDK's default boundaries (0, 5, 10, 25, 50 … 10 000) are designed for
  **milliseconds**. Record seconds with defaults and *everything* lands in the
  first bucket.
- Put boundaries **around your thresholds**. If your target is "under 250 ms",
  have a bucket at `0.25`.

> [!TIP]
> Durations should be in **seconds** (`s`), per the semantic conventions.
> The HTTP instrumentation uses the same boundaries this lesson asks for.

## Try it

The starter records milliseconds into a histogram with default buckets. Switch
to seconds and set buckets that suit a workload of 10 to 600 ms. Compare the
bucket chart in the Metrics tab before and after.
