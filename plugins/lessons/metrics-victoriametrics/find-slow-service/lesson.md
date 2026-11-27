---
title: Find the slow service
summary: Something made the shop slow. Use Grafana to find which service is the cause, not just a victim.
kind: quiz
minutes: 10
concepts: [latency investigation, upstream vs downstream, histogram buckets]
assumes: [histogram_quantile, Grafana dashboards]
tools: ["victoriametrics:dashboards", "victoriametrics:explore"]
scenario:
  chaos:
    inventory: {latency_ms: 700}
  note: One of the shop's services now has a problem. The other faults have been cleared. Give it a minute or two to show up in the graphs.
quiz:
  questions:
    - id: culprit
      prompt: Which service is the **source** of the slowdown?
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: inventory
      explanation: "storefront, checkout and inventory all got slower, but inventory is the one that calls nobody: its own time went up. storefront and checkout are only waiting for it."
      hint: Several services look slow. Which one is slow without calling anything else?
    - id: bucket
      prompt: "Between which bucket boundaries does the culprit's **p95** server latency fall now?"
      options:
        - {id: b1, label: "100 ms – 250 ms"}
        - {id: b2, label: "250 ms – 500 ms"}
        - {id: b3, label: "500 ms – 750 ms"}
        - {id: b4, label: "750 ms – 1 s"}
        - {id: b5, label: "1 s – 2.5 s"}
      answer: b4
      explanation: "The fault adds 700 ms ± 30% to every request, so most requests land between 490 and 910 ms. The slowest 5% sit in the 750 ms – 1 s bucket."
      hint: "Look at `histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{service_name=\"...\"}[2m])))` and compare it with the bucket list from the percentiles lesson."
    - id: routes
      prompt: Which of the culprit's routes are slow?
      multiple: true
      options:
        - {id: stock, label: "GET /stock"}
        - {id: reserve, label: "POST /reserve"}
        - {id: charge, label: "POST /charge"}
      answer: [stock, reserve]
      explanation: "Both inventory routes are slow, so it's the whole service (here: an injected delay before every request), not one slow query."
      hint: "Add `http_route` to the `by` clause of your p95 query."
    - id: checkout-why
      prompt: "storefront's `POST /api/checkout` is slower too. Why?"
      options:
        - {id: own, label: storefront itself got slower}
        - {id: chain, label: "It waits for checkout, which waits for inventory's /reserve"}
        - {id: payments, label: payments is slow}
        - {id: load, label: There is more traffic}
      answer: chain
      explanation: "Latency adds up along the call chain: storefront → checkout → inventory. `http_client_request_duration_seconds` with `server_address=\"inventory\"` on checkout shows exactly that wait."
      hint: "Compare checkout's client metric (`http_client_request_duration_seconds_bucket{service_name=\"checkout\"}`) by `server_address`."
hints:
  - "The **Signal Shop · overview** dashboard has p50/p95 latency per service. Start there."
  - "A slow service makes everything that calls it slow. Follow the calls down until you reach a service whose own latency went up."
---

Someone reports that the shop "feels slow". Your job: find out which service
is actually responsible.

The fault is already injected. Open the **Signal Shop · overview**
dashboard (under **Dashboards → Signal Lab**), or your own from the previous
lesson, and narrow it down.

## A method that works

1. **Start wide.** Latency per service. More than one line went up? Expected:
   a slow service slows down everyone who calls it.
2. **Follow the calls.** storefront calls checkout and inventory; checkout
   calls inventory and payments. A caller's latency includes its callees'.
3. **Find the one that's slow on its own.** The client metric
   `http_client_request_duration_seconds` shows how long each caller waited
   for each `server_address`. The service everyone is waiting for is your
   culprit.
4. **Zoom in.** Which routes? How slow? Check the buckets.

> [!TIP]
> Shorten the rate window (`[1m]` or `[2m]`) or zoom Grafana to the last
> 5 minutes to see the change sooner. A `[5m]` window takes five minutes to
> fully catch up.

> [!NOTE]
> When you finish, use **Clear faults** in the Scenario drawer (or start
> another lesson) to make the shop fast again.
