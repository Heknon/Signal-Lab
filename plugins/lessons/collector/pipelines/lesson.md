---
title: Collector pipelines
summary: Read the lab's own Collector config, and learn where batching, filtering and sampling belong.
kind: quiz
minutes: 6
concepts: [receiver, processor, exporter, pipeline, connector]
assumes: [What OTLP is]
quiz:
  questions:
    - id: receiver
      prompt: In this lab, every pipeline starts with the same component. Which one receives your code's telemetry?
      options:
        - {id: otlp, label: "The `otlp` receiver (gRPC :4317, HTTP :4318)"}
        - {id: lab, label: "The `otlphttp/lab` exporter"}
        - {id: batch, label: "The `batch` processor"}
      answer: otlp
      explanation: Receivers are how data gets in. One receiver can feed many pipelines, which is how the lab fans out to every backend.
    - id: order
      prompt: Why does `memory_limiter` come first in each pipeline's processor list?
      options:
        - {id: first, label: "It must see data before anything else buffers it, so it can refuse data when memory runs low"}
        - {id: alpha, label: "Processors run in alphabetical order"}
        - {id: none, label: "Order doesn't matter"}
      answer: first
      explanation: Processors run in the order listed. The memory limiter goes first so it can apply back-pressure; batch usually goes last before export.
    - id: drop
      prompt: You want to stop health-check spans (`GET /healthz`) from reaching any backend, without changing services. Where?
      options:
        - {id: filter, label: "A `filter` processor in the traces pipelines"}
        - {id: exporter, label: "In each backend's exporter config"}
        - {id: receiver, label: "Turn off the OTLP receiver's HTTP protocol"}
      answer: filter
      explanation: The `filter` processor drops spans, metrics or logs matching OTTL conditions, like this lab's `filter/lab-runs` does for metrics.
    - id: tail
      prompt: You want to keep 100% of traces with errors and 5% of the rest. What do you need?
      options:
        - {id: tail, label: "The `tail_sampling` processor in a Collector that sees whole traces"}
        - {id: head, label: "A `TraceIdRatioBased(0.05)` sampler in every SDK"}
        - {id: batch, label: "A bigger `batch` timeout"}
      answer: tail
      explanation: Head samplers decide before the outcome is known. Tail sampling buffers spans per trace and decides once it's complete. With several Collectors, route by trace id so each trace lands on one instance.
    - id: fanout
      prompt: How does adding a new backend plugin to this lab change the Collector config?
      options:
        - {id: merge, label: "It adds a config file with its own exporter and pipelines; the Collector merges all `--config` files"}
        - {id: edit, label: "You edit base.yaml to add the exporter to every pipeline"}
        - {id: restart, label: "Backends pull data from the Collector, so nothing changes"}
      answer: merge
      explanation: Each plugin ships `collector.yaml`. Maps merge across `--config` files, and new pipeline names don't collide, so plugins never edit each other.
---

The **Collector** is a vendor-neutral pipeline for telemetry. Its config has
four kinds of components, wired together under `service.pipelines`:

| Component | Job | Examples |
|---|---|---|
| **Receivers** | get data in | `otlp`, `prometheus`, `filelog`, `hostmetrics` |
| **Processors** | change it in flight | `batch`, `memory_limiter`, `filter`, `attributes`, `transform`, `tail_sampling` |
| **Exporters** | send it out | `otlp`, `otlphttp`, `debug`, `prometheusremotewrite` |
| **Connectors** | link pipelines: an exporter of one, a receiver of another | `spanmetrics`, `routing`, `count` |

A pipeline is per **signal**: `traces/...`, `metrics/...`, `logs/...`.

```yaml
service:
  pipelines:
    traces/jaeger:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/jaeger]
```

The lab's real config is on the **Stack** page: every pipeline drawn as
receiver → processors → exporters, plus the raw YAML files. Open it in
another tab and use it to answer the questions.

> [!TIP]
> `name/suffix` (like `otlp/jaeger` or `batch/lab`) creates a second instance
> of the same component type with different settings.
