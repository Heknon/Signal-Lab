---
title: Design telemetry from questions
summary: Instrument a checkout feature from scratch so that four operational questions each have an answer in the right signal.
kind: code
minutes: 15
concepts: [instrumentation design, signal choice, cardinality, sampling, log correlation, telemetry budget]
assumes: [Spans, Metrics, Histograms, Structured logs, Log correlation]
runtime:
  service: checkout-service
checks:
  - id: q1-q2-metric
    type: metric
    title: "Q1, Q2: an `orders` counter by `outcome` and `app.payment.provider`"
    name: orders
    instrument: counter
    attributes: [outcome, app.payment.provider]
    attributes_absent: [app.order.id, app.user.id]
    absent_hint: Ids give each order or user its own time series. They belong on the span.
  - id: q3-metric
    type: metric
    title: "Q3: a `checkout.duration` histogram in seconds, by `app.user.tier`"
    name: checkout.duration
    instrument: histogram
    unit: s
    attributes: [app.user.tier]
    attributes_absent: [app.order.id, app.user.id]
  - id: q4-span
    type: span
    title: "Q4: one root `checkout` span per order with `app.order.id`, `app.user.tier` and `app.payment.provider`"
    where:
      name: checkout
      parent: root
      attributes: {app.order.id: "*", app.user.tier: "*", app.payment.provider: "*"}
    count: 20
  - id: q4-failure
    type: span
    title: "Q4: failed orders have an error `checkout` span with the exception"
    where: {name: checkout, status: error, exception: true}
    count: 3
  - id: q4-log
    type: log
    title: "Q4: each failure writes one correlated log record with `app.order.id`"
    attributes: {app.order.id: "~^o-2\\d{3}$"}
    correlated: true
    count: 3
  - id: structured
    type: log
    title: Order ids are attributes, not baked into messages
    body: "~o-\\d+"
    count: {max: 0}
  - id: budget
    type: budget
    title: "Within budget: 40 spans, 12 series, 4 log records"
    spans: {max: 40}
    series: {max: 12}
    logs: {max: 4}
    hint: Count the series each metric's attributes multiply out to, and check that no log line repeats what a span says.
hints:
  - "Start with Q4: wrap `place_order` in `tracer.start_as_current_span(\"checkout\")` and set the order id, tier and provider on it."
  - "Q1 and Q2 are one counter: `orders.add(1, {\"outcome\": outcome, \"app.payment.provider\": provider})`. Add it on both paths."
  - "Q3: time the whole function with `time.perf_counter()` and `duration.record(seconds, {\"app.user.tier\": tier})`. Create it with `meter.create_histogram(\"checkout.duration\", unit=\"s\")`."
  - "In the `except` block: record the exception and error status on the span, then `log.warning(\"payment failed\", extra={\"app.order.id\": ..., \"app.payment.provider\": ...})` inside the span."
---

The starter is a checkout feature with no telemetry at all. Before it ships,
operations has written down what they will ask about it:

1. **How many orders per minute, and what share fail?**
2. **Which payment provider fails most?**
3. **Is checkout slower for gold users?**
4. **What happened to order `o-2009`?** Support has the order id and
   nothing else.

Instrument it so each question has an answer, from the cheapest signal
that answers it well. Use these names, so the checks can find them:
`orders` (counter), `checkout.duration` (histogram, seconds) and a
`checkout` span.

## Which signal for which question

Sort the questions into two kinds first.

**Questions about all requests** (1, 2, 3) are aggregates: rates, ratios,
percentiles. They are metrics. A metric's cost is its number of series, so
each attribute must have a small, fixed set of values:

| Attribute | Values | Fine on a metric? |
| --- | --- | --- |
| `outcome` | ok, failed | yes |
| `app.payment.provider` | 3 | yes |
| `app.user.tier` | standard, gold | yes |
| `app.user.id`, `app.order.id` | unbounded | no |

Questions 1 and 2 are the same counter: `orders` by `outcome` and
provider is at most 2 × 3 = 6 series, and both answers are a `sum by` away.
Question 3 needs a distribution, so a histogram by tier: 2 series.

**Questions about one request** (4) are about a single event, with all its
detail. That is a span: it can carry the order id, user id, tier and
provider at no extra cost, and on failure the exception and error status.

## Why a log as well?

In production, traces are usually sampled. If this service keeps 10% of
traces, there is a 90% chance the trace for `o-2009` is gone. A **failure**
log line, with the order id as an attribute and written inside the span,
survives sampling and still links to the trace when it was kept.

Log failures only. A log per successful order would repeat the span for
every request, which is the duplication the previous lessons removed.

> [!TIP]
> Questions decide the instrumentation, not the other way round. If nobody
> can name the question a signal answers, it probably doesn't need to exist
> yet. When a new question comes up, adding an attribute is a small change.

## Try it

Instrument `place_order` only. Leave the simulated dependencies and the
traffic loop alone: the checks expect 20 orders, 3 of which fail.
