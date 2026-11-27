---
title: Who's flooding payments?
summary: Payments traffic tripled and payments is slow, but customer traffic is flat.
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
      payments:
        error_rate: 0.35
      checkout:
        retries: 3
hints:
- Compare request rates across services. Which ratio changed?
- Payments gets more requests than checkout sends orders. Where do the extra ones come from?
- 'Look for 5xx on payments: something is failing and being retried.'
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
    - id: retries
      label: Checkout retries failed payment calls with no backoff, multiplying load on payments
    - id: attack
      label: External traffic is hitting payments directly
    - id: loadgen
      label: The load generator sent more traffic
    - id: leak
      label: Payments is leaking memory
    answer: retries
    explanation: 'Requests per checkout went from 1 to almost 2. The extra load comes from inside: checkout''s retry policy amplifies payments'' own errors.'
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that returns how many payments calls each checkout makes right now.
    must_include:
    - payments
    - checkout
    expect:
      value:
        gt: 1.3
    hint: Divide payments' request rate by checkout's request rate (route `/checkout`).
    placeholder: sum(rate(...payments...[5m])) / sum(rate(...checkout...[5m]))
    explanation: That's the evidence. Put it in the incident write-up.
---

**#payments-oncall, 03:17**: *"Our request rate is way up and latency with it. Storefront says their traffic is normal. Are we under attack?"*

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
