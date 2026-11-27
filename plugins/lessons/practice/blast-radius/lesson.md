---
title: Blast radius
summary: Inject errors into payments and find every service that felt it.
kind: experiment
minutes: 8
concepts: [blast radius, error propagation, dependencies]
assumes: [Your first experiment, Error ratios]
tools: ["victoriametrics:explore", "victoriametrics:dashboards"]
experiment:
  hypothesis: Storefront checkout success stays above 90% when 30% of payment calls fail.
  steady_state:
    backend: victoriametrics
    query: sum(rate(http_server_request_duration_seconds_count{service_name="storefront",http_route="/api/checkout",http_response_status_code="200"}[30s])) / sum(rate(http_server_request_duration_seconds_count{service_name="storefront",http_route="/api/checkout"}[30s]))
    label: storefront checkout success ratio
    direction: below
    threshold: 0.9
    abort_at: 0.4
  baseline_s: 40
  inject: {payments: {error_rate: 0.3}}
  duration_s: 60
  recovery_s: 40
quiz:
  questions:
    - id: outcome
      kind: outcome
      prompt: Did the hypothesis hold?
      options:
        - {id: held, label: "Yes"}
        - {id: rejected, label: "No"}
        - {id: aborted, label: "Aborted"}
      explanation: Nothing between storefront and payments absorbs the failure, so about 30% of checkouts fail too.
    - id: services
      prompt: Which services returned server errors (5xx) during the fault? Select all that apply.
      multiple: true
      options:
        - {id: payments, label: "`payments`"}
        - {id: checkout, label: "`checkout`"}
        - {id: storefront, label: "`storefront`"}
        - {id: inventory, label: "`inventory`"}
      answer: [payments, checkout, storefront]
      explanation: The error travels up every caller. Inventory isn't a caller of payments, so it's untouched.
    - id: shrink
      prompt: Which change would shrink this blast radius most?
      options:
        - {id: fallback, label: "Checkout accepts the order and charges asynchronously, retrying later"}
        - {id: bigger, label: "More replicas for storefront"}
        - {id: timeout, label: "A longer timeout on storefront → checkout"}
      answer: fallback
      explanation: Decoupling the user request from the flaky dependency stops the error reaching the customer. More storefront replicas or longer timeouts don't touch the cause.
---

A fault never stays where you inject it. Every caller of a failing service
has to do *something* with the error: pass it on, retry, or degrade
gracefully. The set of things that end up affected is the **blast radius**.

This experiment injects a 30% error rate into `payments` and measures what
the *customer* sees: the share of storefront checkouts that succeed.

```promql
sum(rate(http_server_request_duration_seconds_count{service_name="storefront",http_route="/api/checkout",http_response_status_code="200"}[30s]))
/
sum(rate(http_server_request_duration_seconds_count{service_name="storefront",http_route="/api/checkout"}[30s]))
```

The steady state here is a **success ratio**, so lower is worse: the
hypothesis holds while the line stays *above* 0.9, and the experiment aborts
below 0.4.

While it runs, open the provisioned **Signal Shop · overview** dashboard and
watch the error panels.
