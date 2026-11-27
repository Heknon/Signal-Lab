import random
import time

from opentelemetry import metrics, trace

tracer = trace.get_tracer("search")
meter = metrics.get_meter("search")
duration = meter.create_histogram("search.duration", unit="s", explicit_bucket_boundaries_advisory=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5])

random.seed(3)
for i in range(25):
    start = time.perf_counter()
    with tracer.start_as_current_span("search") as span:
        span.set_attribute("app.query.terms", random.randint(1, 6))
        time.sleep(random.choice([0.004, 0.006, 0.008, 0.012, 0.15 if i % 11 == 0 else 0.009]))
        duration.record(time.perf_counter() - start)
