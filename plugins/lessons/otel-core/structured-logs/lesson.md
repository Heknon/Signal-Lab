---
title: Structured logs
summary: Keep the message constant and put the variables in attributes, so logs can be grouped, filtered and counted.
kind: code
minutes: 8
concepts: [structured logging, log attributes, extra]
assumes: [Python logging]
runtime:
  service: order-service
checks:
  - id: constant
    type: log
    title: "Every order logs the same message: `order placed`"
    body: order placed
    count: {min: 4}
  - id: attrs
    type: log
    title: The order details are attributes (`app.order.id`, `app.order.total`, `app.user.id`)
    body: order placed
    attributes: {app.order.id: "*", app.order.total: "*", app.user.id: "*"}
    count: {min: 4}
  - id: typed
    type: log
    title: "`app.order.total` stays a number"
    body: order placed
    attributes: {app.order.total: {gt: 0}}
    count: {min: 4}
  - id: no-baked-values
    type: log
    title: No values baked into any message
    body: "~\\d"
    count: {max: 0}
hints:
  - "`log.info(\"order placed\", extra={\"app.order.id\": order_id, ...})`"
  - "The failure message should be constant too: `log.warning(\"payment declined\", extra={...})`."
---

Compare two ways of logging the same event:

```python
# avoid: every order produces a different message
log.info(f"order {order_id} placed for {total:.2f} USD by {user}")

# prefer: one message, the details as attributes
log.info("order placed", extra={
    "app.order.id": order_id, "app.order.total": total, "app.user.id": user,
})
```

They print similarly, but they're very different to a backend:

| | f-string | constant message + attributes |
|---|---|---|
| Unique messages | one per order: thousands | one: `order placed` |
| "How many orders failed today?" | regex over text | `count by message` |
| "Orders over 100 USD" | impossible without parsing | `WHERE app.order.total > 100` |
| Grouping and alerting on a log pattern | breaks | works |

The OpenTelemetry logging bridge turns each `extra` key into a **log
attribute**, with its type intact. The message becomes the log's **body**.
Think of the message as the *name of the event* and attributes as its
*data*.

What to avoid in log lines:

- **No context**: `"error occurred"`. Error *where*, for *which* order?
- **Secrets and personal data**: tokens, card numbers, emails. Logs get
  copied everywhere.
- **Logging what a metric or span already tells you**: a log line per
  request at INFO is usually a span you haven't written.

## Try it

Rewrite the f-string logs so every message is constant and the details are
attributes. The Logs tab shows the attributes as chips under each message.

> [!TIP]
> Attribute names follow the same rules as span attributes: dotted and
> namespaced. Use the same names on spans and logs so you can correlate them.
