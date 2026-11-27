---
title: rate() and increase()
summary: Turn ever-growing counters into per-second rates and totals over a window.
kind: query
minutes: 6
concepts: [counter, rate, increase, range vector, counter reset]
assumes: [Selecting series with label matchers]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
    - {label: Raw counter (don't graph this), query: "shop_checkouts_total"}
    - {label: Checkouts per second, query: "rate(shop_checkouts_total[5m])"}
    - {label: Checkouts in the last hour, query: "increase(shop_checkouts_total[1h])"}
checks:
  - id: uses-rate
    type: query
    title: Use `rate()` over a `[5m]` window
    must_include: ["rate(", "[5m]"]
    expect: {rows: {min: 1}}
    success: That's a per-second rate averaged over 5 minutes.
  - id: answer
    type: query
    title: Failed checkouts per second, per series
    reference: 'rate(shop_checkouts_total{outcome="failed"}[5m])'
    tolerance: 0.05
    hint: Filter on `outcome="failed"` inside the selector, then wrap it in `rate(...[5m])`.
    success: A small, steady number. That's what a healthy error rate looks like.
hints:
  - "`rate()` takes a *range vector*: a selector followed by a window, like `metric{...}[5m]`."
  - "Answer: `rate(shop_checkouts_total{outcome=\"failed\"}[5m])`"
---

`shop_checkouts_total` is a **counter**: it only goes up, and it starts
again from zero whenever a process restarts. Its raw value means "checkouts
since this process started", which is almost never the question you have.

Ask instead how fast it grows:

```promql
rate(shop_checkouts_total[5m])      # per-second rate, averaged over 5 minutes
increase(shop_checkouts_total[1h])  # how much it grew in the last hour
```

`increase(x[1h])` is the same as `rate(x[1h]) * 3600`. Use `rate` for graphs
and alerts (the unit stays "per second" whatever the window), and `increase`
when a human wants a total ("37 failed checkouts in the last hour").

Both functions handle **counter resets**: when a counter drops because its
process restarted, they treat the drop as a restart, not as negative traffic.
Subtracting raw values yourself would not.

## Choosing the window

The window (`[5m]`) is how far back each point looks. Short windows react
fast but are noisy; long windows are smooth but slow to show change. It has
to cover several exports: the shop exports every 5 seconds, so `[1m]` works,
and `[5m]` is a calmer default.

> [!TIP]
> MetricsQL lets you leave the window out: `rate(shop_checkouts_total)`
> picks one from the query step automatically. Handy in Grafana, but write it
> explicitly while you learn.

## Try it

Return the per-second rate of **failed** checkouts over the last 5 minutes.
Keep every series (no `sum` yet).
