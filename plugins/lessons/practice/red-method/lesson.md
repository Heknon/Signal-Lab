---
title: The RED method
summary: 'Rate, Errors and Duration for one service in one query: the three numbers that describe any request-driven service.'
kind: query
minutes: 10
concepts: [RED method, request rate, error ratio, latency percentile, label_set, union]
assumes: [rate() on counters, sum by, histogram_quantile, Error ratios]
tools: ['victoriametrics:explore']
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
  - {label: 'Rate: requests per second', query: 'sum(rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m]))'}
  - {label: 'Errors: 5xx share', query: 'sum(rate(http_server_request_duration_seconds_count{service_name="checkout", http_response_status_code=~"5.."}[5m]))
      / sum(rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m]))'}
  - {label: 'Duration: p95', query: 'histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="checkout"}[5m])))'}
  - {label: RED per route, query: 'sum by (http_route) (rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m]))'}
checks:
- id: shape
  type: query
  title: Three rows, `rate`, `errors` and `duration_p95`, built from rates and a histogram
  must_include: [rate(, 5.., histogram_quantile, _bucket]
  expect:
    rows: {min: 2, max: 3}
    columns: [signal, value]
  mistakes:
  - {pattern: 'status_code\s*=~?\s*"(2\.\.|[23]\d\d|\(2)', message: 'Divide the errors by all requests, not only the successful
      ones: errors / (errors + successes) is the error ratio.'}
  - {pattern: '(max|min|avg|sum|quantile)\s*(by\s*\([^)]*\)\s*)?\(\s*histogram_quantile', message: 'Aggregate the buckets
      first (`sum by (le, …)`), then take `histogram_quantile`. Percentiles can''t be combined with max, avg or sum afterwards.'}
- id: answer
  type: query
  title: 'RED for `checkout`: requests/s, 5xx ratio and p95 latency'
  reference: |-
    union(
      label_set(sum(rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m])), "signal", "rate"),
      label_set(sum(rate(http_server_request_duration_seconds_count{service_name="checkout", http_response_status_code=~"5.."}[5m])) / sum(rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m])), "signal", "errors"),
      label_set(histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="checkout"}[5m]))), "signal", "duration_p95")
    )
  tolerance: 0.05
  hint: Rate needs `rate(...[5m])`; errors are 5xx divided by all requests; duration is `histogram_quantile(0.95, ...)` over
    `_bucket`, not the average.
  success: 'That''s checkout''s RED: a few requests per second, a couple of percent failing, and a p95 of a couple of hundred milliseconds (checkout waits for inventory and payments).'
hints: ['Rate: the raw `_count` is a counter since start-up. Wrap it in `rate(...[5m])`.', 'Errors: divide the 5xx rate by
    the rate of all requests, so it''s a ratio between 0 and 1.', 'Duration: replace the average with `histogram_quantile(0.95,
    sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="checkout"}[5m])))`.']
---

For any service that handles requests, three numbers tell you most of what
matters to its users. Tom Wilkie named them the **RED method**:

| | Question | From the HTTP server histogram |
| --- | --- | --- |
| **Rate** | How much traffic? | `rate(…_count[5m])` |
| **Errors** | How much of it fails? | 5xx rate ÷ total rate |
| **Duration** | How long does it take? | `histogram_quantile` over `rate(…_bucket[5m])` |

All three come from one instrument the Signal Shop already has,
`http.server.request.duration`, which HTTP auto-instrumentation records for
every request. That's typical: RED needs no custom code, so it's the same
for every service, and one dashboard template covers them all.

## Why these three

They describe the service **as its callers see it**. A caller doesn't care
about the CPU or the pool size; it cares whether its request was answered,
correctly, quickly. Each one also catches a different failure:

- Rate drops when upstream breaks or traffic is being routed elsewhere.
- Errors rise when a dependency fails or a deploy is bad.
- Duration rises when something is saturated or slow.

Use **percentiles** for duration, not the average. An average hides the
slow tail: 95 fast requests and 5 that take 3 s average out to a number
that looks fine and that no real request experienced.

> [!TIP]
> RED is for request-driven services. For resources such as CPU, disks,
> pools and queues, the USE method in the next lesson fits better.

## Try it

The editor holds one query that returns three rows, one per signal, using
`label_set` to name each and `union` to combine them. Each part has a
mistake:

1. `rate` reads the raw counter, which only says how many requests there
   have been since start-up.
2. `errors` is a rate of errors, which depends on traffic. Make it a ratio.
3. `duration_p95` is an average. Make it the 95th percentile.

Fix all three for the `checkout` service.
