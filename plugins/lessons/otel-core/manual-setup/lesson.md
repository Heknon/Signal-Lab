---
title: Setting up the SDK yourself
summary: Build the tracer provider, exporter and processor by hand, so you know what opentelemetry-instrument does for you.
kind: code
minutes: 8
concepts: [TracerProvider, BatchSpanProcessor, OTLPSpanExporter, Resource]
assumes: [Creating a span]
runtime:
  service: billing-job
  auto_instrument: false
checks:
  - id: exported
    type: span
    title: "`run-billing` reaches the Collector"
    where: {name: run-billing}
  - id: resource
    type: span
    title: The service is identified as `billing-job` version `2.3.0`
    where: {name: run-billing, service: billing-job, resource: {service.version: "2.3.0"}}
  - id: children
    type: span
    title: All 3 invoices are exported, none lost at exit
    where: {name: send-invoice, parent: run-billing}
    count: 3
hints:
  - "`provider = TracerProvider(resource=Resource.create({\"service.name\": \"billing-job\", \"service.version\": \"2.3.0\"}))`"
  - "`provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))`, then `trace.set_tracer_provider(provider)`."
  - "`OTLPSpanExporter()` with no arguments reads `OTEL_EXPORTER_OTLP_ENDPOINT` from the environment."
---

Every lesson so far ran under `opentelemetry-instrument`. This one runs with
plain `python main.py`. Without an SDK the API is a **no-op**: spans are
created and immediately forgotten.

Setting up tracing takes four pieces:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": "billing-job", "service.version": "2.3.0"})
provider = TracerProvider(resource=resource)                       # 1. the SDK
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # 2. processor → 3. exporter
trace.set_tracer_provider(provider)                                 # 4. make it global
```

- The **Resource** describes *what is emitting*: service name, version,
  environment, host. `Resource.create` also merges `OTEL_RESOURCE_ATTRIBUTES`.
- The **BatchSpanProcessor** buffers spans and exports them in the
  background. (`SimpleSpanProcessor` exports one at a time: handy for
  debugging, slow in production.)
- The **exporter** speaks OTLP. With no arguments it uses the standard
  `OTEL_EXPORTER_OTLP_*` variables.

> [!WARNING]
> Batching means spans sit in memory for a moment. Short-lived scripts must
> flush before exiting. The provider registers an exit hook, and you can call
> `provider.shutdown()` yourself to be sure.

## Try it

Configure the SDK so the billing job's spans are exported with the right
service identity.
