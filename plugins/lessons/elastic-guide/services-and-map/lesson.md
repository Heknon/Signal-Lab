---
title: Services, transactions and the service map
summary: Find your way around Kibana APM, from the service list down to a service's transactions and who it calls.
kind: quiz
minutes: 7
concepts: [service inventory, transaction, transaction group, service map]
assumes: [What a trace and a span are]
tools: ["elastic:apm", "elastic:service-map"]
quiz:
  questions:
    - id: transaction
      prompt: "In Elastic APM, what is a **transaction**?"
      options:
        - {id: trace, label: A whole trace, across all services}
        - {id: server, label: "The entry span of a service: the server span that starts its work for a request"}
        - {id: any, label: Any span with a duration over 1 ms}
        - {id: db, label: A database transaction}
      answer: server
      explanation: "APM Server turns each service's incoming (server or consumer) spans, and every root span, into transactions, and everything inside them into spans. One trace through the shop has a transaction per service it touched."
      hint: Open one service and look at what the Transactions table lists. Are those requests it received, or calls it made?
    - id: inventory-groups
      prompt: "Open **inventory**. Which transaction groups does it have from shop traffic?"
      multiple: true
      options:
        - {id: stock, label: "GET /stock"}
        - {id: reserve, label: "POST /reserve"}
        - {id: charge, label: "POST /charge"}
        - {id: products, label: "GET /api/products"}
      answer: [stock, reserve]
      explanation: "A transaction group is every transaction with the same name. inventory serves stock lookups for the storefront and reservations for checkout."
      hint: Services → inventory → Transactions.
    - id: slowest
      prompt: "Open **storefront**. Roughly how much slower is `POST /api/checkout` than `GET /api/products`, on average?"
      options:
        - {id: same, label: "About the same"}
        - {id: x3, label: "About 3×"}
        - {id: x10, label: "About 10×"}
        - {id: x30, label: "About 30×"}
      answer: x3
      explanation: "Around 150 ms against 50 ms. /api/checkout waits for checkout, which waits for inventory and payments in turn; /api/products only asks inventory for stock."
      hint: Compare the latency column in the storefront's Transactions table.
    - id: checkout-calls
      prompt: "Which services does **checkout** call?"
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: [inventory, payments]
      explanation: "checkout reserves stock in inventory, then charges the card through payments. The service map draws exactly these edges, worked out from the spans' parent/child links across services."
      hint: Open the service map and look at checkout's outgoing arrows, or open one checkout trace and look at which services appear below it.
    - id: leaves
      prompt: "Which services call no other shop service?"
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: [inventory, payments]
      explanation: "inventory and payments are leaves. They still have outgoing spans (a simulated database and a simulated payment provider), but those are dependencies, not instrumented services."
      hint: On the map, which service nodes have no arrows leaving them toward another service?
hints:
  - "Kibana → Observability → APM → **Services** lists every `service.name` that sent data."
  - "Click a service for its Overview: latency, throughput, failed transaction rate, and the Transactions table."
---

Kibana's APM app is built on traces. Open **Kibana APM** below and you land
on the **service inventory**: one row per `service.name`, with latency,
throughput and failed transaction rate.

Elastic uses its own words for OpenTelemetry concepts:

| OpenTelemetry | Elastic APM |
| --- | --- |
| Server span (where a service receives a request) | **transaction** |
| Every other span | **span** |
| Span name of a server span, e.g. `POST /api/checkout` | `transaction.name`, grouped into a **transaction group** |
| Span status `ERROR` / HTTP 5xx | `event.outcome: failure` |
| Attributes Elastic has no field for, e.g. `app.user.tier` | `labels.app_user_tier` |

Click into a service to see its transaction groups, then open the
**Service map** to see how the services connect.

> [!NOTE]
> The service map is a paid feature in self-managed Kibana. If Kibana asks
> you to upgrade, start a free 30-day trial under **Stack Management →
> License Management**, or answer the map questions from a trace instead: the
> waterfall shows every service a request went through.
