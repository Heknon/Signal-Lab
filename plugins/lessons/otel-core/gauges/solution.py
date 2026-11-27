import time

from opentelemetry import metrics

meter = metrics.get_meter("jobs")
queue = [f"job-{i}" for i in range(12)]

active = meter.create_up_down_counter("jobs.active", unit="{job}", description="Jobs in progress")


def observe(options):
    yield metrics.Observation(len(queue), {"app.queue.name": "emails"})


meter.create_observable_gauge("queue.length", callbacks=[observe], unit="{job}", description="Jobs waiting")

while queue:
    job = queue.pop()
    active.add(1)
    time.sleep(0.15)
    active.add(-1)
    print("done", job, "remaining", len(queue))
