import random
import time

from opentelemetry import trace

tracer = trace.get_tracer("orders")


def step(name: str, seconds: float) -> None:
    with tracer.start_as_current_span(name):
        time.sleep(seconds)


with tracer.start_as_current_span("process-order"):
    step("validate", 0.02)
    step("charge", random.uniform(0.05, 0.12))
    step("ship", 0.03)
