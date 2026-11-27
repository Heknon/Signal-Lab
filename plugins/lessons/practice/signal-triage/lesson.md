---
title: Signal triage
summary: Twelve concrete needs. For each, pick the signal that serves it best, or decide not to record anything.
kind: quiz
minutes: 12
concepts: [signal choice, metrics vs spans vs logs, span events, baggage, profiling, cardinality, PII]
assumes: [Spans, Metrics, Structured logs]
quiz:
  questions:
    - id: dashboard-rate
      prompt: "A service already runs with FastAPI auto-instrumentation. A teammate wants to add an `api.requests` counter by route and status code, for a requests-per-second dashboard."
      options: &signals
        - {id: metric, label: "A metric"}
        - {id: span, label: "A span, or an attribute on one"}
        - {id: event, label: "A span event"}
        - {id: log, label: "A log record"}
        - {id: baggage, label: "Baggage"}
        - {id: profile, label: "A profile, not span/metric/log telemetry"}
        - {id: none, label: "Nothing new: don't record it, or it's already covered"}
      answer: none
      explanation: "The HTTP server instrumentation already records `http.server.request.duration`, a histogram by route, method and status code. Its `_count` series is a request counter: `rate(http_server_request_duration_seconds_count[5m])`. A second counter doubles the series for no new answer. Check what you already have before adding anything."
      hint: What does HTTP server auto-instrumentation already emit for every request?
    - id: slow-query
      prompt: "A request sometimes takes 3 s. It runs about 40 SQL queries. You need to know which one took the time."
      options: *signals
      answer: span
      explanation: "Where time went inside one request is what a trace shows. Database instrumentation creates a client span per query with the statement and duration, so the slow one stands out in the waterfall. A metric would tell you queries got slower on average, not which one did in this request."
      hint: You care about one particular request, and the order and duration of the work inside it.
    - id: tier-filter
      prompt: "You want to filter slow traces by the customer's subscription tier (free, pro, enterprise)."
      options: *signals
      answer: span
      explanation: "Set `app.user.tier` as a span attribute on the request span. Attributes on spans are what trace search filters on. With three values it would be fine on a metric too, but the question is about traces."
      hint: Trace search filters on something that's attached to each span.
    - id: cache-miss
      prompt: "During a request, the cache sometimes misses and falls back to the database. You want to see exactly when it happened on the trace timeline, with the cache key's namespace."
      options: *signals
      answer: event
      explanation: "A span event is a timestamped point inside a span, with its own attributes: `span.add_event(\"cache.miss\", {\"app.cache.namespace\": ns})`. It shows up at the right moment in the waterfall. The database call that follows gets its own span from the database instrumentation. To count misses over time, use a metric as well."
      hint: It's a moment, not a duration, and you want it inside the request's timeline.
    - id: tenant
      prompt: "The edge gateway knows the tenant id. Five services further down the call chain each need to put it on their own spans."
      options: *signals
      answer: baggage
      explanation: "Baggage is context that propagates with the request, in a header, to every downstream service. Each service reads it and sets it as a span attribute (the baggage span processor can do that automatically). It is not telemetry by itself: it's sent on every outgoing call, so keep it small and never put secrets in it."
      hint: The value has to travel across process boundaries with the request.
    - id: cpu
      prompt: "One span takes 2 s on its own: it calls no other service and no database. The pod's CPU is at 90%. Which function is burning it?"
      options: *signals
      answer: profile
      explanation: "A CPU profiler samples stacks and tells you which functions use the time. Adding spans around functions until you find it is slow and changes what you measure. OpenTelemetry has a profiles signal in development; until then use a continuous profiler such as Pyroscope or py-spy."
      hint: The trace already told you which span. The question is now about code inside it.
    - id: bodies
      prompt: "Someone proposes recording the full request and response body of every API call as span attributes, in case they're needed."
      options: *signals
      answer: none
      explanation: "Bodies are large, often contain personal data or credentials, and are almost never read. Span attribute limits truncate them anyway. If something specific in them matters, record that as a small attribute, such as a body size, an item count or a validation error code."
      hint: '"In case we need it" is the cost argument backwards. What would you actually query?'
    - id: startup-config
      prompt: "At startup, the service reads its configuration: pool size, enabled feature flags, the region. You want it on record for when behaviour changes after a deploy."
      options: *signals
      answer: log
      explanation: "A single structured INFO log at startup, with the values as attributes. It happens once per process, so a metric would be a series with one point, and there is no request to attach a span to. Static facts such as the version and region belong in resource attributes, which every signal then carries."
      hint: It happens once per process, not per request.
    - id: health-check
      prompt: "The load balancer calls `/healthz` on every pod every 2 seconds. Auto-instrumentation creates a span for each call."
      options: *signals
      answer: none
      explanation: "On a quiet service, health checks can outnumber real requests, and they answer nothing. The load balancer already tracks failed checks. Exclude the route in the instrumentation (`OTEL_PYTHON_FASTAPI_EXCLUDED_URLS=healthz`) or drop those spans in the Collector."
      hint: Who reads these spans, and what do they learn from them?
    - id: cart-size
      prompt: "Product wants the distribution of cart sizes across all checkouts. Support wants the cart size of one customer's slow checkout. Choose every signal you need."
      multiple: true
      options: *signals
      answer: [metric, span]
      explanation: "Two questions, two signals. The distribution across all checkouts is an aggregate: a histogram metric, unsampled and cheap. One customer's checkout is an individual event: `app.cart.items` on the checkout span. Spans could approximate the distribution, but they're usually sampled and costly to aggregate."
      hint: One question is about all checkouts, the other about one.
    - id: bad-record
      prompt: "A batch job processes 10,000 records under one `import batch` span. One record is malformed and skipped. You want to know which, and why. Choose every signal that fits."
      multiple: true
      options: *signals
      answer: [event, log]
      explanation: "Either works: a WARNING log with the record id and reason, emitted inside the batch span so it's correlated, or a span event on the batch span. A log survives trace sampling and is easy to search; an event sits on the timeline. What you shouldn't do is create 10,000 spans, one per record, to catch one failure."
      hint: Don't create a span per record. What can attach a detail to the one span that exists?
    - id: email
      prompt: "Support wants to find a customer's traces. Someone suggests putting the customer's email address on every span."
      options: *signals
      answer: none
      explanation: "Don't record the email. It's personal data, it ends up in a system with different access rules and retention than your user database, and erasure requests become hard. Use the internal, pseudonymous `app.user.id`; support can look up the id from the email in the admin tool."
      hint: Is there an identifier that finds the same traces without the personal data?
hints:
  - "Aggregates over all requests are metrics. One request in detail is a span. Something that happened, with context, inside or outside a request is a log or a span event."
  - "Several answers are \"don't record it\". Think about who reads the data, and whether something already records it."
---

Knowing how to emit each signal is the easy part. The judgment is in
choosing which one, or none. A rough guide:

| Signal | Good for | Costs grow with |
| --- | --- | --- |
| Metric | Counts, rates, distributions over **all** requests; alerts; long retention | Number of series (attribute combinations) |
| Span | **One** request in detail: timing, causality, high-cardinality attributes | Requests × spans per request (so it's often sampled) |
| Span event | A timestamped moment inside a span | Same as spans |
| Log | Something that happened, with context; also outside any request | Volume in bytes |
| Baggage | Carrying a value to downstream services | Header size on every call |
| Profile | Where CPU and memory go inside the code | Sampling rate |

And one more option for every need: **record nothing**, because it's
already covered, nobody will read it, or you're not allowed to keep it.

Each question below describes a real need. Pick the signal that answers it
best. A few accept more than one answer and say so.
