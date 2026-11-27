import time

from opentelemetry import trace

tracer = trace.get_tracer("batch")

contexts = []
for order_id in ["o-1", "o-2", "o-3"]:
    with tracer.start_as_current_span("enqueue") as span:
        span.set_attribute("app.order.id", order_id)
        # TODO: remember this span's context
        time.sleep(0.01)

# TODO: link this span to every enqueue span
with tracer.start_as_current_span("process-batch") as span:
    span.set_attribute("app.batch.size", 3)
    time.sleep(0.05)
