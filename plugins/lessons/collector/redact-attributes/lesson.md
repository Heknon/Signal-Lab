---
title: Redacting sensitive attributes
summary: Delete card numbers and hash email addresses before telemetry leaves your network.
kind: collector
filename: collector.yaml
minutes: 7
concepts: [attributes processor, PII, hashing]
assumes: [Collector pipelines]
runtime:
  service: payments
collector:
  settle_s: 2
checks:
  - id: no-card
    type: span
    title: No span carries `app.card.number`
    where: {attributes: {app.card.number: "*"}}
    count: {max: 0}
  - id: hashed
    type: span
    title: "`user.email` is replaced by a hash on every `charge` span"
    where: {name: charge, attributes: {user.email: "~^[0-9a-f]{40,64}$"}}
    count: {min: 10}
  - id: kept
    type: span
    title: Useful attributes like `app.payment.amount` survive
    where: {name: charge, attributes: {app.payment.amount: "*"}}
    count: {min: 10}
hints:
  - "The `attributes` processor takes a list of `actions`, each with a `key` and an `action`."
  - "`action: delete` removes a key; `action: hash` replaces its value with a hash."
---

Telemetry gets copied everywhere: backends, dashboards, exports,
screenshots in tickets. Personal or payment data that lands there is a
compliance problem that's hard to clean up.

The Collector is the last place you control before data leaves. The
**attributes** processor rewrites span, log and metric attributes:

```yaml
processors:
  attributes/scrub:
    actions:
      - key: app.card.number
        action: delete
      - key: user.email
        action: hash        # same input → same hash: you can still group by user
```

Hashing keeps the attribute useful (*how many failures for this user?*)
without storing who the user is. Other actions are `insert`, `update`,
`upsert` and `extract`.

> [!NOTE]
> The `redaction` processor takes the opposite approach: an allow-list of
> keys, with everything else removed, plus regex masking of values. Use it
> when you can't list every sensitive key in advance.

## Try it

`traffic.py` records card payments with an email address and a full card
number. Scrub them.
