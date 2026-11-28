import random

from opentelemetry import metrics

meter = metrics.get_meter("orders")

duration = meter.create_histogram(
    "order.processing.duration",
    unit="s",
    description="Time to process an order",
    explicit_bucket_boundaries_advisory=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2],
)

random.seed(7)
for _ in range(200):
    elapsed_ms = random.lognormvariate(3.8, 0.6)  # mostly 20-100 ms, a long tail
    duration.record(elapsed_ms / 1000)

print("recorded 200 orders")
