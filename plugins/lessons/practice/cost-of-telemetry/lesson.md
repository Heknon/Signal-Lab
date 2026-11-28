---
title: The cost of telemetry
summary: Estimate series, span and log volume with back-of-envelope arithmetic, and choose between sampling, dropping and aggregating.
kind: quiz
minutes: 10
concepts: [cardinality, series count, span volume, log volume, head sampling, tail sampling, aggregation]
assumes: [Metrics, Spans, Structured logs]
quiz:
  questions:
    - id: series
      prompt: "`http.server.request.duration` has 20 routes, 3 methods and 6 status codes. It runs on 12 pods, and each pod's `service.instance.id` becomes a label. Stored Prometheus-style, each combination is 15 buckets plus `_sum` and `_count`. What is the worst-case series count?"
      options:
        - {id: a, label: "360"}
        - {id: b, label: "4,320"}
        - {id: c, label: "73,440"}
        - {id: d, label: "1,468,800"}
      answer: c
      explanation: "20 × 3 × 6 = 360 attribute combinations, × 12 pods = 4,320, × 17 series per histogram = 73,440. Real counts are lower, because not every route returns every status code, but the worst case is what you size for. Histograms multiply everything by their bucket count, so keep their attributes especially tight."
      hint: Multiply every dimension, then remember that one histogram is several series.
    - id: user-id
      prompt: "Someone adds `app.user.id` (50,000 active users) to a counter that had 360 attribute combinations, on one pod. What's the upper bound on its series count now?"
      options:
        - {id: a, label: "50,360"}
        - {id: b, label: "360,000"}
        - {id: c, label: "18,000,000"}
      answer: c
      explanation: "Attributes multiply: 360 × 50,000 = 18 million. In practice each user touches a few routes, so the real number might be a few hundred thousand, which is still far more than most backends handle comfortably for one metric, and it grows with every new user. User ids go on spans."
      hint: A new attribute doesn't add its values to the count; it multiplies by them.
    - id: spans
      prompt: "A service handles 200 requests per second. Each request produces 25 spans, about 1 KB each. Roughly how much span data per day, before sampling?"
      options:
        - {id: a, label: "4.3 GB"}
        - {id: b, label: "43 GB"}
        - {id: c, label: "432 GB"}
        - {id: d, label: "4.3 TB"}
      answer: c
      explanation: "200 × 25 = 5,000 spans/s. × 86,400 s = 432 million spans a day, × 1 KB ≈ 432 GB. This is why traces are sampled and metrics usually aren't: halving spans per request saves as much as halving traffic."
      hint: "Spans per second first, then seconds per day (86,400)."
    - id: logs
      prompt: "The same service writes one 400-byte INFO log per request (\"request handled\"). How much is that over a 30-day retention?"
      options:
        - {id: a, label: "About 2 GB"}
        - {id: b, label: "About 21 GB"}
        - {id: c, label: "About 207 GB"}
        - {id: d, label: "About 2 TB"}
      answer: c
      explanation: "200 × 400 B = 80 KB/s, × 86,400 = 6.9 GB/day, × 30 ≈ 207 GB, and it says nothing the request span and the HTTP metrics don't. Per-request INFO logs are usually the easiest saving in a telemetry bill."
      hint: "Bytes per second, then per day, then × 30."
    - id: sampling-metrics
      prompt: "You turn on 10% head sampling for traces. Which of these still gives you an unsampled request rate?"
      options:
        - {id: spans, label: "Counting server spans in the trace backend"}
        - {id: spans10, label: "Counting server spans and multiplying by 10"}
        - {id: metric, label: "`rate(http_server_request_duration_seconds_count[5m])`"}
      answer: metric
      explanation: "Metrics are recorded in the process for every request, before any trace sampling, so they stay exact. Multiplying sampled spans by 10 gives an estimate that gets noisy for rare events, such as errors on a quiet route. Use traces for examples and metrics for counts."
      hint: Which signal is recorded for every request, regardless of the trace sampler?
    - id: cardinality-sampling
      prompt: "Your trace sampler keeps 1% of traces. Does that reduce the number of series of a metric recorded in the same service?"
      options:
        - {id: reduces, label: "Yes, by about 99%"}
        - {id: partly, label: "Somewhat, because rare combinations stop appearing"}
        - {id: unaffected, label: "No, the sampler only affects spans"}
      answer: unaffected
      explanation: "The sampler decides which spans are exported; metrics don't pass through it. Series count depends only on attribute cardinality. To cut metric cost you remove attributes (in code, or with a View or the Collector), not sample."
      hint: Do metric measurements go through the trace sampler?
    - id: tail
      prompt: "You must keep every trace that has an error or takes over 1 s, but only 1% of the rest. Which technique?"
      options:
        - {id: head, label: "Head sampling at 1% in the SDK"}
        - {id: tail, label: "Tail sampling in the Collector"}
        - {id: drop, label: "Drop all successful spans in the Collector"}
        - {id: aggregate, label: "Replace traces with a latency histogram"}
      answer: tail
      explanation: "Head sampling decides when the trace starts, before anyone knows it will fail or be slow, so it keeps 1% of errors too. Tail sampling buffers a whole trace and decides at the end, with policies such as \"status is error\", \"latency above 1 s\" and \"1% probabilistic\". It costs Collector memory, and all spans of a trace must reach the same Collector."
      hint: Whether a trace is slow or failed is only known once it has finished.
    - id: chatty
      prompt: "A third-party library emits 5,000 DEBUG log lines per second. Nobody has ever queried them."
      options:
        - {id: sample, label: "Sample them at 10%"}
        - {id: drop, label: "Drop them: raise that logger's level, or filter in the Collector"}
        - {id: aggregate, label: "Turn them into a metric"}
      answer: drop
      explanation: "Data nobody reads is pure cost. Set `logging.getLogger(\"that.library\").setLevel(logging.WARNING)`, or filter by severity in the Collector if you can't change the code. Sampling still pays for 10% of nothing."
      hint: What is 10% of a signal nobody uses worth?
    - id: raw-path
      prompt: "A custom middleware sets `http.route` to the raw path (`/users/8812/orders`), so the metric has 20,000 route values. What's the fix?"
      options:
        - {id: sample, label: "Sample the metric"}
        - {id: drop, label: "Drop `http.route` from the metric"}
        - {id: template, label: "Record the route template, `/users/{id}/orders`"}
      answer: template
      explanation: "Aggregate at the source: the template has a handful of values and keeps the per-route breakdown that dashboards need. Dropping the attribute loses that breakdown. The raw path, if you need it for one request, is `url.path` on the span."
      hint: Keep the useful dimension, but with bounded values.
hints:
  - "Series = product of each attribute's distinct values (× buckets for a histogram). Spans/day = RPS × spans per request × 86,400."
  - "Sampling reduces spans, dropping removes data nobody reads, aggregating turns many events into a few numbers."
---

Telemetry bills are mostly arithmetic, so the cost of a change can be
estimated before it ships. Three formulas cover most of it.

## Metrics: series

A metric's cost is its number of **time series**, one per distinct
combination of attribute values (including resource attributes that become
labels, such as the instance id):

```text
series = values(attr1) × values(attr2) × … × instances
histogram series = that × (buckets + 2)      # + _sum and _count
```

Series cost memory and index space in the backend for as long as they are
active, whether one request or a million hit them.

## Spans: volume

```text
spans per day = requests/s × spans per request × 86,400
bytes per day = spans per day × bytes per span          # 0.5 to 2 KB is typical
```

Every extra span per request costs the same as an extra request. Sampling
divides the total.

## Logs: bytes

```text
bytes per day = lines/s × bytes per line × 86,400
```

Multiply by your retention in days to get storage.

## Three ways to spend less

| Technique | What it does | Use it for |
| --- | --- | --- |
| **Sample** | Keep a fraction of traces, ideally chosen at the tail | High-volume traces where examples are enough |
| **Drop** | Don't emit or don't forward | Data nobody reads: health checks, debug noise, duplicates |
| **Aggregate** | Turn many events into a few numbers, or bound an attribute's values | Counts and distributions; raw paths into route templates |

> [!NOTE]
> Prices vary a lot between vendors, and self-hosting has its own costs.
> The volumes don't vary. Estimate them in series, spans and bytes first,
> then apply your price.
