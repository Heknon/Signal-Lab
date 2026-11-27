---
title: Aggregating with sum by
summary: Collapse many series into the few you care about with sum by, and rank them with topk.
kind: query
minutes: 6
concepts: [aggregation, sum by, without, topk]
assumes: [rate() on counters]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
    - {label: Total shop traffic, query: "sum(rate(http_server_request_duration_seconds_count[5m]))"}
    - {label: Checkouts by outcome, query: "sum by (outcome) (rate(shop_checkouts_total[5m]))"}
    - {label: Two lowest-stock products, query: "bottomk(2, sum by (app_product_sku) (inventory_stock))"}
checks:
  - id: uses-sum-by
    type: query
    title: "Aggregate with `sum by (service_name)`"
    must_include: ["sum", "service_name", "rate("]
    expect: {rows: {min: 2}, columns: [service_name, value]}
    success: One row per service.
  - id: answer
    type: query
    title: Requests per second for each service
    reference: 'sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))'
    tolerance: 0.05
    hint: "Rate first, then sum: `sum by (service_name) (rate(...[5m]))`. Don't filter anything out."
    success: storefront and inventory get twice the traffic of checkout and payments. Can you see why from the routes?
hints:
  - "`sum by (label) (expr)` keeps only `label` and adds up everything else."
  - "Always `rate` before you `sum`: summing raw counters from processes that restart at different times gives garbage."
  - "Answer: `sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))`"
---

`rate(http_server_request_duration_seconds_count[5m])` returns a series for
every combination of service, route, method, status code and process. To
answer "how busy is each service?" you add those up.

```promql
sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))
```

- `sum by (a, b)` keeps only labels `a` and `b`; everything else is summed away.
- `sum without (service_instance_id)` is the opposite: drop just those labels.
- `avg`, `min`, `max`, `count` work the same way.

**Order matters:** rate first, then aggregate. `rate(sum(...))` is not
allowed in PromQL, and summing raw counters hides resets from `rate`.

## Ranking

`topk(3, expr)` and `bottomk(3, expr)` keep the 3 highest or lowest series
at each point in time:

```promql
topk(3, sum by (service_name, http_route) (rate(http_server_request_duration_seconds_count[5m])))
```

> [!TIP]
> In graphs, `topk` is evaluated at every step, so different series can
> drift in and out. MetricsQL's `topk_avg(3, ...)` ranks by the average over
> the whole range instead, which usually reads better.

## Try it

Return requests per second for **each service**, one row per
`service_name`, over a 5 minute window.
