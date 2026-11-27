---
title: Nested spans
summary: Build a parent/child tree so a trace shows where the time went.
kind: code
minutes: 6
concepts: [context, parent span, waterfall]
assumes: [Creating a span]
runtime:
  service: order-worker
checks:
  - id: root
    type: span
    title: A root span `process-order`
    where: {name: process-order, parent: root}
  - id: children
    type: span
    title: "`validate`, `charge` and `ship` are children of `process-order`"
    where: {name: "~^(validate|charge|ship)$", parent: process-order}
    count: {min: 3}
  - id: one-trace
    type: trace
    title: Everything is in a single trace
    spans: {min: 4}
    roots: 1
hints:
  - "A span started while another is *current* becomes its child automatically."
  - "Put the three `with tracer.start_as_current_span(...)` blocks *inside* the `process-order` block."
---

A single span tells you something took 300 ms. A **tree** of spans tells
you *which part* took 300 ms.

When you use `start_as_current_span`, the new span becomes the **current
span** in the active **context** until the `with` block ends. Any span
started in the meantime records it as its **parent**:

```python
with tracer.start_as_current_span("parent"):
    with tracer.start_as_current_span("child"):   # parent_span_id = parent
        ...
```

Backends draw this tree as a **waterfall**: each row is a span, indented
under its parent, with a bar showing when it ran.

## Try it

The starter code runs each step as a separate root span, which produces
four unrelated traces. Restructure it so that `validate`, `charge` and `ship`
are children of `process-order`.

> [!TIP]
> After running, click any row in the waterfall to see its `span_id` and
> `parent_span_id`. That pair of ids is all a backend needs to rebuild the tree.
