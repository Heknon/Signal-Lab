---
title: Publishing to a queue
summary: Record a message send as a producer span, so the topic shows up on the map as a dependency.
kind: code
minutes: 6
concepts: [producer span, messaging semantic conventions, messaging.destination.name, service map]
assumes: [Naming dependencies, Span kind]
runtime:
  service: price-fetcher
checks:
  - id: topic
    type: map
    title: "The map shows `price-fetcher` → `price-updates`"
    edge: {from: price-fetcher, to: price-updates, external: true}
  - id: producer
    type: span
    title: "`send price-updates` is a `producer` span"
    where: {name: send price-updates, kind: producer}
  - id: conventions
    type: span
    title: It uses the messaging attribute names
    where:
      kind: producer
      attributes: {messaging.system: "*", messaging.destination.name: price-updates, messaging.operation.type: send}
  - id: no-custom
    type: span
    title: "No home-made `queue`, and no `peer.service` for a topic"
    where: {kind: producer, attributes_absent: [queue, topic, peer.service]}
hints:
  - "`kind=SpanKind.PRODUCER`, and the span name is `{operation} {destination}`."
  - "The keys are `messaging.system`, `messaging.destination.name`, `messaging.operation.type` and `messaging.operation.name`."
  - "A topic isn't a service: name it with `messaging.destination.name`, not `peer.service`."
---

After refreshing prices, the service tells the rest of the system by
publishing to a `price-updates` topic. Right now that's an `internal` span
with a home-made `queue` attribute, so the **Map** has no idea a message was
sent anywhere.

Sending a message is a call to another system, like an HTTP request, but
nobody answers it. That's what the `producer` kind says: *I handed this to a
broker and didn't wait*. The messaging conventions say how to describe it:

| What | Convention |
|---|---|
| Span kind | `producer` (the receiving side is `consumer`) |
| Span name | `{operation} {destination}`: `send price-updates` |
| Broker | `messaging.system`: `kafka`, `rabbitmq`, `aws_sqs`… |
| Topic or queue | `messaging.destination.name` |
| Operation | `messaging.operation.type`: `send` (or `create`, `receive`, `process`, `settle`) and `messaging.operation.name`: the client's own word for it |

```python
with tracer.start_as_current_span("send price-updates", kind=SpanKind.PRODUCER) as span:
    span.set_attribute("messaging.system", "kafka")
    span.set_attribute("messaging.destination.name", "price-updates")
    ...
```

A map draws a producer span as an arrow to its destination, named by
`messaging.destination.name`. Don't reach for `peer.service` here: the
topic is not a service. The services that consume it sit on the other side
of the topic, and the messaging lesson in the next module shows how they
continue your trace.

> [!NOTE]
> Older SDKs and docs name producer spans the other way round,
> `{destination} {operation}` (`price-updates publish`), and use `publish`
> as the operation. You'll still see that in the wild. Backends read the
> attributes, not the name, so both draw the same map.

## Try it

1. Run the starter: the map has `price-api` and `fx-rates`, but nothing for
   the message.
2. Make `publish` a `producer` span named `send price-updates`, with the
   messaging attributes instead of `queue`.
3. Run again: a third arrow, to `price-updates`.
