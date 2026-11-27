---
title: Span links
summary: Connect work that's related but isn't a parent and child, like a batch job processing many requests.
kind: code
minutes: 6
concepts: [span links, batch processing]
assumes: [Nested spans]
runtime:
  service: batch-worker
checks:
  - id: producers
    type: span
    title: Three `enqueue` spans, each in its own trace
    where: {name: enqueue, parent: root}
    count: 3
  - id: links
    type: span
    title: "`process-batch` links to all three"
    where: {name: process-batch, links: {min: 3}}
hints:
  - "Collect `span.get_span_context()` inside each `enqueue` span."
  - "Pass `links=[trace.Link(ctx) for ctx in contexts]` when starting `process-batch`."
---

Parent/child works when one operation *causes* another. Some work doesn't
fit that shape:

- A batch job processes 100 messages that came from 100 different requests.
- A retry starts a fresh trace, but you want to jump back to the original.
- A scheduled job is *triggered by* a request but runs much later.

A span has exactly one parent, but it can have many **links**. A link
points at another span context, often in a different trace, and says
*this is related*.

```python
links = [trace.Link(ctx, {"app.reason": "batched"}) for ctx in contexts]
with tracer.start_as_current_span("process-batch", links=links):
    ...
```

Links must be supplied when the span **starts**, because samplers can use
them to decide whether to keep the span.

## Try it

Each `enqueue` creates its own trace. Capture their span contexts and link
`process-batch` to them. In the waterfall, linked spans show a link icon, and
the detail panel lists the trace ids they point to.
