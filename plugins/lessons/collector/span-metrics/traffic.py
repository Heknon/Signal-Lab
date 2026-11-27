"""Traffic for this lesson: a catalog service. Durations are set explicitly."""
import random
import time

from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

tracer = trace.get_tracer("catalog")
random.seed(5)
for _ in range(40):
    route = random.choice(["/products", "/products/{id}", "/search"])
    start = time.time_ns()
    span = tracer.start_span(f"GET {route}", kind=SpanKind.SERVER, start_time=start)
    span.set_attribute("http.route", route)
    if random.random() < 0.1:
        span.set_status(Status(StatusCode.ERROR))
    span.end(end_time=start + int(random.lognormvariate(3.5, 0.6) * 1e6))
time.sleep(1.5)  # let the connector flush its first interval
print("sent 40 requests")
