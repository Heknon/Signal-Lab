---
title: Tail sampling
summary: Keep every error and every slow trace, and only a sample of the boring ones.
kind: collector
filename: collector.yaml
minutes: 10
concepts: [tail_sampling, decision_wait, policies]
assumes: [Sampling, Collector pipelines]
runtime: {service: checkout, timeout: 30}
collector: {settle_s: 5}
checks:
- id: errors
  type: span
  title: All 10 failed checkouts are kept
  where: {name: checkout, parent: root, status: error}
  count: {min: 10}
- id: slow
  type: span
  title: All 10 slow checkouts (over 500 ms) are kept
  where: {name: checkout, parent: root, min_duration_ms: 500}
  count: {min: 10}
- id: sampled
  type: span
  title: A sample of the 80 fast, successful ones is kept too (21 to 40 traces in total)
  where: {name: checkout, parent: root}
  count: {min: 21, max: 40}
- id: whole
  type: span
  title: Kept traces are whole, with their `charge-card` child
  where: {name: charge-card, parent: checkout}
  count: {min: 21, max: 40}
hints: ['Policies are OR-ed: a trace is kept if any policy says so.', 'You need three policies: `type: status_code` (ERROR),
    `type: latency` (`threshold_ms: 500`) and `type: probabilistic` (`sampling_percentage: 10`).', 'Set `decision_wait: 2s`
    so the processor waits for the whole trace before deciding.']
---

Head sampling decides when a trace *starts*, before anyone knows how it
ends. Keep 10% and you keep 10% of your errors too.

**Tail sampling** decides after the trace is complete. The Collector buffers
spans by trace id for `decision_wait`, then applies **policies**:

```yaml
processors:
  tail_sampling:
    decision_wait: 2s
    policies:
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}
      - name: slow
        type: latency
        latency: {threshold_ms: 500}
      - name: baseline
        type: probabilistic
        probabilistic: {sampling_percentage: 10}
```

A trace is kept if **any** policy matches. The `and`, `composite` and
`rate_limiting` types build more complex rules.

> [!WARNING]
> Every span of a trace must reach the *same* Collector instance, or each one
> decides on a fragment. With several replicas, put a `loadbalancing` exporter
> in front that routes by trace id.

## Try it

`traffic.py` sends 100 checkouts: 10 fail, 10 are slow, and 80 are fast and
fine. Configure tail sampling to keep every interesting trace and about 10%
of the rest.
