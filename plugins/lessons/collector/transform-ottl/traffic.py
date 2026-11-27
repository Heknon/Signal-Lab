"""Traffic for this lesson: a legacy service using pre-1.0 HTTP attribute names."""
import random
import uuid

from opentelemetry import trace
from opentelemetry.trace import SpanKind

tracer = trace.get_tracer("legacy-api")
random.seed(2)
for _ in range(12):
    path = random.choice(["/api/items", "/api/cart", "/api/search"])
    with tracer.start_as_current_span("GET", kind=SpanKind.SERVER) as span:
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.target", f"{path}?id={random.randint(1, 999)}&session={uuid.uuid4().hex[:8]}")
print("sent 12 requests")
