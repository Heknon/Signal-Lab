---
title: Exploring in Grafana
summary: Use Grafana Explore's metrics and label browser to answer questions about the shop without writing much MetricsQL.
kind: quiz
minutes: 6
concepts: [Grafana Explore, label browser, client vs server metrics]
assumes: [Selecting series with label matchers]
tools: ["victoriametrics:explore", "victoriametrics:grafana"]
quiz:
  questions:
    - id: clients
      prompt: "Which services report **outgoing** HTTP calls (`http_client_request_duration_seconds_count`)?"
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
        - {id: loadgen, label: loadgen}
      answer: [storefront, checkout, loadgen]
      explanation: "Only services that call other services have HTTP client metrics. inventory and payments are leaves: they serve requests but make no HTTP calls of their own (inventory's database is simulated with spans, not HTTP)."
      hint: "In Explore, pick the metric, then open the label filter for `service_name` to see which values exist."
    - id: callees
      prompt: "Which hosts does **checkout** call? Look at the `server_address` label of its client metric."
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
        - {id: provider, label: api.payments.example}
      answer: [inventory, payments]
      explanation: "checkout reserves stock in inventory and charges payments. `api.payments.example` only shows up in traces: the payments provider call is a span, not an instrumented HTTP request."
      hint: "Try `sum by (server_address) (rate(http_client_request_duration_seconds_count{service_name=\"checkout\"}[5m]))`."
    - id: codes
      prompt: "Which status codes does the payments `/charge` route return during normal traffic?"
      multiple: true
      options:
        - {id: "200", label: "200"}
        - {id: "402", label: "402"}
        - {id: "500", label: "500"}
        - {id: "503", label: "503"}
      answer: ["200", "402"]
      explanation: "200 for captured payments and 402 for the ~2% of cards the simulated issuer declines. 503 only appears when you inject a fault."
      hint: "Group the server request counter for payments by `http_response_status_code`."
    - id: env
      prompt: "Every series carries a `deployment_environment_name` label, set from the OpenTelemetry resource. What is its value?"
      input: text
      answer: lab
      explanation: "The shop sets `OTEL_RESOURCE_ATTRIBUTES=deployment.environment.name=lab,...`. Resource attributes become labels on every metric the process sends, which is how you'd tell staging from production."
      hint: "Run `count by (deployment_environment_name) (inventory_stock)`, or use the label browser."
hints:
  - "Explore has a **Builder** mode (pick metric, labels and operations from menus) and a **Code** mode (type MetricsQL). Switch with the toggle above the query."
  - "The label filter drop-downs only offer values that actually exist for the chosen metric."
---

**Explore** is Grafana's scratchpad: one query, one graph, no dashboard to
save. It's where you go to poke at data before you know what the panel
should look like.

Open **Grafana Explore** below. The VictoriaMetrics data source is already
selected. A few things worth knowing:

- **Metrics browser / Builder**: pick a metric name and see every label it
  has, with the values that occur. You can answer most questions here
  without typing a query.
- **Code** mode: type MetricsQL directly, with autocomplete for metric and
  label names. **Shift + Enter** runs it.
- **Table** view: switch the result to a table to read exact label values.
- **Split**: compare two queries side by side.

> [!TIP]
> From Explore, **Add → Add to dashboard** turns the current query into a
> panel. That's often the quickest way to start a dashboard.

Answer the questions using Explore. Every answer is visible in the labels.
