---
title: How OpenTelemetry fits together
summary: The five moving parts, and the journey a span takes from your code to a backend.
kind: quiz
minutes: 4
concepts: [API, SDK, OTLP, Collector, backend]
assumes: []
quiz:
  questions:
    - id: api-sdk
      prompt: A library author wants their package to emit spans without forcing users into any vendor. What should the library depend on?
      options:
        - {id: api, label: "The OpenTelemetry API (`opentelemetry-api`) only"}
        - {id: sdk, label: "The OpenTelemetry SDK with an OTLP exporter"}
        - {id: vendor, label: "A vendor agent"}
      answer: api
      explanation: The API is a thin, no-op-by-default interface. Applications install the SDK and decide where data goes; libraries never should.
      hint: Think about who should decide where the data ends up, the library or the application.
    - id: otlp
      prompt: What is OTLP?
      options:
        - {id: protocol, label: "The wire protocol and data model OpenTelemetry uses to send telemetry"}
        - {id: backend, label: "An open-source storage backend"}
        - {id: lang, label: "A query language for traces"}
      answer: protocol
      explanation: OTLP (gRPC or HTTP, protobuf or JSON) is how SDKs, Collectors and backends exchange traces, metrics and logs.
    - id: collector
      prompt: In this lab, why does telemetry go through a Collector instead of straight to the backends? Pick all that apply.
      multiple: true
      options:
        - {id: fanout, label: "One stream can be fanned out to several backends"}
        - {id: process, label: "Data can be batched, filtered, redacted or sampled in one place"}
        - {id: decouple, label: "Apps only need to know one endpoint; backends can change without redeploying them"}
        - {id: required, label: "The SDK can't export without a Collector"}
      answer: [fanout, process, decouple]
      explanation: The SDK can export directly, but a Collector decouples apps from backends and centralises processing.
    - id: env
      prompt: The lab runs your code as `opentelemetry-instrument python main.py`. Where does the SDK learn the export endpoint?
      options:
        - {id: env, label: "From `OTEL_*` environment variables such as `OTEL_EXPORTER_OTLP_ENDPOINT`"}
        - {id: code, label: "From a hard-coded URL in the lesson's starter code"}
        - {id: backend, label: "It discovers the backend automatically"}
      answer: env
      explanation: Auto-configuration reads the standard `OTEL_*` variables. Open the Environment tab in any code lesson to see them.
---

OpenTelemetry (OTel) is a standard for producing telemetry: **traces**,
**metrics** and **logs**. It doesn't store or display anything. That's the
backend's job. Five parts work together:

| Part | What it does |
|---|---|
| **API** | Interfaces your code calls: `get_tracer()`, `start_span()`, `create_counter()`. No-op until an SDK is installed. |
| **SDK** | The implementation: samples, batches and exports what the API records. |
| **OTLP** | The protocol everything speaks, over gRPC (`:4317`) or HTTP (`:4318`). |
| **Collector** | An optional pipeline in the middle that receives, processes and exports telemetry. |
| **Backend** | Stores and queries it: Elastic, VictoriaMetrics, Jaeger, and many others. |

In this lab a span takes this path:

```text
your code ─API→ SDK ─OTLP→ Collector ─┬→ Elastic / Jaeger / VictoriaMetrics …
                                      └→ the lab's live inspector
```

Because the code only talks to the API, and the SDK only talks OTLP,
**swapping a backend never touches application code**. That's the core
promise of OpenTelemetry, and the reason this course works with whichever
backends you enable.

> [!TIP]
> Already comfortable with this? Mark the module as known on the course page
> and jump straight to **Traces**.
