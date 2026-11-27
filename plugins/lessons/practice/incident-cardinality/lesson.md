---
title: The metrics bill doubled
summary: Dashboards are slow and the metrics bill jumped overnight. Nothing is down.
kind: incident
minutes: 12
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
    load: 6
  - at: 60
    fault: true
    set:
      storefront:
        label_user_id: true
hints:
- 'Count series per metric name: `count by (__name__) ({__name__=~"shop_.*"})`.'
- Which labels does the exploding metric have? Pick one series and read its labels.
- Which service records that metric?
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
    answer: storefront
    explanation: 'Right: symptoms show up upstream, but the cause is here.'
    hint: Follow the call graph down from where the symptom appears.
  - id: mechanism
    prompt: What is happening?
    options:
    - id: label
      label: A user id was added as a metric attribute, creating a series per user
    - id: traffic
      label: More traffic means more series
    - id: scrape
      label: Metrics are exported more often
    - id: histogram
      label: A new histogram with many buckets
    answer: label
    explanation: Series count is the product of label cardinalities. One user-id label multiplies `shop_checkouts_total` by the number of users.
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that returns how many time series `shop_checkouts_total` has now.
    must_include:
    - count
    expect:
      value:
        gt: 40
    hint: '`count(...)` over the metric name counts its series.'
    placeholder: count(shop_checkouts_total)
    explanation: That's the evidence. Put it in the incident write-up.
---

**#platform, 08:55**: *"Our metrics backend ingests way more series since yesterday's deploy, and Grafana is crawling. Which team did this?"*

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
