---
title: From a log line to its trace
summary: Start from an error log in Discover, follow its trace.id to the full trace, and find what really went wrong.
kind: quiz
minutes: 8
concepts: [log correlation, trace.id, Discover, KQL]
assumes: [Reading a trace waterfall]
tools: ["elastic:discover", "elastic:apm"]
quiz:
  questions:
    - id: field
      prompt: "Which field ties a log record to the trace it was written in?"
      options:
        - {id: trace, label: "trace.id"}
        - {id: tx, label: "transaction.name"}
        - {id: host, label: "host.name"}
        - {id: label, label: "labels.order_id"}
      answer: trace
      explanation: "The OpenTelemetry logging handler stamps each record with the active trace and span ids. APM Server stores them as `trace.id` and `span.id`, the same fields the spans carry."
      hint: Open any shop log document in Discover and look for an id that also appears on spans.
    - id: storefront-log
      prompt: "In `logs-apm*`, find an **error** log from **storefront**. What does it say?"
      options:
        - {id: checkout, label: "checkout failed for user user-…: HTTP 502"}
        - {id: stock, label: "order …: stock reservation failed"}
        - {id: placed, label: "order … placed: … item(s)"}
        - {id: timeout, label: "connection timed out"}
      answer: checkout
      explanation: "storefront logs this whenever checkout returns an error. It tells you *that* checkout failed, not why."
      hint: "KQL: `service.name : \"storefront\" and log.level : (ERROR or error)`. Python writes the level in capitals; KQL on keyword fields is case-sensitive."
    - id: who-logged
      prompt: "Filter Discover on that log's `trace.id`. Which services wrote a log line in the same trace?"
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: [storefront, checkout, payments]
      explanation: "payments warns that the payment was declined, checkout logs `payment failed`, storefront logs `checkout failed`. Read bottom-up, the logs tell the story in order."
      hint: "Click the `trace.id` value in the document and choose **Filter for value**."
    - id: root
      prompt: "Open the trace in APM. On which span is the root-cause exception recorded?"
      options:
        - {id: authorize, label: "provider.authorize (payments)"}
        - {id: charge, label: "POST /charge (payments)"}
        - {id: checkout, label: "POST /checkout (checkout)"}
        - {id: api, label: "POST /api/checkout (storefront)"}
      answer: authorize
      explanation: "`provider.authorize` records a `CardDeclined` exception and sets its status to ERROR. Everything above it is a consequence. (A declined card is a 402 on `POST /charge`, which Elastic doesn't count as a server failure.)"
      hint: In the waterfall, look for the span with an error marker deepest in the tree.
hints:
  - "Discover → data view or index pattern `logs-apm*`. Narrow the time picker to the last 15 minutes."
  - "From an APM trace you can also go the other way: the transaction's **Logs** tab lists logs with the same `trace.id`."
---

Logs are often where an investigation starts: someone pastes an error line
into chat. On its own, a line like `checkout failed for user user-123: HTTP
502` doesn't say much. Its **`trace.id`** gets you everything else.

Every log the shop writes inside a request carries the ids of the active
trace and span. That makes two jumps possible:

- **Log → trace**: copy the `trace.id` from a log and open the trace in APM
  (or search APM for it).
- **Trace → logs**: from a transaction in APM, open its **Logs** tab, or
  filter Discover on the same `trace.id`.

## Try it

You don't need to inject anything: about 2% of card payments are declined in
normal traffic, and each decline leaves a trail of logs across services.

Open **Discover** below, choose `logs-apm*`, and find an error log from
storefront. Then follow its `trace.id`.

> [!TIP]
> In Discover, add the `service.name`, `log.level` and `message` columns
> from the field list. A compact table is much easier to read than whole
> documents.
