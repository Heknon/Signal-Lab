---
title: Propagating through a queue
summary: Carry trace context inside a message so the consumer continues the producer's trace.
kind: code
minutes: 7
concepts: [producer, consumer, carrier, extract]
assumes: [Propagating context over HTTP, Publishing to a queue]
runtime:
  service: order-pipeline
checks:
  - id: producer
    type: span
    title: "`send orders` is a `producer` span"
    where: {name: send orders, kind: producer}
  - id: consumer
    type: span
    title: "`process orders` is a `consumer` span whose parent is `send orders`"
    where: {name: process orders, kind: consumer, parent: send orders}
    count: 3
hints:
  - "Producer: `propagate.inject(message[\"headers\"])` inside the publish span."
  - "Consumer: `ctx = propagate.extract(message[\"headers\"])`, then `start_as_current_span(..., context=ctx, kind=SpanKind.CONSUMER)`."
---

HTTP has headers, and so do Kafka, RabbitMQ, SQS and most queues: message
**headers** or **attributes** you can use as a carrier. The pattern is the
same everywhere:

```python
# producer
with tracer.start_as_current_span("send orders", kind=SpanKind.PRODUCER):
    propagate.inject(message["headers"])
    queue.put(message)

# consumer: maybe a different process, minutes later
ctx = propagate.extract(message["headers"])
with tracer.start_as_current_span("process orders", context=ctx, kind=SpanKind.CONSUMER):
    ...
```

`extract` returns a **Context**; passing it as `context=` makes the new
span its child instead of starting a new trace.

> [!TIP]
> The span names follow the messaging conventions, `{operation} {destination}`:
> `send orders` on the producer, `process orders` on the consumer. Together with
> `messaging.destination.name`, that's what lets a backend draw the `orders`
> queue between the two sides.

## Try it

The queue here is an in-memory list standing in for Kafka. Make the consumer
spans continue the producer's trace.
