"""Traffic for this lesson: payments that carry personal data they shouldn't."""
import random

from opentelemetry import trace

tracer = trace.get_tracer("payments")
random.seed(9)
for i in range(12):
    with tracer.start_as_current_span("charge") as span:
        span.set_attribute("user.email", f"customer{i % 5}@example.com")
        span.set_attribute("app.card.number", f"4242 4242 4242 {1000 + i}")
        span.set_attribute("app.payment.amount", round(random.uniform(5, 200), 2))
print("sent 12 charges")
