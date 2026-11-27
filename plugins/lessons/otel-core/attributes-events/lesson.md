---
title: Attributes and events
summary: Attach the context you'll want when debugging, and mark moments inside a span.
kind: code
minutes: 6
concepts: [attributes, span events]
assumes: [Creating a span]
runtime:
  service: cart-service
checks:
  - id: attrs
    type: span
    title: "`checkout` carries `app.user.id` and `app.cart.items`"
    where: {name: checkout, attributes: {app.user.id: "*", app.cart.items: {gte: 1}}}
  - id: number
    type: span
    title: "`app.cart.items` is a number, not a string"
    where: {name: checkout, attributes: {app.cart.items: {gte: 1}}}
  - id: event
    type: span
    title: "A `cart.validated` event is recorded on `checkout`"
    where: {name: checkout, events: [cart.validated]}
hints:
  - "`span.set_attribute(\"app.user.id\", user_id)` adds a key/value pair to the current span."
  - "Attribute values keep their type: pass `len(items)`, not `str(len(items))`."
  - "`span.add_event(\"cart.validated\", {\"app.cart.items\": len(items)})` records a timestamped event."
---

**Attributes** are key/value pairs on a span. They're what you filter and
group by later: *show me slow checkouts for gold-tier users*.

```python
span.set_attribute("app.user.id", "u-42")
span.set_attribute("app.cart.items", 3)        # keep numbers as numbers
```

A few rules of thumb:

- Use **namespaced, dotted keys** (`app.cart.items`, not `items`), so they
  never collide with standard ones.
- Keep **types** honest. A number stored as a string can't be summed or compared.
- Put identifiers like user or order ids on **spans**, not on metrics. Spans
  are individual events, so high-cardinality values are fine here.

**Events** are timestamped log-like records *inside* a span. They mark
moments: *cache miss*, *retry*, *validation passed*.

```python
span.add_event("cart.validated", {"app.cart.items": 3})
```

## Try it

Add the two attributes and the event to the `checkout` span, then run. Click
the span in the waterfall: attributes appear in the detail panel, and the
event shows as a tick on the bar.
