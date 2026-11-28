---
title: Correlating logs with traces
summary: Log inside spans so every line carries a trace id, and jump between the two.
kind: code
minutes: 5
concepts: [log correlation, trace_id, span_id]
assumes: [Structured logs, Creating a span]
runtime: {service: refund-service}
checks:
- id: correlated
  type: log
  title: Every log record carries a trace id and span id
  correlated: true
  count: {min: 3}
  in_span: refund
- id: all
  type: log
  title: No log record is left without trace context
  correlated: false
  count: {max: 0}
- {id: error-linked, type: log, title: The failure is logged at ERROR inside the failing span, severity: ERROR, correlated: true,
  in_span: refund}
hints: [Move the `log.info`/`log.error` calls inside the `with tracer.start_as_current_span(...)` block.]
---

When a log record is emitted while a span is **active**, the SDK stamps it
with that span's `trace_id` and `span_id`. That turns *"here's an error log"*
into *"here's the error, and here's the whole request that led to it"*.

No extra code is needed, as long as you log **inside** the span. Logs written
before the span starts, or after it ends, have no trace context.

```python
with tracer.start_as_current_span("refund"):
    log.info("refund requested", extra={"app.order.id": order_id})   # ← correlated
log.info("done")                                                    # ← no trace id
```

Backends use this both ways. Elastic shows a trace's logs next to its
waterfall, and from a log line you can open the trace.

## Try it

The starter logs around the spans instead of inside them. Fix it, run, then
click a trace id in the **Logs** tab to jump to the exact span that wrote it.
