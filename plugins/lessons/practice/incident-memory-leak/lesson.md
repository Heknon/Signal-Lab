---
title: Blips every few minutes
summary: Inventory throws a short burst of errors every couple of minutes, then recovers on its own.
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
        leak_mb_per_min: 150
hints:
- Plot inventory's request rate. Notice anything about counters?
- Count the distinct `service_instance_id` values for inventory. Why are there several?
- Look at `process_memory_usage_bytes` for inventory over 15 minutes.
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
    - id: leak
      label: Memory grows until the process is killed and restarts, dropping in-flight requests
    - id: cron
      label: A scheduled job runs every few minutes
    - id: gc
      label: Garbage-collection pauses
    - id: deps
      label: A dependency fails periodically
    answer: leak
    explanation: Memory climbs in a sawtooth and drops at each restart; every restart gets a new `service_instance_id`, and counters reset to zero.
  - id: evidence
    kind: query
    backend: victoriametrics
    language: metricsql
    prompt: Write a query that returns the highest memory inventory reached in the last 10 minutes.
    must_include:
    - process_memory
    expect:
      value:
        gt: 200000000
    hint: '`max_over_time` of `process_memory_usage_bytes` for inventory.'
    placeholder: max_over_time(process_memory_usage_bytes{service_name="inventory"}[10m])
    explanation: That's the evidence. Put it in the incident write-up.
---

**#alerts**: *inventory error rate > 1%: firing… resolved… firing… resolved.* The pattern repeats every few minutes.

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
