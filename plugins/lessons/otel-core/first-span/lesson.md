---
title: Your first span
summary: Create a span, run it, and follow it through the Collector into real backends.
kind: code
minutes: 4
concepts: [span, tracer, auto-configuration]
assumes: []
runtime:
  service: hello-otel
checks:
  - id: span
    type: span
    title: Export a span named `say-hello`
    where: {name: say-hello}
  - id: attr
    type: span
    title: Give it a `greeting.name` attribute
    where: {name: say-hello, attributes: {greeting.name: "*"}}
hints:
  - "`tracer.start_as_current_span(\"say-hello\")` starts a span and ends it when the `with` block exits."
  - "Inside the block, call `span.set_attribute(\"greeting.name\", name)`."
---

A **span** is one unit of work: something with a name, a start and an end.
Spans are the building blocks of a **trace**, the story of a single request
as it moves through your system.

To create spans you ask a **tracer** for one. Tracers come from the global
`TracerProvider`, which the lab has already configured for you, just like
`opentelemetry-instrument` would in production:

```python
from opentelemetry import trace

tracer = trace.get_tracer("hello")

with tracer.start_as_current_span("say-hello") as span:
    span.set_attribute("greeting.name", "Ada")
    print("hello, Ada")
```

## Try it

The editor has most of this already. Rename the span to `say-hello`, add the
attribute, then press **Run** (`⌘ Enter`).

Watch the **Traces** tab: your span shows up there the moment the Collector
forwards it. Shortly after, each enabled backend confirms it has the trace too,
with a link straight to it.

> [!NOTE]
> Nothing in this code mentions a backend. The SDK sends OTLP to whatever
> `OTEL_EXPORTER_OTLP_ENDPOINT` points at. Here that's the Collector, which
> fans the data out. Open **Environment** under the editor to see every
> variable the SDK was configured with.
