---
title: All green, revenue down
summary: Finance reports revenue is down sharply. Every engineering dashboard is green.
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
  - at:
      min: 150
      max: 420
    fault: true
    set:
      storefront:
        empty_cart_rate: 0.5
hints:
- 'RED metrics are fine. Look at business metrics: checkouts and orders.'
- Compare 'checkouts that succeeded' with 'orders that were placed'.
- Which service decides what goes in the cart?
quiz:
  questions:
  - id: start
    kind: time
    prompt: When did the problem start? (to the minute)
    tolerance_s: 60
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
    answer: storefront
    explanation: 'Right: symptoms show up upstream, but the cause is here.'
    hint: Follow the call graph down from where the symptom appears.
  - id: mechanism
    prompt: What is happening?
    options:
    - id: empty
      label: Storefront sends empty carts to checkout, which succeeds without placing an order
    - id: traffic
      label: Fewer customers are visiting
    - id: payments
      label: Payments declines more cards
    - id: latency
      label: Customers give up because the site is slow
    answer: empty
    explanation: 'Successful checkouts didn''t drop, but orders with a value did. Nothing errored: only a business metric shows it.'
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query for the share of successful checkouts that actually produced an order.
    must_include:
    - shop_order_value
    - shop_checkouts_total
    expect:
      value:
        gt: 0.2
        lt: 0.8
    hint: Divide the rate of `shop_order_value_USD_count` by the rate of `shop_checkouts_total{outcome="ok"}`.
    placeholder: sum(rate(shop_order_value_USD_count[5m])) / sum(rate(shop_checkouts_total{outcome="ok"}[5m]))
    explanation: That's the evidence. Put it in the incident write-up.
    must_match:
    - pattern: outcome\s*=\s*"ok"
      message: Divide by successful checkouts only (`outcome="ok"`).
    - pattern: \b(rate|increase|irate)\s*\(
      message: These are counters; take their `rate()` over a short window first, or the result is a total since each process started.
    mistakes:
    - pattern: \b1\s*-
      message: That's the share that went missing; the question asks for the share that produced an order.
    - pattern: http_server_request_duration
      message: HTTP requests include page views and product lookups. Compare against successful checkouts.
---

**#finance, 16:20**: *"Revenue today is down about 40% vs the same time last week. Is something broken?"* No alerts have fired.

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
