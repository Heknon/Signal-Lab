import time

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({"service.name": "billing-job", "service.version": "2.3.0"})
provider = TracerProvider(resource=resource)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("billing")

with tracer.start_as_current_span("run-billing"):
    for invoice in ["inv-1", "inv-2", "inv-3"]:
        with tracer.start_as_current_span("send-invoice") as span:
            span.set_attribute("app.invoice.id", invoice)
            time.sleep(0.01)

provider.shutdown()  # flush before exit
print("billing run complete")
