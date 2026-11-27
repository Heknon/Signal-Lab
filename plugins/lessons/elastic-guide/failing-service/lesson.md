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
      prompt: "The source service's **Errors** tab shows `CardDeclined: card declined by issuer`. Is that the fault you're investigating?"
      options:
        - {id: "yes", label: "Yes, it's the injected fault"}
        - {id: "no", label: "No, card declines happen all the time; the new failures don't record an exception at all"}
      answer: "no"
      explanation: "About 2% of cards are declined in normal traffic, and those record an exception on the `provider.authorize` span. The injected 503s are failed transactions without any recorded exception, so they never appear under Errors. Failed transaction rate and errors are different signals: check both, and compare against what's normal."
      hint: Is the error count new, or was it there before? Does it match a 40% failure rate?
hints:
  - "On the service inventory, sort by **Failed transaction rate**."
  - "In a service's Transactions table, open a transaction group and use the **Failed transaction correlations** or the outcome filter to get failed samples."
  - "Discover works too: `event.outcome : \"failure\" and processor.event : \"transaction\"` over `traces-apm*`."
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
