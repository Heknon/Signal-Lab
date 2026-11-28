from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

provider = TracerProvider(
    resource=Resource.create({"service.name": "search-api"}),
    sampler=TraceIdRatioBased(0.2),
)
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("search")

for i in range(200):
    with tracer.start_as_current_span("handle-search") as span:
        span.set_attribute("app.query.length", i % 17)
        with tracer.start_as_current_span("query-index"):
            pass

provider.shutdown()
print("handled 200 searches")
