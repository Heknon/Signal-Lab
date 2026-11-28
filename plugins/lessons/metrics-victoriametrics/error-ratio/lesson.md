---
title: Error ratio per service
summary: Divide 5xx responses by all responses to get each service's error ratio.
kind: query
minutes: 7
concepts: [ratio, vector matching, status code regex]
assumes: [rate() on counters, sum by]
query:
  backend: victoriametrics
  language: metricsql
  range_s: 900
  examples:
  - {label: Responses by status code, query: 'sum by (service_name, http_response_status_code) (rate(http_server_request_duration_seconds_count[5m]))'}
  - {label: Checkout failure ratio (business view), query: 'sum(rate(shop_checkouts_total{outcome="failed"}[5m])) / sum(rate(shop_checkouts_total[5m]))'}
checks:
- id: shape
  type: query
  title: Divide a 5xx rate by a total rate
  must_include: [/, http_response_status_code, rate(]
  expect:
    rows: {min: 1}
    columns: [service_name, value]
  success: Ratio of two rates, matched by service.
  mistakes:
  - {pattern: 'status_code\s*=~?\s*"(2\.\.|[23]\d\d|\(2)', message: 'Divide the errors by all requests, not only the successful
      ones: errors / (errors + successes) is the error ratio.'}
- {id: answer, type: query, title: 5xx error ratio for each service, reference: 'sum by (service_name) (rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
    / sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))', tolerance: 0.05, hint: 'Count only 5xx
    in the numerator (`=~"5.."`), everything in the denominator, and use `sum by (service_name)` on both sides so the labels
    match.', success: 'About 2% for checkout and half that for storefront, which also serves /api/products. payments isn''t
    here at all: its card declines are 402s.'}
hints: ['Both sides need the same labels, or `/` finds nothing to divide. `sum by (service_name)` on each side does that.',
  'Card declines are HTTP 402. That''s a 4xx: the request was fine, the card wasn''t. Don''t count it.', 'Answer: `sum by
    (service_name) (rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m])) / sum by (service_name)
    (rate(http_server_request_duration_seconds_count[5m]))`']
---

An error *count* depends on traffic: 10 errors a minute is a disaster at 20
requests a minute and noise at 20,000. Divide by the total and you get a
**ratio** that means the same thing at any load.

```promql
  sum by (service_name) (rate(http_server_request_duration_seconds_count{http_response_status_code=~"5.."}[5m]))
/
  sum by (service_name) (rate(http_server_request_duration_seconds_count[5m]))
```

## How `/` pairs series

Binary operators match series with **identical label sets**. Here both
sides are `sum by (service_name)`, so `{service_name="checkout"}` on the
left divides `{service_name="checkout"}` on the right. A service with no
5xx series at all has nothing on the left side and drops out of the result.

> [!TIP]
> Want those services to show `0` instead of disappearing? Fill the
> numerator from the denominator: `(errors or total * 0) / total`. For this
> lesson's check, leave them out.

## Which errors?

Not every non-2xx is the server's fault. `payments` returns **402** when the
simulated card issuer declines a card: the service worked fine. Server
errors are **5xx**; a status code regex `=~"5.."` selects exactly those.

## Try it

Return the **5xx error ratio per service** over the last 5 minutes, as a
number between 0 and 1.
