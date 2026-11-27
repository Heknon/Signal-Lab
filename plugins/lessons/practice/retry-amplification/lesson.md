---
title: When retries make it worse
summary: Retries hide errors from users, but multiply load on a dependency that's already struggling.
kind: experiment
minutes: 9
concepts: [retries, load amplification, retry storm]
assumes: [Blast radius]
tools: ["victoriametrics:explore"]
experiment:
  hypothesis: With 3 retries, payments receives at most 1.5× as many requests as checkout makes orders, even when 40% of payment calls fail.
  steady_state:
    backend: victoriametrics
    query: sum(rate(http_server_request_duration_seconds_count{service_name="payments",http_route="/charge"}[30s])) / sum(rate(http_server_request_duration_seconds_count{service_name="checkout",http_route="/checkout"}[30s]))
    label: payments calls per checkout
    threshold: 1.5
    abort_at: 4
  baseline_s: 40
  inject: {payments: {error_rate: 0.4}, checkout: {retries: 3}}
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
      explanation: Each failed attempt costs another call. With 40% failing, the average order needs about 1.6 calls, and more when the slowdown adds errors.
    - id: success
      prompt: What happened to the storefront checkout success rate compared with the previous experiment?
      options:
        - {id: better, label: "Much better: most failures were hidden by retries"}
        - {id: worse, label: "Worse"}
        - {id: same, label: "About the same"}
      answer: better
      explanation: Up to four attempts turn a 40% failure rate into about 2.5%. That's why retries are tempting.
    - id: risk
      prompt: Payments slows down as its concurrent requests grow. What's the danger of these retries during a real outage?
      options:
        - {id: storm, label: "A retry storm: extra load makes payments slower and less reliable, which triggers more retries"}
        - {id: none, label: "None: retries only happen when calls fail"}
        - {id: cost, label: "Only a slightly bigger cloud bill"}
      answer: storm
      explanation: Retries add load exactly when the dependency is weakest. Use backoff with jitter, a retry budget (e.g. at most 10% extra calls), and circuit breakers.
---

Retries are the most common resilience fix, and the most common way to turn
a partial outage into a total one.

`checkout` will retry failed payment calls up to 3 times, immediately and
with no backoff. Meanwhile, 40% of payment calls fail. The steady state
measures **amplification**: how many payment calls each checkout produces.

```promql
sum(rate(http_server_request_duration_seconds_count{service_name="payments",http_route="/charge"}[30s]))
/
sum(rate(http_server_request_duration_seconds_count{service_name="checkout",http_route="/checkout"}[30s]))
```

Normally that ratio is 1. Watch it during the fault, and compare the
customer-facing success rate with the previous lesson in Grafana.
