---
title: Review an under-instrumented handler
summary: Add the least telemetry that answers three concrete questions about a shipping handler that fails silently.
kind: code
minutes: 12
concepts: [telemetry review, swallowed exceptions, client spans, span status, low-cardinality metrics, telemetry budget]
assumes: [Spans, Metrics, Span status and exceptions]
runtime:
  service: shipping-service
checks:
  - id: failed-status
    type: span
    title: "Q1: the two orders that didn't ship have an error `ship order` span"
    where: {name: ship order, status: error}
    count: 2
  - id: exception
    type: span
    title: "Q1: the exception (why it failed) is recorded"
    where: {status: error, exception: true}
    count: {min: 2}
  - id: shipped-ok
    type: span
    title: The eight orders that shipped are not marked as errors
    where: {name: ship order, status: unset}
    count: 8
  - id: dependency-spans
    type: span
    title: "Q2: each dependency call is a child client span with `server.address`"
    where:
      kind: client
      parent: ship order
      attributes: {server.address: "*"}
    count: {min: 30}
  - id: slow-visible
    type: span
    title: "Q2: the slow carrier call shows up as its own span"
    where: {kind: client, min_duration_ms: 150}
    count: {min: 1}
  - id: shipments
    type: metric
    title: "Q3: a `shipments` counter by `app.carrier` and `outcome`"
    name: shipments
    instrument: counter
    attributes: [app.carrier, outcome]
    attributes_absent: [app.order.id]
    absent_hint: Order ids belong on the span. On a metric, each order becomes its own series.
  - id: budget
    type: budget
    title: "Within budget: 40 spans, 6 series, 2 log records"
    spans: {max: 40}
    series: {max: 6}
    logs: {max: 2}
    hint: Three questions, three answers. Is anything here answering a fourth one nobody asked?
hints:
  - "In the `except` block: `span.record_exception(e)` and `span.set_status(Status(StatusCode.ERROR, str(e)))`, then return as before."
  - "Wrap each dependency call: `with tracer.start_as_current_span(\"carrier quote\", kind=SpanKind.CLIENT) as s: s.set_attribute(\"server.address\", f\"api.{carrier}.example\")`."
  - "Create `shipments = meter.create_counter(\"shipments\", unit=\"{shipment}\")` and add 1 with `{\"app.carrier\": carrier, \"outcome\": \"shipped\"}` or `\"failed\"`."
---

The opposite problem to the last lesson: a shipping handler that tells you
almost nothing. It produces one span per order and no metrics. When an
order doesn't ship, the exception is caught and thrown away, because a
nightly job retries it and the customer only sees "queued". The span ends
with status *unset*, so the failure is invisible.

On-call has three questions about it:

1. **Why didn't order `o-1003` ship?**
2. **Shipping got slower last week. Which dependency is slow?**
3. **How many shipments fail, per carrier?**

Add the minimum telemetry that answers each one, from the right signal.

## Q1: a handled failure is still a failure

Catching an exception is a product decision; it doesn't make the operation
succeed. Record the exception on the span and set its status to error,
then return `queued` exactly as before:

```python
except Exception as e:
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)))
    return {"status": "queued"}
```

A log line would also work, but the span already exists, is already
correlated, and already carries the order id. Adding a log would answer the
same question twice.

## Q2: spans around I/O, not around code

"Which dependency is slow" is a question about where time goes inside one
request, which is what child spans are for. The handler makes three calls
to other systems; give each its own `CLIENT` span with `server.address`, so
traces can be grouped by destination:

| Call | `server.address` |
| --- | --- |
| `validate_address` | `address-service` |
| `carrier_quote` | `api.parcelpost.example` or `api.swiftship.example` |
| `print_label` | `label-printer` |

Don't add spans for the arithmetic in between.

## Q3: a count over time is a metric

"How many, per carrier" is an aggregate. Searching traces for it works for
ten orders and breaks for ten million, and sampling makes the count wrong.
A counter with two low-cardinality attributes, `app.carrier` (2 values)
and `outcome` (2 values), is four time series forever.

> [!NOTE]
> The budget is generous enough for one more small signal, such as a
> duration histogram per carrier. If you add one, say which question it
> answers that the spans don't. (Answer: percentiles over all requests,
> unsampled.)

## Try it

Run the starter: ten spans, every one looks healthy, and two orders
quietly didn't ship. Instrument the handler and leave the simulated
dependencies and the traffic loop alone.
