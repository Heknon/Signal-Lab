"""Traffic for this lesson: 100 checkouts. Durations are set explicitly, so nothing sleeps."""
import random
import time

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("checkout")
random.seed(11)
kinds = ["error"] * 10 + ["slow"] * 10 + ["ok"] * 80
random.shuffle(kinds)

for kind in kinds:
    start = time.time_ns()
    duration_ms = random.uniform(650, 1500) if kind == "slow" else random.uniform(20, 120)
    end = start + int(duration_ms * 1e6)
    root = tracer.start_span("checkout", start_time=start)
    ctx = trace.set_span_in_context(root)
    child = tracer.start_span("charge-card", context=ctx, start_time=start + 1_000_000)
    if kind == "error":
        child.set_status(Status(StatusCode.ERROR, "card declined"))
        root.set_status(Status(StatusCode.ERROR, "payment failed"))
    child.end(end_time=end - 1_000_000)
    root.end(end_time=end)

print("sent 100 checkouts: 10 failed, 10 slow, 80 fine")
