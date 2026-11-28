---
title: Latency percentiles
summary: Estimate p95 latency per service from histogram buckets with histogram_quantile.
kind: query
minutes: 7
concepts: [histogram, buckets, le, histogram_quantile, percentile]
assumes: [rate() on counters, sum by]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
  - {label: Bucket rates for storefront, query: 'sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="storefront"}[5m]))'}
  - {label: Median for the whole shop, query: 'histogram_quantile(0.5, sum by (le) (rate(http_server_request_duration_seconds_bucket[5m])))'}
  - {label: Average (not a percentile), query: 'sum by (service_name) (rate(http_server_request_duration_seconds_sum[5m]))
      / sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))'}
checks:
- id: shape
  type: query
  title: Use `histogram_quantile` over `rate(..._bucket)` and keep `le`
  must_include: [histogram_quantile, _bucket, le]
  expect:
    rows: {min: 2}
    columns: [service_name, value]
  success: Right shape.
  must_match:
  - {pattern: \b(rate|increase)\(, message: 'Turn the cumulative buckets into a recent window with `rate(...[5m])` (or `increase`).'}
  mistakes:
  - {pattern: '(max|min|avg|sum|quantile)\s*(by\s*\([^)]*\)\s*)?\(\s*histogram_quantile', message: 'Aggregate the buckets
      first (`sum by (le, …)`), then take `histogram_quantile`. Percentiles can''t be combined with max, avg or sum afterwards.'}
- {id: answer, type: query, title: p95 server latency for each service, reference: 'histogram_quantile(0.95, sum by (le, service_name)
    (rate(http_server_request_duration_seconds_bucket[5m])))', tolerance: 0.05, hint: 'Use 0.95, and aggregate the bucket
    rates with `sum by (le, service_name)` inside `histogram_quantile`.', success: That's p95 in seconds. 95% of requests
    to each service were faster than this.}
hints: ['Percentiles are `0.0`-`1.0` here: p95 is `0.95`.', 'The `by` clause needs `le` *and* the label you want one line
    per: `by (le, service_name)`.', 'Answer: `histogram_quantile(0.95, sum by (le, service_name) (rate(http_server_request_duration_seconds_bucket[5m])))`']
---

A histogram doesn't store individual durations. It counts how many requests
fell into each **bucket**: `le="0.05"` counts requests that took at most
50 ms, `le="0.1"` at most 100 ms, and so on up to `le="+Inf"` (all of them).
Buckets are cumulative.

`histogram_quantile` finds the bucket where, say, the 95th percentile falls,
and interpolates inside it:

```promql
histogram_quantile(0.95,
  sum by (le, service_name) (
    rate(http_server_request_duration_seconds_bucket[5m])
  )
)
```

Read it inside out:

1. `rate(..._bucket[5m])`: how fast each bucket counter grows, so you look
   at recent requests, not everything since start-up.
2. `sum by (le, service_name)`: merge routes, status codes and instances,
   but keep the buckets (`le`) apart and one set per service.
3. `histogram_quantile(0.95, ...)`: estimate the p95 from those buckets.

> [!WARNING]
> Drop `le` from the `by` clause and every bucket is added into one number:
> the query still runs, but the answer is meaningless.

> [!NOTE]
> The result is an estimate. The SDK's default buckets for HTTP durations
> are 5, 10, 25, 50, 75, 100, 250, 500, 750 ms, then 1, 2.5, 5, 7.5, 10 s. A
> p95 of "83 ms" really means "somewhere between 75 and 100 ms, probably
> around 83".

## Try it

Return the **p95** server-side request latency **per service** over the last
5 minutes.
