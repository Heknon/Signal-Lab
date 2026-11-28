---
title: Reading a trace waterfall
summary: Open one checkout trace in Kibana and work out where its time goes.
kind: quiz
minutes: 7
concepts: [trace waterfall, span, critical path, labels]
assumes: [Kibana APM transactions]
tools: ["elastic:apm"]
quiz:
  questions:
    - id: services
      prompt: "Open a `POST /api/checkout` trace from **storefront**. Not counting `loadgen`, how many services take part? (a number)"
      input: text
      answer: "4"
      explanation: "storefront → checkout → inventory and payments (plus loadgen at the root if you view the full trace: its client span starts it all). Each appears as its own transaction in the waterfall, nested under the client span that called it."
      hint: Count the distinct service names (the coloured legend above the waterfall).
    - id: slowest-span
      prompt: "In a typical successful checkout, which span inside **checkout's** work takes the longest?"
      options:
        - {id: price, label: "price-order"}
        - {id: reserve, label: "The call to inventory (POST /reserve)"}
        - {id: charge, label: "The call to payments (POST /charge)"}
      answer: charge
      explanation: "The payment call dominates: payments waits 60-120 ms on its (simulated) provider in `provider.authorize`. Pricing takes a few milliseconds and the stock reservation about 40 ms."
      hint: Compare the bar lengths of the spans directly under checkout's transaction.
    - id: provider
      prompt: "Expand the payments transaction. What is the name of the span that talks to the payment provider?"
      input: text
      answer: provider.authorize
      explanation: "`provider.authorize` is a client span created by hand in the payments service. It's also where card declines are recorded as exceptions."
      hint: It's the child of payments' `POST /charge` transaction.
    - id: order-id
      prompt: "Click checkout's transaction and open its metadata. Under which field is the order id (`app.order.id` in the code) stored?"
      options:
        - {id: labels, label: "labels.app_order_id"}
        - {id: attr, label: "attributes.app.order.id"}
        - {id: order, label: "order.id"}
        - {id: tx, label: "transaction.id"}
      answer: labels
      explanation: "Attributes without an ECS equivalent become `labels.*`, with dots replaced by underscores. Numeric attributes go to `numeric_labels.*` instead, like `numeric_labels.app_order_total` on the price-order span."
      hint: Look for fields starting with `labels.` in the transaction's metadata tab.
hints:
  - "Services → storefront → Transactions → `POST /api/checkout`, then scroll to **Trace sample**."
  - "Use **View full trace** to see the trace from its root, including the load generator's client span."
---

A **trace waterfall** shows one request as a timeline. Each row is a span,
indented under its parent, with a bar for when it ran. In Kibana, transactions
(the work a service did for a request) are labelled with their service, and
spans sit inside them.

Open **Kibana APM**, pick **storefront → Transactions → POST /api/checkout**,
and scroll down to **Trace sample**. Use the arrows to step through a few
samples.

Things to look for:

- **Gaps**: time inside a transaction not covered by any child span is the
  service's own work (or something nobody instrumented).
- **Sequence**: spans one after another happened in sequence; overlapping
  spans ran in parallel.
- **The critical path**: the chain of spans that decides the total duration.
  Speeding up anything off that path won't make the request faster.

