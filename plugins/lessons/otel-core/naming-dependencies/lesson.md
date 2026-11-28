---
title: Naming dependencies
summary: Tell the map which service sits behind a host, so two regions of one API show up as one dependency.
kind: code
minutes: 6
concepts: [peer.service, server.address, service map, dependencies]
assumes: [Semantic conventions]
runtime:
  service: price-fetcher
checks:
  - id: price-api
    type: map
    title: "The map shows one `price-api` dependency, called twice"
    edge: {from: price-fetcher, to: price-api, external: true, calls: 2}
  - id: fx-rates
    type: map
    title: "`fx.example` is named `fx-rates`"
    edge: {from: price-fetcher, to: fx-rates, external: true, calls: 1}
  - id: hosts-gone
    type: map
    title: No bare hostnames left on the map
    nodes_absent: [eu.prices.example, us.prices.example, fx.example]
  - id: hosts-kept
    type: span
    title: "Each call still records its real host in `server.address`"
    where: {kind: client, attributes: {server.address: "~^(eu|us)\\.prices\\.example$|^fx\\.example$"}}
    count: {min: 3}
hints:
  - "Run the starter and open the Map tab: one dashed box per host. You want one per service."
  - "`span.set_attribute(\"peer.service\", ...)` on each client span. Add a `peer` parameter to `http_get`."
  - "Keep `server.address` as it is: it's still the right answer to *where* each call went."
---

Your service calls a price API that runs in two regions, `eu.prices.example`
and `us.prices.example`, and an exchange-rate API at `fx.example`. Neither is
instrumented: you only know about them from your own client spans. Run the
starter and open the **Map** tab: three dashed boxes, one per hostname, and
nothing says two of them are the same service.

Two attributes describe the other end of a call, and they answer different
questions:

| Attribute | Answers | Example |
|---|---|---|
| `server.address` | where did this call connect? | `eu.prices.example`, `10.0.3.7` |
| `peer.service` | which logical service is that? | `price-api` |

They differ whenever several hosts are one service (regions, replicas behind
IPs, a blue and a green deployment) or one host is a gateway in front of
several services. With only `server.address`, a map shows one box per host;
with `peer.service`, one box per service.

```python
span.set_attribute("server.address", "eu.prices.example")  # where
span.set_attribute("peer.service", "price-api")            # who
```

Keep both. `server.address` still matters: when only the EU region is slow,
that's the attribute that shows it.

> [!NOTE]
> `peer.service` is for callees you **can't** instrument: third-party APIs,
> managed databases, another team's service. When the callee is instrumented,
> its own server span names it, and the map uses that instead. The value
> should match the name that service would use for itself, so the two never
> disagree.

## Try it

1. Run the starter and look at the Map tab: `eu.prices.example`,
   `us.prices.example` and `fx.example`.
2. Give `http_get` a `peer` parameter and set `peer.service` from it.
3. Pass `"price-api"` for both prices hosts and `"fx-rates"` for `fx.example`.
4. Run again: two boxes, `price-api` (called 2×) and `fx-rates`. Click the
   `price-api` arrow to open one of the calls in Traces: the host is still there.
