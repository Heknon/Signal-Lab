import time

from opentelemetry import metrics

meter = metrics.get_meter("jobs")
queue = [f"job-{i}" for i in range(12)]

# TODO: an up-down counter "jobs.active"
# TODO: an observable gauge "queue.length" with attribute app.queue.name="emails"

while queue:
    job = queue.pop()
    # job starts
    time.sleep(0.15)
    # job ends
    print("done", job, "remaining", len(queue))
