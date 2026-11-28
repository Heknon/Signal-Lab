---
title: Which function for which metric?
summary: Recognise counters, gauges and histograms by their names, and pick the right function for each.
kind: quiz
minutes: 4
concepts: [counter, gauge, UpDownCounter, histogram buckets]
assumes: [rate() on counters]
tools: ["victoriametrics:explore", "victoriametrics:vmui"]
quiz:
  questions:
    - id: stock
      prompt: "`inventory_stock` comes from an observable **gauge**. Which query makes sense for a graph of stock per product?"
      options:
        - {id: rate, label: "rate(inventory_stock[5m])"}
        - {id: raw, label: "sum by (app_product_sku) (inventory_stock)"}
        - {id: increase, label: "increase(inventory_stock[1h])"}
        - {id: quantile, label: "histogram_quantile(0.9, inventory_stock)"}
      answer: raw
      explanation: A gauge is already the current value, so you graph it as is (or aggregate it). rate() and increase() assume a counter that only goes up; on a gauge that falls when stock is reserved, they treat every drop as a counter reset and return nonsense.
      hint: Stock goes up and down. Which functions assume a value that only goes up?
    - id: reserved
      prompt: "The shop records `inventory.reserved` with an **UpDownCounter**. Look it up in Explore. Under which name is it stored?"
      options:
        - {id: total, label: "inventory_reserved_total"}
        - {id: plain, label: "inventory_reserved"}
        - {id: items, label: "inventory_reserved_items_total"}
      answer: plain
      explanation: "An UpDownCounter can go down, so it is not a monotonic counter and gets no `_total` suffix: it's stored like a gauge. Treat it like one (no rate())."
      hint: Only monotonic counters get the `_total` suffix.
    - id: histogram
      prompt: "`http.server.request.duration` is a histogram. Which series does it produce in VictoriaMetrics?"
      multiple: true
      options:
        - {id: bucket, label: "http_server_request_duration_seconds_bucket"}
        - {id: count, label: "http_server_request_duration_seconds_count"}
        - {id: sum, label: "http_server_request_duration_seconds_sum"}
        - {id: p95, label: "http_server_request_duration_seconds_p95"}
      answer: [bucket, count, sum]
      explanation: "A histogram is a set of counters: one per bucket (with an `le` label, \"less than or equal\"), plus the total count and the sum of all observed values. Percentiles are computed at query time, never stored."
      hint: Percentiles aren't stored. They're estimated from something else.
    - id: buckets
      prompt: "How many `le` buckets (including `+Inf`) does `shop_order_value_USD_bucket` have for one series? Try `count by (le) (shop_order_value_USD_bucket)`."
      input: text
      answer: "8"
      explanation: "The checkout service sets explicit boundaries 5, 10, 25, 50, 100, 250 and 500 USD. Seven boundaries plus `+Inf` make eight buckets."
      hint: Count the distinct values of the `le` label. Don't forget `+Inf`.
    - id: count-rate
      prompt: "Which query gives requests per second, using only the histogram?"
      options:
        - {id: count, label: "rate(http_server_request_duration_seconds_count[5m])"}
        - {id: sum, label: "rate(http_server_request_duration_seconds_sum[5m])"}
        - {id: raw, label: "http_server_request_duration_seconds_count"}
      answer: count
      explanation: "`_count` is a counter of observations, one per request, so its rate is requests per second. `rate(_sum)` is seconds of work per second, which is useful too: divide it by rate(_count) to get the average duration."
      hint: Which of these counts requests rather than seconds?
hints:
  - "Open Grafana Explore and type a metric name: the label browser shows every label and value."
  - "Suffixes give it away: `_total` is a counter, `_bucket`/`_count`/`_sum` are a histogram, no suffix is usually a gauge."
---

Prometheus-style metrics have no type attached to the query. You tell what
something is from its name, and the function you choose has to match:

| Kind | Looks like | Query it with |
| --- | --- | --- |
| Counter | `shop_checkouts_total` | `rate()`, `increase()` |
| Gauge, UpDownCounter | `inventory_stock`, `db_client_connection_count` | the value itself, `avg_over_time()`, `max_over_time()` |
| Histogram | `…_bucket`, `…_count`, `…_sum` | `histogram_quantile()` over `rate(…_bucket)`; `rate(…_count)` |

Answer the questions below. Use **Grafana Explore** or **VMUI** (links
below) to check the names and labels yourself rather than guessing.

> [!NOTE]
> OpenTelemetry sends each metric with its instrument type. VictoriaMetrics
> uses it to choose the name (`_total` only for monotonic sums), and that
> name is all you have to go on at query time.
