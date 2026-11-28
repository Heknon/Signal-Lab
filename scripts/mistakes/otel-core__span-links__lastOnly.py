import time

from opentelemetry import trace

tracer = trace.get_tracer("batch")

contexts = []
for order_id in ["o-1", "o-2", "o-3"]:
    with tracer.start_as_current_span("enqueue") as span:
        span.set_attribute("app.order.id", order_id)
        time.sleep(0.01)
    contexts.append(span.get_span_context())

links = [trace.Link(ctx) for ctx in contexts]
with tracer.start_as_current_span("process-batch", links=links) as span:
    span.set_attribute("app.batch.size", 3)
    time.sleep(0.05)
