---
title: It's only some customers
summary: Error rate rose a little after this morning's deploy. Support says it's only certain customers.
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
      checkout:
        version: 1.5.0
        gold_error_rate: 0.7
hints:
- Split checkout errors by `service_version`.
- The overall error rate is small. Split it by any attribute that describes the customer.
- '`shop_checkouts_total` has an `app_user_tier` label.'
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
    answer: checkout
    explanation: 'Right: symptoms show up upstream, but the cause is here.'
    hint: Follow the call graph down from where the symptom appears.
  - id: mechanism
    prompt: What is happening?
    options:
    - id: release
      label: The new checkout release fails for gold-tier customers only
    - id: payments
      label: Payments rejects gold-tier cards
    - id: capacity
      label: Checkout is overloaded
    - id: all
      label: Every customer is affected a little
    answer: release
    explanation: 'Split by `service_version` and by `app_user_tier`: the errors started with 1.5.0 and hit gold users only.'
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that shows which customer tier the failed checkouts come from.
    must_include:
    - shop_checkouts_total
    expect:
      top:
        app_user_tier: gold
    hint: Rate of `shop_checkouts_total{outcome="failed"}` split by `app_user_tier`.
    placeholder: sum by (app_user_tier) (rate(shop_checkouts_total{outcome="failed"}[5m]))
    explanation: That's the evidence. Put it in the incident write-up.
---

**#deploys, 09:30**: *checkout 1.5.0 rolled out.* **#support, 09:41**: *"Our best customers can't check out!"*

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
