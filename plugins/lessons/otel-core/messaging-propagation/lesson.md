---
title: Propagating through a queue
summary: Carry trace context inside a message so the consumer continues the producer's trace.
kind: code
minutes: 7
concepts: [producer, consumer, carrier, extract]
assumes: [Propagating context over HTTP]
runtime:
  service: order-pipeline
checks:
  - id: producer
    type: span
    title: "`orders publish` is a `producer` span"
    where: {name: orders publish, kind: producer}
  - id: consumer
    type: span
    title: "`orders process` is a `consumer` span whose parent is `orders publish`"
    where: {name: orders process, kind: consumer, parent: orders publish}
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
with tracer.start_as_current_span("orders publish", kind=SpanKind.PRODUCER):
    propagate.inject(message["headers"])
    queue.put(message)

# consumer: maybe a different process, minutes later
ctx = propagate.extract(message["headers"])
with tracer.start_as_current_span("orders process", context=ctx, kind=SpanKind.CONSUMER):
    ...
```

`extract` returns a **Context**; passing it as `context=` makes the new
span its child instead of starting a new trace.

> [!TIP]
> Messaging semantic conventions name spans `"{destination} {operation}"`,
> e.g. `orders publish` / `orders process`, so backends can draw the queue as
> an edge in the service map.

## Try it

The queue here is an in-memory list standing in for Kafka. Make the consumer
spans continue the producer's trace.
