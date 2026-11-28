---
title: Slow, but nothing's failing
summary: Latency is up across the shop since a traffic spike, with no errors anywhere.
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
    load: 4
  - at:
      min: 150
      max: 420
    fault: true
    load: 9
    set:
      inventory:
        pool_size: 1
hints:
- Errors are flat, so look at latency per service. Which one got slow first?
- Upstream services are slow because they wait on something. Follow the call graph down.
- Search metric names for `db_client`.
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
    answer: inventory
    explanation: 'Right: symptoms show up upstream, but the cause is here.'
    hint: Follow the call graph down from where the symptom appears.
  - id: mechanism
    prompt: What is happening?
    options:
    - id: pool
      label: Inventory's database connection pool is saturated, so requests queue for a connection
    - id: cpu
      label: Every service ran out of CPU
    - id: errors
      label: A dependency is failing intermittently
    - id: network
      label: Network latency between services rose
    answer: pool
    explanation: Connections are all in use and requests wait for one. Saturation shows up as latency, not errors. That's the S in USE.
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that shows requests waiting for a database connection.
    must_include:
    - pending
    expect:
      value:
        gt: 2
    hint: Look for a `db_client_connection_*` metric about pending requests.
    placeholder: db_client_connection_pending_requests
    explanation: That's the evidence. Put it in the incident write-up.
    mistakes:
    - pattern: \bcount\s*\(
      message: '`count()` counts series, not waiting requests: it is 1 on a healthy shop too.'
    - pattern: \b(rate|increase|irate|deriv)\s*\(
      message: Pending requests is a gauge (a level, not a counter); read its value, or its max over a window.
    - pattern: \+
      message: Adding other metrics hides the signal; show the pending requests on their own.
    - pattern: \[\s*(\d+[hdw]|(1[6-9]|[2-9]\d|\d{3,})m)\s*\]
      message: That window reaches back before this incident. Look at the last few minutes.
---

**#marketing, 11:05**: *"Newsletter went out at 11:00, traffic is up."* **#support, 11:09**: *"Site feels slow."* Error-rate alerts are quiet.

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
