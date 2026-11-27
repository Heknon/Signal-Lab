---
title: Your first experiment
summary: Test whether checkout stays fast when its inventory dependency slows down.
kind: experiment
minutes: 8
concepts: [hypothesis, steady state, latency injection]
assumes: [What chaos engineering is, Latency percentiles]
tools: ["victoriametrics:explore"]
experiment:
  hypothesis: Checkout p95 latency stays under 1 s when inventory adds 300 ms to every request.
  steady_state:
    backend: victoriametrics
    query: histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="checkout"}[30s])))
    label: checkout p95 (s)
    threshold: 1.0
    abort_at: 3.0
  baseline_s: 40
  inject: {inventory: {latency_ms: 300}}
  duration_s: 60
  recovery_s: 40
quiz:
  questions:
    - id: outcome
      kind: outcome
      prompt: Did the hypothesis hold?
      options:
        - {id: held, label: "Yes, p95 stayed under the limit"}
        - {id: rejected, label: "No, p95 crossed the limit"}
        - {id: aborted, label: "The experiment was aborted"}
      explanation: Right. The chart is the evidence; the hypothesis is only as good as the metric you chose.
    - id: why-more
      prompt: Checkout's p95 rose by *more* than 300 ms. Why?
      options:
        - {id: jitter, label: "The injected delay varies per request, and p95 picks the slow end of that range"}
        - {id: twice, label: "Checkout calls inventory twice per order"}
        - {id: cpu, label: "The fault also made checkout's CPU busy"}
      answer: jitter
      explanation: The fault adds 300 ms ± 30%. A percentile sits on the slow side of that spread, which is why you test with percentiles, not averages.
    - id: radius
      prompt: Which service got slower without being touched? Check in Grafana.
      options:
        - {id: storefront, label: "`storefront`"}
        - {id: payments, label: "`payments`"}
        - {id: loadgen, label: "None"}
      answer: storefront
      explanation: Storefront calls checkout and inventory, so it inherits both delays. Latency propagates up the call graph. That's the blast radius.
---

**Hypothesis:** checkout's p95 latency stays under 1 second even when its
inventory dependency adds 300 ms to every request.

When you press **Start experiment**, the lab:

1. records 40 s of **baseline**,
2. **injects** 300 ms of latency into `inventory` for 60 s,
3. removes it and watches 40 s of **recovery**.

The chart plots the steady-state query every few seconds: the dashed line is
the hypothesis limit, and the red line is the abort condition. If p95 ever
crosses 3 s, the fault is removed immediately.

```promql
histogram_quantile(0.95,
  sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name="checkout"}[30s])))
```

> [!TIP]
> A 30 s rate window makes the graph react quickly, at the cost of noise.
> Real experiments often use a longer window and run for longer.

Answer the questions once it finishes. Use Grafana Explore to look beyond
checkout.
