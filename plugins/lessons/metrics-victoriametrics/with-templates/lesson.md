---
title: WITH templates
summary: Use MetricsQL's WITH expressions to write a ratio once instead of repeating it, on the shop's order-value histogram.
kind: query
minutes: 6
concepts: [MetricsQL, WITH templates, average from histogram, histogram_share]
assumes: [rate() on counters, sum by, ratios]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
  - {label: Shared label filter, query: 'WITH (f = {service_name="checkout"}) sum(rate(http_server_request_duration_seconds_count{f}[5m]))'}
  - {label: Share of requests under 100 ms, query: 'histogram_share(0.1, sum by (le, service_name) (rate(http_server_request_duration_seconds_bucket[5m])))'}
  - {label: Order value p90, query: 'histogram_quantile(0.9, sum by (le) (rate(shop_order_value_USD_bucket[5m])))'}
checks:
- id: uses-with
  type: query
  title: Use a `WITH` template
  must_include: [WITH (, rate(]
  expect:
    rows: {min: 1}
    columns: [app_user_tier, value]
  success: Defined once, used twice.
- {id: answer, type: query, title: Average order value per user tier, reference: 'sum by (app_user_tier) (rate(shop_order_value_USD_sum[5m]))
    / sum by (app_user_tier) (rate(shop_order_value_USD_count[5m]))', tolerance: 0.05, hint: 'Average = rate of `_sum` divided
    by rate of `_count`, both `sum by (app_user_tier)` over `[5m]`.', success: 'Dollars per order, per tier. Gold members
    get 10% off, but it''s a small sample, so don''t read too much into the gap.'}
hints: ['A function template: `WITH (r(m) = sum by (app_user_tier) (rate(m[5m]))) r(a) / r(b)`.', 'Answer: `WITH (r(m) = sum
    by (app_user_tier) (rate(m[5m]))) r(shop_order_value_USD_sum) / r(shop_order_value_USD_count)`']
---

Ratios repeat themselves: the same `sum by (...) (rate(...[5m]))` wrapper
appears on both sides of the `/`. Change the window on one side, forget the
other, and the numbers quietly go wrong.

MetricsQL (the VictoriaMetrics dialect, a superset of PromQL) lets you name
pieces of a query with **`WITH`**:

```promql
WITH (
  r(m) = sum by (app_user_tier) (rate(m[5m]))
)
r(shop_order_value_USD_sum) / r(shop_order_value_USD_count)
```

Templates can be plain expressions, functions with arguments, or label
filters you reuse:

```promql
WITH (lab = {deployment_environment_name="lab"})
sum(rate(http_server_request_duration_seconds_count{lab}[5m]))
```

VictoriaMetrics expands the templates before running the query, so the
result is identical to writing it out by hand.

## Averages from a histogram

Every histogram carries `_sum` and `_count`. Dividing their rates gives the
**average** of the observed values. For `shop_order_value_USD`, recorded by
the checkout service for each placed order, that's the average order value.

> [!WARNING]
> `WITH`, `histogram_share`, `topk_avg` and friends are MetricsQL only. A
> plain Prometheus server, or an alert rule evaluated by one, rejects them.

## Try it

Return the **average order value per `app_user_tier`** over the last 5
minutes, using a `WITH` template.
