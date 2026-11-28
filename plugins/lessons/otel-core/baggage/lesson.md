---
title: Baggage
summary: Carry business context, like a tenant id, alongside the trace to every service downstream.
kind: code
minutes: 6
concepts: [baggage, context]
assumes: [Context propagation]
runtime: {service: tenant-api}
checks:
- id: tagged
  type: span
  title: '`apply-discount` records the `acme` tenant from that request''s baggage'
  where:
    name: apply-discount
    attributes: {app.tenant.id: acme}
  count: 1
- id: tagged-globex
  type: span
  title: …and the `globex` tenant from the next request's
  where:
    name: apply-discount
    attributes: {app.tenant.id: globex}
  count: 1
- {id: header, type: output, title: The outgoing headers include a `baggage` header, contains: baggage}
hints: ['`ctx = baggage.set_baggage("app.tenant.id", "acme")`, then `token = context.attach(ctx)`.', 'Downstream, `baggage.get_baggage("app.tenant.id")`
    reads it back.']
---

**Baggage** is a set of key/value pairs that travels with the context, the
same way the trace id does, in a `baggage` HTTP header. Any service downstream
can read it.

```python
from opentelemetry import baggage, context

token = context.attach(baggage.set_baggage("app.tenant.id", "acme"))
try:
    handle_request()            # everything in here, and every service it calls, sees the tenant
finally:
    context.detach(token)
```

Baggage is **not** automatically added to spans: it's context, not
telemetry. Read it where it's useful and copy it onto spans yourself.

> [!WARNING]
> Baggage is sent on every outgoing request, including to third parties.
> Never put secrets or personal data in it, and keep it small.

## Try it

Two requests arrive, one from tenant `acme` and one from `globex`. Set
`app.tenant.id` as baggage at the edge for each, and have `apply-discount`
(deep in the call stack, with no tenant parameter) read it and record it as a
span attribute. The code
prints the headers it would send downstream so you can see the `baggage`
header.
