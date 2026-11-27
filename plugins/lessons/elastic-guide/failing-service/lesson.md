---
title: Find the failing service
summary: Checkouts are failing. Follow failed transactions through Kibana APM to the service that causes them.
kind: quiz
minutes: 10
concepts: [failed transaction rate, event.outcome, errors vs failures, root cause]
assumes: [Kibana APM transactions, Reading a trace waterfall]
tools: ["elastic:apm", "elastic:service-map", "elastic:discover"]
scenario:
  chaos:
    payments: {error_rate: 0.4}
  note: One of the shop's services has started failing. The other faults have been cleared. Give it a minute to show up in Kibana.
quiz:
  questions:
    - id: source
      prompt: Which service is the **source** of the failures?
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: payments
      explanation: "storefront and checkout fail too, but only because the call below them failed. In a failed trace, payments' transaction is the deepest one marked as failed: nothing it calls has failed."
      hint: Open a failed `POST /api/checkout` trace and walk down the waterfall to the last failed transaction.
    - id: status
      prompt: "Which HTTP status code does the source service return for the failing requests?"
      input: text
      answer: "503"
      explanation: "503 Service Unavailable. checkout turns it into a 502 for storefront, which returns 502 to the user: the original code only survives on the deepest span."
      hint: "Look at `http.response.status_code` on the source service's failed transactions."
    - id: rate
      prompt: "Roughly what **failed transaction rate** does Kibana show for that service now?"
      options:
        - {id: r2, label: "about 2%"}
        - {id: r20, label: "about 20%"}
        - {id: r40, label: "about 40%"}
        - {id: r100, label: "100%"}
      answer: r40
      explanation: "The fault fails 40% of payments requests. checkout's rate matches it (every payment failure fails the order), while storefront's is lower because its product listing doesn't involve payments."
      hint: It's on the service inventory and on the service's Overview.
    - id: errors-tab
      prompt: "The source service's **Errors** tab includes `CardDeclined: card declined by issuer` and `RuntimeError: payments is having a bad day (injected fault)`. Which one is the incident?"
      options:
        - {id: runtime, label: "The `RuntimeError`: it appeared when the failures started, and its count tracks the failed transaction rate"}
        - {id: declined, label: "`CardDeclined`: it's a payment error"}
        - {id: both, label: "Both equally"}
      answer: runtime
      explanation: "About 2% of cards are declined in normal traffic, so `CardDeclined` was there before the incident and its rate didn't change. Always compare against what's normal: the new error group, and the one whose count follows the failure rate, is the incident."
      hint: Look at each group's occurrences over time. Which one was already there an hour ago?
---

Users report failed checkouts. The fault is already injected somewhere in
the shop. Your job: find **where** it starts.

## How failures propagate

When a service fails, its callers usually fail as well: checkout gets an
error from a dependency and returns its own error to storefront, which
returns one to the user. So in the service list, several services go red at
once. Only one of them is the **source**.

Two signals help you tell them apart:

- **Failed transaction rate**: share of transactions with
  `event.outcome: failure`. For HTTP servers that's a 5xx status (or a span
  status of `ERROR`).
- **Errors**: exceptions that were recorded on spans, grouped by type and
  message. Only exceptions the code actually recorded show up here.

## A method that works

1. On the **service inventory**, see which services' failed transaction rate
   went up.
2. Open a failed trace from the top-most one (storefront's
   `POST /api/checkout`).
3. Walk down the waterfall. The source is the deepest failed transaction
   whose children all succeeded.
4. Check what you found against the **Errors** tab and against normal
   traffic, so you don't chase a problem that was always there.

> [!NOTE]
> When you finish, use **Clear faults** in the Scenario drawer (or start
> another lesson) to stop the failures.
