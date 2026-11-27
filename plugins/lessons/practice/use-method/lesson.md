---
title: The USE method
summary: Utilization, Saturation and Errors for the resources behind a service, using the Signal Shop's connection pool and memory metrics.
kind: quiz
minutes: 10
concepts: [USE method, utilization, saturation, connection pool, queueing, RED vs USE]
assumes: [MetricsQL basics, The RED method]
tools: ["victoriametrics:explore", "victoriametrics:vmui"]
quiz:
  questions:
    - id: which-method
      prompt: "Which of these would you watch with USE rather than RED? Choose every one."
      multiple: true
      options:
        - {id: pool, label: "The inventory service's database connection pool"}
        - {id: api, label: "The storefront's `/api/checkout` endpoint"}
        - {id: disk, label: "The disk VictoriaMetrics writes to"}
        - {id: queue, label: "A message queue between two services"}
        - {id: payments, label: "The payments service as checkout sees it"}
      answer: [pool, disk, queue]
      explanation: "USE is for **resources**: things with a capacity that work waits for, such as pools, disks, CPUs and queues. RED is for **services**: things that receive requests and answer them. An endpoint and a downstream service are seen through their requests, so RED."
      hint: Which of these has a fixed capacity, as opposed to answering requests?
    - id: utilization
      prompt: "The inventory service exports `db_client_connection_count` with `db_client_connection_state` = `used` or `idle`. Which query is the pool's utilization?"
      options:
        - {id: ratio, label: "sum(db_client_connection_count{db_client_connection_state=\"used\"}) / sum(db_client_connection_count)"}
        - {id: used, label: "sum(db_client_connection_count{db_client_connection_state=\"used\"})"}
        - {id: rate, label: "rate(db_client_connection_count[5m])"}
        - {id: pending, label: "sum(db_client_connection_pending_requests)"}
      answer: ratio
      explanation: "Utilization is the share of capacity that's busy: used ÷ (used + idle). The number of used connections alone means nothing until you know the pool size. `rate()` is wrong here: this is an UpDownCounter, a value that goes up and down."
      hint: Utilization is a fraction of capacity, between 0 and 1.
    - id: saturation
      prompt: "Which of these measure the pool's **saturation**? Choose every one."
      multiple: true
      options:
        - {id: pending, label: "`db_client_connection_pending_requests`: requests waiting for a connection"}
        - {id: wait, label: "`db_client_connection_wait_time_seconds`: time spent waiting for a connection"}
        - {id: used, label: "Connections in state `used`"}
        - {id: errors, label: "5xx responses from inventory"}
      answer: [pending, wait]
      explanation: "Saturation is work that can't be served yet: the length of the queue, or how long things wait in it. When utilization reaches 100%, saturation is what grows, and that growth is what users feel as latency."
      hint: Saturation is about work that is waiting, not work that is being done.
    - id: bursts
      prompt: "A dashboard shows the pool at 40% average utilization, yet `db_client_connection_pending_requests` regularly goes above zero. What's the likely explanation?"
      options:
        - {id: bug, label: "The metric is wrong: you can't queue below 100%"}
        - {id: burst, label: "Load is bursty: for short moments every connection is busy, and the average hides it"}
        - {id: errors, label: "Connections are failing and being retried"}
      answer: burst
      explanation: "Utilization averaged over a scrape interval or a 5-minute window smooths out bursts. If ten requests arrive in the same millisecond, they queue even if the pool is idle the rest of the second. Saturation shows the bursts that averaged utilization misses, which is why USE asks for both."
      hint: What happens to a one-second spike when you average over a minute?
    - id: active-requests
      prompt: "`http_server_active_requests` counts requests in flight. The shop's services are async Python with no fixed worker limit. Which USE letter is it closest to?"
      options:
        - {id: u, label: "Utilization"}
        - {id: s, label: "Saturation"}
        - {id: e, label: "Errors"}
      answer: s
      explanation: "With no fixed capacity there's nothing to divide by, so it isn't a utilization. Rising in-flight requests while the request rate stays flat means each request is waiting longer for something, so it works as a saturation proxy. Little's law: in-flight = arrival rate × time in system."
      hint: Utilization needs a capacity to divide by. Is there one?
    - id: memory
      prompt: "`process_memory_usage_bytes` for one inventory instance climbs steadily for an hour. Rate, errors and latency all look normal. What should you conclude?"
      options:
        - {id: fine, label: "Nothing: RED is healthy, so users are fine"}
        - {id: leading, label: "A resource is running out. RED will look fine until it doesn't, so act before the process is killed"}
        - {id: scale, label: "Add more instances: traffic must be growing"}
      answer: leading
      explanation: "This is where USE earns its place next to RED. RED measures symptoms, which only appear once something breaks: here, when the process hits its memory limit and restarts, failing every request in flight. A steadily rising utilization predicts that failure. Investigate it, but alert on the symptom, not on memory alone."
      hint: RED tells you users are hurting now. What tells you they will be soon?
    - id: missing
      prompt: "Which USE signal for the shop's services can you **not** find in VictoriaMetrics? Search the metric names in Explore or VMUI."
      options:
        - {id: cpu, label: "CPU utilization"}
        - {id: memory, label: "Memory usage"}
        - {id: pool, label: "Connection pool usage"}
        - {id: pending, label: "Connection pool queue"}
      answer: cpu
      explanation: "The shop exports memory (`process_memory_usage_bytes`) and the inventory pool, but no CPU metric. In a real deployment, CPU usually comes from the platform: the Collector's `hostmetrics` or `kubeletstats` receiver, or cAdvisor in Kubernetes, rather than from the application itself."
      hint: "Search Explore for names starting with `process_`, `db_client_` and `cpu`."
hints:
  - "Utilization = busy ÷ capacity. Saturation = what's waiting. Errors = the resource failing (not HTTP errors)."
  - "In Grafana Explore, start typing `db_client_` or `process_` in the metric browser to see what exists."
---

RED describes a service from the outside. When it says something is wrong,
the next question is usually *what is it running out of?* Brendan Gregg's
**USE method** answers that by checking every **resource**: anything with a
finite capacity that work queues for.

| | Question | Example: a DB connection pool |
| --- | --- | --- |
| **Utilization** | How busy is it, as a share of capacity? | used ÷ total connections |
| **Saturation** | How much work is waiting for it? | requests waiting for a connection, and for how long |
| **Errors** | Is the resource itself failing? | failed connection attempts, timeouts acquiring one |

Saturation is the one most often missing, and the most useful. A resource
at 100% utilization with an empty queue is working hard, and fine. A queue
that keeps growing means latency is about to climb.

## What the shop exposes

The inventory service exports its database pool the way the OpenTelemetry
semantic conventions describe:

```promql
# utilization
sum(db_client_connection_count{db_client_connection_state="used"})
  / sum(db_client_connection_count)

# saturation: queue length and wait time
sum(db_client_connection_pending_requests)
histogram_quantile(0.95, sum by (le) (rate(db_client_connection_wait_time_seconds_bucket[5m])))
```

Every service also exports its resident memory as
`process_memory_usage_bytes`. Look these up in **Grafana Explore** as you
answer the questions.

## USE or RED?

Use both, at different layers. RED on every service tells you **that**
users are affected and where. USE on the resources behind it tells you
**why**. Alert on RED, because symptoms are what matter to users, and use
USE to diagnose, and to spot a resource heading for exhaustion before RED
shows it.
