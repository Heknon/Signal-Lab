"""Traffic for this lesson: a web API with real requests and lots of health checks."""
import random

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("web-api")
random.seed(4)
requests = [("GET", "/api/items")] * 20 + [("POST", "/api/orders")] * 5 + [("GET", "/healthz")] * 30
random.shuffle(requests)

for method, route in requests:
    with tracer.start_as_current_span(f"{method} {route}", kind=SpanKind.SERVER) as span:
        span.set_attribute("http.request.method", method)
        span.set_attribute("http.route", route)
        span.set_attribute("http.response.status_code", 200)

print(f"sent {len(requests)} requests, {sum(r == '/healthz' for _, r in requests)} of them health checks")
