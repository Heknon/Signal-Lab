---
title: SLIs and SLOs
summary: Turn "the storefront is fast and available" into two ratios of good events to all events, and set targets for them.
kind: query
minutes: 10
concepts: [SLI, SLO, availability, latency SLI, histogram buckets, good events / valid events]
assumes: [rate() on counters, Histogram buckets and le, Error ratios]
tools: ['victoriametrics:explore']
query:
  backend: victoriametrics
  language: metricsql
  range_s: 3600
  examples:
  - {label: Availability SLI (storefront), query: 'sum(rate(http_server_request_duration_seconds_count{service_name="storefront",
      http_response_status_code!~"5.."}[5m])) / sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[5m]))'}
  - {label: Storefront buckets, query: 'sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="storefront"}[5m]))'}
  - {label: 'p95, for comparison', query: 'histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="storefront"}[5m])))'}
checks:
- id: shape
  type: query
  title: Divide the rate of the `le="0.25"` bucket by the rate of all requests
  must_include: [le="0.25", _bucket, rate(, /]
  expect: {rows: 1}
  must_match:
  - {pattern: _count|le\s*=\s*"\+Inf", message: 'Divide by all requests: the `_count` series (or the `le="+Inf"` bucket).'}
  - {pattern: service_name\s*=\s*"storefront", message: 'The SLO is for storefront: filter both sides on `service_name="storefront"`.'}
  - {pattern: '\[\s*5m\s*\]', message: 'The SLI is measured over the last 5 minutes: use `[5m]` on both sides.'}
  mistakes:
  - {pattern: '_bucket\{[^}]*status_code', message: 'Every request counts toward the SLI denominator and numerator alike:
      don''t drop failed ones from the fast-request count.'}
- {id: answer, type: query, title: 'Latency SLI: share of storefront requests faster than 250 ms', reference: 'sum(rate(http_server_request_duration_seconds_bucket{service_name="storefront",
    le="0.25"}[5m])) / sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[5m]))', tolerance: 0.02,
  hint: 'Select the single bucket with `le="0.25"` in the numerator, and sum over all routes on both sides so you get one
    number.', success: 'A number between 0 and 1: the fraction of requests that were fast enough. Compare it with an SLO of
    0.95.'}
hints: ['Buckets are cumulative: `le="0.25"` already counts every request that took 250 ms or less.', 'Both sides need `sum(...)`
    with no `by`, so the result is one series.', 'Answer: `sum(rate(http_server_request_duration_seconds_bucket{service_name="storefront",
    le="0.25"}[5m])) / sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[5m]))`']
---

A dashboard full of graphs doesn't tell you whether the service is doing
its job. A **service level indicator** (SLI) does, as one number:

```text
SLI = good events / valid events          # between 0 and 1
```

A **service level objective** (SLO) is the target for it over a window:
*99% of storefront requests succeed, measured over 30 days*.

Writing it as a ratio of events, rather than as "p95 under 250 ms" or
"error rate under 1%", has two advantages. It means the same thing at any
traffic level, and it turns directly into an error budget, which the next
lesson uses.

## Availability

A request is good if it didn't fail because of the server:

```promql
  sum(rate(http_server_request_duration_seconds_count{service_name="storefront", http_response_status_code!~"5.."}[5m]))
/
  sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[5m]))
```

4xx responses count as good: the server did its job, the request was
wrong. That's a decision, and it belongs in the SLO's written definition.

## Latency

A request is good if it was **fast enough**. Pick a threshold that matches a
bucket boundary, because the histogram can only count requests at its
boundaries. The default HTTP buckets include 250 ms (`le="0.25"`), and
buckets are cumulative, so that one bucket's rate is the rate of requests
that took 250 ms or less.

> [!TIP]
> "95% of requests under 250 ms" and "p95 under 250 ms" sound alike, but only
> the first is an SLI. It counts good events, so it can be summed over 30
> days and turned into a budget. A percentile can't be averaged over time.

## Choosing targets

- Start from what users notice, not from what the system does today.
- Don't aim for 100%. Every extra nine costs much more than the last, and
  the users' own networks and devices aren't that reliable anyway.
- 99% over 30 days allows 7.2 hours of complete outage. 99.9% allows 43
  minutes.

## Try it

Write the **latency SLI** for the storefront: the share of requests over
the last 5 minutes that took at most 250 ms.
