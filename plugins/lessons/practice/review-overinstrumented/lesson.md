---
title: Review an over-instrumented handler
summary: Cut a checkout handler's telemetry down to what answers real questions, and take the card number out.
kind: code
minutes: 12
concepts: [telemetry review, duplicate signals, span granularity, PII, cardinality, telemetry budget]
assumes: [Spans, Metrics, Structured logs, Span status and exceptions]
runtime:
  service: checkout-service
checks:
  - id: checkout-span
    type: span
    title: One root `checkout` span per order, with the item count in `app.cart.items`
    where:
      name: checkout
      parent: root
      attributes: {app.cart.items: {gte: 1}}
    count: 12
  - id: declined
    type: span
    title: Each declined order's `checkout` span has status `error` and the exception
    where: {name: checkout, status: error, exception: true}
    count: 3
  - id: no-item-spans
    type: span
    title: No span per cart item
    where: {name: add item}
    count: {max: 0}
  - id: no-card-span
    type: span
    title: No span carries the card number
    where:
      attributes: {app.card.number: "*"}
    count: {max: 0}
  - id: no-card-log
    type: log
    title: No log line contains a card number
    body: "~(?<!\\d)\\d{13,16}(?!\\d)"
    count: {max: 0}
  - id: orders-metric
    type: metric
    title: "`orders` counts checkouts by `outcome`, not by user"
    name: orders
    instrument: counter
    attributes: [outcome]
    attributes_absent: [app.user.id]
    absent_hint: A user id gives every customer their own time series. It's already on the span.
  - id: declines-not-errors
    type: log
    title: A declined card is not logged at ERROR
    severity: ERROR
    count: {max: 0}
  - id: budget
    type: budget
    title: "Within budget: 24 spans, 3 series, 4 log records"
    spans: {max: 24}
    series: {max: 3}
    logs: {max: 4}
    hint: Look for signals that repeat what another signal already says.
hints:
  - "Replace the `add item` loop with plain arithmetic and set `span.set_attribute(\"app.cart.items\", ...)` on `checkout`."
  - "Delete the `checkout.failures` counter: `orders{outcome=\"declined\"}` already counts declines. Drop `app.user.id` from `orders`."
  - "`service.started` is a counter that is incremented once in the process's life, with a timestamp as an attribute. A single `log.info(\"checkout service started\")` says the same."
  - "Keep `span.record_exception(e)` and `set_status(...)`. Remove `log.exception(...)` and both per-request `log.info(...)` calls."
---

Instrumentation accumulates. Someone adds a log to debug an incident,
someone else adds a metric for a dashboard nobody opens, a third person
wraps a loop in spans. Each addition looked reasonable; together they cost
money, slow queries down, and can leak data you are not allowed to keep.

The starter is a checkout handler after a few months of that. It runs, and
its telemetry is complete. Your job is to make it smaller without losing
any answer.

## What it emits now

| Signal | What it says | Problem |
| --- | --- | --- |
| `add item` span per cart item | "we added an item" | Sub-millisecond arithmetic. 2 to 5 spans per order, with no information beyond the item count. |
| `log.info("checkout started ... card ...")` | a request started | The `checkout` span already records that, with its start time. It also prints the full card number. |
| `log.info("checkout finished in span ...")` | a request finished | The span's end time. Copying the span id into the message by hand does not correlate anything; the SDK does that for you. |
| `log.exception(...)` on a decline | the card was declined | Also recorded on the span and counted twice in metrics. A decline is an expected business outcome; at ERROR it pages someone or trips a log alert. |
| `checkout.failures{app.user.id}` | declines per user | `orders{outcome="declined"}` already counts declines. Per-user series grow with your customer base. |
| `orders{outcome, app.user.id}` | orders per user | Fine counter, wrong attribute. |
| `app.card.number` span attribute | the card | A primary account number in your telemetry backend puts that backend in PCI scope. It is never worth it. |
| `service.started` counter | the process started | A time series that is incremented once in the process's life, with a timestamp as an attribute, so each start makes a new series. |

## What to keep

Ask what someone will need when something goes wrong:

- **How many orders, and how many declined?** `orders` by `outcome`.
- **What happened to this order?** The `checkout` span: user, item count,
  and on a decline, error status and the exception.
- **Is the payment provider slow?** The `charge` client span. That one is a
  network call to another system, so it earns its span.

Everything else is either already answered by one of those or not worth
answering.

> [!TIP]
> A rule of thumb for child spans: make one when the work can be slow or
> fail independently of its parent, which usually means I/O (a network
> call, a query, a file). Loops over in-memory data almost never qualify;
> put the count on the parent instead.

## Try it

Run the starter and look at the inspector: 67 spans, 16 metric series and
two log lines per request, for 12 orders. Refactor until the checks pass. The traffic
at the bottom stays as it is.
