---
title: Find the failing service
summary: Checkouts are failing. Use Grafana Explore and LogsQL to find which service's own logs show the fault.
kind: quiz
minutes: 10
concepts: [Grafana Explore, VictoriaLogs data source, log volume, root cause, trace_id]
assumes: [LogsQL field filters, LogsQL stats by]
tools: ["victorialogs:grafana", "victorialogs:explore"]
scenario:
  chaos:
    payments: {error_rate: 0.4}
  note: One of the shop's services has started failing. The other faults have been cleared. Give it a minute to show up in the logs.
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
      explanation: "storefront and checkout log errors too, but theirs are about a call that failed (`HTTP 502`, `payment failed`). payments' ERROR lines are about payments itself: nothing below it failed."
      hint: "Count ERROR lines per service with `severity_text:=ERROR | stats by (service.name) count()`, then read what each service's errors actually say."
    - id: message
      prompt: "What is the exact message (`_msg`) of the source service's new ERROR lines?"
      input: text
      answer: injected fault
      explanation: "The shop logs `injected fault` whenever its chaos setting fails a request. The message stays constant and the details go in fields, so you can search for it and count it."
      hint: "`service.name:=<the source> severity_text:=ERROR`, and look at `_msg`."
    - id: rate
      prompt: "Those lines carry a field with the configured fault rate. What is the value of `app.chaos.error_rate`?"
      input: text
      answer: "0.4"
      explanation: "Attributes passed with `extra={...}` become fields. 0.4 means 40% of payments requests fail on purpose."
      hint: "Expand one of the lines in Grafana to see all of its fields, or add `| fields _msg, app.chaos.error_rate`."
    - id: affected
      prompt: Which services now log ERROR lines because of the fault?
      multiple: true
      options:
        - {id: storefront, label: storefront}
        - {id: checkout, label: checkout}
        - {id: inventory, label: inventory}
        - {id: payments, label: payments}
      answer: [storefront, checkout, payments]
      explanation: "The failure travels up the call chain: payments fails, checkout logs `payment failed`, storefront logs `checkout failed ... HTTP 502`. inventory isn't on the failing path."
      hint: "`_time:5m severity_text:=ERROR | stats by (service.name) count() errors`"
    - id: last
      prompt: "Take one `injected fault` line and pull every line with its `trace_id`, oldest first. Which line comes **last**?"
      options:
        - {id: fault, label: "payments: injected fault"}
        - {id: payfail, label: "checkout: order ...: payment failed"}
        - {id: checkout, label: "storefront: checkout failed for user ...: HTTP 502"}
        - {id: inv, label: "checkout: order ...: stock reservation failed"}
      answer: checkout
      explanation: "storefront is the first service in and the last one out: it writes its error after checkout's 502 comes back. Reading a trace's logs in time order shows how a failure moved through the system."
      hint: "`_time:5m trace_id:=\"<id>\" | sort by (_time)`"
hints:
  - "In Explore, pick the **VictoriaLogs** data source, type LogsQL in the query field and press **Shift + Enter**. The time picker sets the range, so you don't need a `_time` filter."
  - "Errors from a service that called something else usually describe the call. Look for the service whose errors don't."
---

Users report failed checkouts. A fault is injected somewhere in the shop.
Find **where** it starts, using only logs.

## Grafana Explore with VictoriaLogs

Open **Grafana Explore** below. The **VictoriaLogs** data source is
selected, and the query field takes LogsQL.

- The **Logs** view lists lines; click one to see all of its fields, with
  buttons to filter for or against a value.
- The **log volume** histogram above the lines shows how many lines match
  over time, split by level. A fault shows up as a step.
- A `| stats by (...)` query switches the result to a table or graph.

> [!NOTE]
> The VictoriaLogs data source is a Grafana plugin that Grafana downloads on
> first start. If Explore doesn't list it, use **VMUI** instead: it's
> VictoriaLogs' own UI and takes exactly the same queries.

## A method that works

1. **Count errors per service.** More than one service will show up: when
   a call fails, the caller usually logs an error too.
2. **Read the messages.** An error about a failed call points down the
   chain. The service whose errors are about itself is your culprit.
3. **Follow one request.** Take a `trace_id` from the culprit's error and
   read every line of that trace in time order.

> [!NOTE]
> When you finish, use **Clear faults** in the Scenario drawer (or start
> another lesson) to stop the failures.
