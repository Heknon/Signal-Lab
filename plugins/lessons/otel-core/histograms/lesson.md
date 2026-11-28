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
  - id: values
    type: metric
    title: The recorded values are seconds too
    name: order.processing.duration
    max: {lte: 5}
    max_hint: "With unit `s`, that's minutes per order. The unit is only a label: divide milliseconds by 1000 when you record."
  - id: buckets
    type: metric
    title: "The buckets fit this workload: the orders spread across them"
    name: order.processing.duration
    spread: {max_share: 0.5, max_overflow: 0.05, min_used: 4}
  - id: count
    type: metric
    title: All 200 orders are recorded
    name: order.processing.duration
    value: 200
hints:
  - "`meter.create_histogram(name, unit=\"s\", explicit_bucket_boundaries_advisory=[...])`."
  - "The unit doesn't convert anything: record `elapsed_ms / 1000`."
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

## Choosing buckets

A histogram only knows which bucket a value fell into, so the boundaries decide
what you can answer later. Pick them from the data you expect and the
questions you'll ask:

1. **Cover the range.** From a bit below your fastest values to a bit above your
   slow tail. Anything above the last boundary lands in one overflow bucket
   where all detail is gone, so keep that for rare outliers.
2. **Put a boundary on every threshold you care about.** If the target is
   "99% under 250 ms", you need a boundary at `0.25`, or "how many were under
   250 ms" can't be answered exactly.
3. **Be denser where most values are.** Percentiles are interpolated inside a
   bucket, so a bucket that holds half the requests makes p50 a guess. Roughly
   doubling steps (1, 2.5, 5, 10 …) give even resolution on a log scale.
4. **Don't overdo it.** Every bucket is another time series per attribute
   combination. 8–15 boundaries is typical.

For orders that take 10 to 600 ms, mostly 20–100 ms, with a 250 ms target:

```python
explicit_bucket_boundaries_advisory=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1]
#                                    fast  ─── where most are ───  target  tail
```

Other lists work too: the goal checks where your orders actually land, not
which numbers you chose.

## Why seconds?

Your timer probably gives milliseconds, and that's fine: convert when you
record. The semantic conventions use **seconds** for every duration
(`http.server.request.duration` is in `s`), so durations from different
services, libraries and languages line up, add up, and share alerts. Backends
show them as milliseconds when that reads better.

The unit is only a label. `unit="s"` doesn't convert anything, and buckets of
`0.01 … 1` only fit if the numbers you record are seconds:

```python
duration.record(elapsed_ms / 1000)   # 45 ms is recorded as 0.045
```

Record `45` under `unit="s"` and every order lands in the last bucket, as
if it took 45 seconds.

## Try it

The starter records milliseconds into a histogram with default buckets.

1. Change the unit to `s` and set buckets that suit a workload of 10 to 600 ms.
2. Convert each measurement to seconds when you record it.
3. Compare the bucket chart in the Metrics tab before and after: the orders
   should spread across the buckets, with most of them between 0.025 and 0.1.
