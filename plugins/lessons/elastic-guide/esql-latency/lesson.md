---
title: Latency with ES|QL
summary: Compute average and p95 latency per transaction name, and convert microseconds to milliseconds.
kind: query
minutes: 7
concepts: [AVG, PERCENTILE, EVAL, transaction.duration.us]
assumes: [ES|QL FROM, WHERE and STATS]
query:
  backend: elastic
  language: esql
  range_s: 900
  examples:
    - {label: Slowest transactions right now, query: "FROM traces-apm* | WHERE processor.event == \"transaction\" | SORT transaction.duration.us DESC | KEEP @timestamp, service.name, transaction.name, transaction.duration.us | LIMIT 10"}
    - {label: Span latency by span name (payments), query: "FROM traces-apm* | WHERE processor.event == \"span\" AND service.name == \"payments\" AND @timestamp > NOW() - 15 minutes | STATS p95_us = PERCENTILE(span.duration.us, 95) BY span.name"}
checks:
  - id: shape
    type: query
    title: "Use `PERCENTILE(transaction.duration.us, 95)` grouped by `transaction.name`"
    must_include: ["PERCENTILE", "transaction.duration.us", "transaction.name", "storefront"]
    expect: {rows: {min: 2}, columns: [avg_ms, p95_ms, transaction.name]}
    success: "avg_ms and p95_ms per storefront transaction group. `POST /api/checkout` should be the slower one."
hints:
  - "Durations are stored in microseconds: `transaction.duration.us`. Divide by `1000.0` for milliseconds."
  - "Aggregate first, then convert: `STATS avg_us = AVG(...), p95_us = PERCENTILE(..., 95) BY transaction.name | EVAL avg_ms = avg_us / 1000.0, p95_ms = p95_us / 1000.0`."
  - "Use `KEEP` to drop the intermediate `_us` columns if you like."
---

Every transaction document has `transaction.duration.us`: how long it took,
in **microseconds**. Spans have `span.duration.us`.

`STATS` supports the aggregations you'd expect: `COUNT`, `AVG`, `MIN`,
`MAX`, `MEDIAN` and `PERCENTILE(field, p)`. Use `EVAL` to compute new columns
from existing ones:

```esql
FROM traces-apm*
| WHERE processor.event == "transaction" AND service.name == "checkout"
| STATS p95_us = PERCENTILE(transaction.duration.us, 95) BY transaction.name
| EVAL p95_ms = ROUND(p95_us / 1000.0, 1)
```

> [!TIP]
> Averages hide outliers. A handful of very slow requests barely moves the
> average but shows up clearly in p95 or p99. Look at both.

## Try it

For **storefront**, over the last 15 minutes, return one row per
`transaction.name` with two columns: `avg_ms` (average) and `p95_ms` (95th
percentile), both in milliseconds.
