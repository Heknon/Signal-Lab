import random

from opentelemetry import metrics

meter = metrics.get_meter("orders")

# TODO: unit should be seconds, with buckets that fit 10 ms to 600 ms
duration = meter.create_histogram("order.processing.duration", unit="ms")

random.seed(7)
for _ in range(200):
    elapsed_ms = random.lognormvariate(3.8, 0.6)  # mostly 20-100 ms, a long tail
    duration.record(elapsed_ms)

print("recorded 200 orders")
