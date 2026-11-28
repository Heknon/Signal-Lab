---
title: Counters
summary: Count things that happen, split by a few meaningful attributes.
kind: code
minutes: 6
concepts: [meter, counter, attributes, units]
assumes: [Basic Python]
runtime: {service: order-service}
checks:
- {id: counter, type: metric, title: '`orders.placed` is a counter with unit `{order}`', name: orders.placed, instrument: counter,
  unit: '{order}'}
- id: attrs
  type: metric
  title: It's split by `app.payment.method`
  name: orders.placed
  attributes: [app.payment.method]
  series: {max: 3}
  series_hint: 'One series per payment method: card, paypal, voucher. Per-order values belong on spans.'
- {id: total, type: metric, title: All 6 orders are counted, name: orders.placed, value: 6}
hints: ['`meter.create_counter("orders.placed", unit="{order}", description=...)` creates the instrument once.', '`orders.add(1,
    {"app.payment.method": method})` records one order.']
---

Metrics answer *how many* and *how much*, cheaply, over long periods of time.
Instead of storing every event, the SDK **aggregates** measurements in memory
and exports a summary every few seconds.

You record measurements with **instruments** from a **meter**:

```python
from opentelemetry import metrics

meter = metrics.get_meter("orders")
orders = meter.create_counter("orders.placed", unit="{order}", description="Orders placed")

orders.add(1, {"app.payment.method": "card"})
```

A **counter** only goes up: requests served, orders placed, bytes sent. The
SDK keeps one running total per unique **attribute set**, which is one *time
series*.

A few conventions worth following:

- **Names** are lowercase and dotted (`orders.placed`), with no unit or
  `_total` in the name. Prometheus-style backends add those for you.
- **Units** use UCUM: `s`, `ms`, `By`, `1`, or a curly-brace annotation for
  counts of things: `{order}`, `{request}`.

## Try it

Create the counter and record each order with its payment method. After
running, open the **Metrics** tab: one counter, three series (card, paypal,
voucher), with a total for each.

> [!NOTE]
> In VictoriaMetrics this metric shows up as `orders_placed_total`, with the
> attribute as a label: `app_payment_method="card"`.
