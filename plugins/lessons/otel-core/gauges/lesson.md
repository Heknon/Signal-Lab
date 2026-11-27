---
title: Gauges and up-down counters
summary: Track values that go up and down, by recording changes or by observing the current value.
kind: code
minutes: 6
concepts: [up-down counter, observable gauge, callbacks]
assumes: [Counters]
runtime:
  service: job-runner
checks:
  - id: active
    type: metric
    title: "`jobs.active` is an up-down counter"
    name: jobs.active
    instrument: updowncounter
  - id: queue
    type: metric
    title: "`queue.length` is an observable gauge"
    name: queue.length
    instrument: gauge
    attributes: [app.queue.name]
hints:
  - "`meter.create_up_down_counter(\"jobs.active\")`, then `.add(1)` when a job starts and `.add(-1)` when it ends."
  - "`meter.create_observable_gauge(\"queue.length\", callbacks=[observe])`, where `observe` yields `metrics.Observation(value, attributes)`."
---

Not everything only goes up. Two instruments cover values that move both ways:

| Instrument | You report | Use it for |
|---|---|---|
| **Up-down counter** | *changes*: `+1`, `-1` | things you track as they change: active jobs, open connections |
| **Observable gauge** | the *current value*, from a callback | things you can only sample: queue length, temperature, memory |

Observable ("asynchronous") instruments don't record anything when your code
runs. Instead, the SDK calls your **callback** each time it collects:

```python
def observe(options):
    yield metrics.Observation(len(queue), {"app.queue.name": "emails"})

meter.create_observable_gauge("queue.length", callbacks=[observe])
```

## Try it

Track active jobs with an up-down counter, and report the queue length with
an observable gauge.
