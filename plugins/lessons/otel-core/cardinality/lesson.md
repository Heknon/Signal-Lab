---
title: Cardinality
summary: Why one innocent attribute can create thousands of time series, and how to fix it.
kind: code
minutes: 7
concepts: [cardinality, time series, attributes]
assumes: [Counters]
runtime:
  service: api-gateway
checks:
  - id: no-user
    type: metric
    title: "`api.requests` no longer has a `user.id` attribute"
    name: api.requests
    attributes_absent: [user.id]
    absent_hint: User ids belong on spans and logs, not on metrics.
  - id: tier
    type: metric
    title: It's split by `app.user.tier` instead
    name: api.requests
    attributes: [app.user.tier]
  - id: series
    type: metric
    title: At most 6 time series
    name: api.requests
    series: {max: 6}
    series_hint: Every unique combination of attribute values is a separate series.
hints:
  - "Keep `http.route` and add `app.user.tier`; drop `user.id`."
---

Each unique combination of attribute values on a metric is a separate **time
series** that the backend must index and store, *forever*. That number is the
metric's **cardinality**:

```text
api.requests{http.route, user.id}
  2 routes × 500 users = 1 000 series      ← and growing with every new user
api.requests{http.route, app.user.tier}
  2 routes × 3 tiers  =     6 series       ← bounded
```

High-cardinality attributes (user ids, order ids, request ids, full URLs,
timestamps) are fine on **spans and logs**, where every record is
individual anyway. On metrics, they slow queries and multiply storage costs.
Many backends start dropping data at some limit.

> [!TIP]
> Resource attributes count too: `service.instance.id` changes on every
> restart, so each deploy creates new series. That's usually acceptable,
> but it's worth knowing.

## Try it

Run the starter and look at the Metrics tab: hundreds of series, and a
warning. Replace `user.id` with the user's tier and run again.
