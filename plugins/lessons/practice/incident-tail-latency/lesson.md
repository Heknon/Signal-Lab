---
title: The p99 nobody saw
summary: Customers say checkout sometimes hangs. The average latency graph looks fine.
kind: incident
minutes: 15
concepts:
- investigation
- metrics
assumes:
- MetricsQL basics
- RED method
tools:
- victoriametrics:dashboards
- victoriametrics:explore
incident:
  duration_s: 900
  metrics_only: true
  timeline:
  - at: 0
    load: 5
  - at: 75
    fault: true
    set:
      inventory:
        slow_sku: TEL-001
        slow_sku_ms: 1200
hints:
- Averages are flat. Look at p99 instead, per service.
- The slow service is called by checkout. Split its latency by route.
- Is every reservation slow, or only some? Compare p50 and p99.
quiz:
  questions:
  - id: start
    kind: time
    prompt: When did the problem start? (to the minute)
    tolerance_s: 120
    hint: Look for where the line first leaves its usual band, and use a 1m rate window to see it sharply.
  - id: cause
    prompt: Which service is the root cause, not just where the symptom shows?
    options:
    - id: storefront
      label: '`storefront`'
    - id: checkout
      label: '`checkout`'
    - id: inventory
      label: '`inventory`'
    - id: payments
      label: '`payments`'
    answer: inventory
    explanation: 'Right: symptoms show up upstream, but the cause is here.'
    hint: Follow the call graph down from where the symptom appears.
  - id: mechanism
    prompt: What is happening?
    options:
    - id: one-path
      label: 'One code path is slow: reserving one product, so only orders containing it are affected'
    - id: all-slow
      label: Inventory got uniformly slower
    - id: errors
      label: Inventory is failing and requests are retried
    - id: traffic
      label: There's simply more traffic
    answer: one-path
    explanation: Only reservations of one SKU are slow, so the average barely moves while p99 jumps. Averages hide tails.
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that shows *which inventory route* has the bad tail.
    must_include:
    - histogram_quantile
    expect:
      top:
        http_route: /reserve
    hint: Compute p99 per `http_route` for inventory, and keep `le` in the `sum by`.
    placeholder: histogram_quantile(0.99, sum by (le, http_route) (rate(...{service_name="inventory"}[5m])))
    explanation: That's the evidence. Put it in the incident write-up.
---

**#support, 10:42**: *"Several customers say the checkout button spins for ages, then works. Not everyone. Can someone look?"* The on-call engineer checks the average latency panel: flat.

## Your job

Find out what's wrong using **metrics only**: Grafana dashboards, Explore
and MetricsQL. Traces and logs are off-limits for this one; in real
incidents they're often missing, sampled away, or too slow to search.

1. Press **Start incident**. The shop runs normally for a while, then
   something changes. The incident runs for 15 minutes.
2. Find **when** it started, **where** the cause is, and **what** is
   happening.
3. Prove it with a query.

Hints are below if you get stuck. Each one narrows the search, so try
without them first.

> [!TIP]
> Start broad (request rate, errors, latency per service), then narrow. Ask
> "what changed?" before "what's broken?".
