---
title: Selecting series
summary: Find OpenTelemetry metrics under their Prometheus names and narrow them down with label matchers.
kind: query
minutes: 5
concepts: [time series, label matcher, OTLP name mapping]
assumes: [What a metric is]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
  - {label: Every stock gauge, query: inventory_stock}
  - {label: One product, query: 'inventory_stock{app_product_sku="TEL-001"}'}
  - {label: Regex match, query: 'http_server_request_duration_seconds_count{http_route=~"/api/.*"}'}
checks:
- id: selector
  type: query
  title: Use a label matcher on `http_response_status_code`
  must_include: [http_server_request_duration_seconds_count, http_response_status_code]
  expect:
    rows: {min: 1}
  success: You are filtering on a label.
  must_match:
  - {pattern: 'service_name\s*=~?\s*"payments"', message: Narrow it to the payments service with a `service_name` label filter.}
  - {pattern: status_code\s*=\s*"402"|status_code\s*!=\s*"200"|status_code\s*!~\s*"2, message: 'Select the declined payments:
      the `402` status code.'}
- {id: answer, type: query, title: Return every non-2xx counter series from `payments`, reference: 'http_server_request_duration_seconds_count{service_name="payments",
    http_response_status_code!~"2.."}', hint: Filter on both `service_name` and the status code. `!~"2.."` means "does not
    match the regex 2.."., success: Those are the card declines. Every distinct label combination is its own series.}
hints: ['Matchers go in curly braces after the metric name: `metric{label="value"}`.', '`!=` excludes one value; `!~` excludes
    everything matching a regex, like `"2.."`.', 'Answer: `http_server_request_duration_seconds_count{service_name="payments",
    http_response_status_code!~"2.."}`']
---

A **time series** is a metric name plus a unique set of **labels**. The
selector `inventory_stock` returns one series per label combination; add
matchers in braces to keep only the ones you want.

## From OpenTelemetry names to Prometheus names

The shop sends metrics over OTLP. VictoriaMetrics translates names and
attributes into Prometheus conventions on the way in:

| OpenTelemetry | In VictoriaMetrics |
| --- | --- |
| `http.server.request.duration` (histogram, unit `s`) | `http_server_request_duration_seconds_bucket`, `_count`, `_sum` |
| `shop.checkouts` (counter) | `shop_checkouts_total` |
| `inventory.stock` (gauge) | `inventory_stock` |
| attribute `http.response.status_code` | label `http_response_status_code` |
| resource attribute `service.name` | label `service_name` |

Dots become underscores, the unit is appended, and monotonic counters gain
`_total`. Resource attributes such as `service.version` and
`deployment.environment.name` become labels on every series too.

## Matchers

| Matcher | Meaning |
| --- | --- |
| `label="x"` | equals |
| `label!="x"` | not equal |
| `label=~"x\|y"` | matches regex (anchored) |
| `label!~"2.."` | does not match regex |

## Try it

Select `http_server_request_duration_seconds_count` series from the
`payments` service whose status code is **not** 2xx.

> [!NOTE]
> You'll get the raw, ever-growing count since each process started. That's
> fine for looking at which series exist, but not for graphs. The next lesson
> shows why.

> [!TIP]
> Seeing two series where you expected one? Look at `service_instance_id`:
> every process restart starts a new series.
