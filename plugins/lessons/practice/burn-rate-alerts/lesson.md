---
title: Burn-rate alerts
summary: Create a Grafana alert that pages when the storefront burns its error budget fast, checked over a long and a short window.
kind: task
minutes: 15
concepts: [burn rate, multi-window alert, error budget, symptom-based alerting, Grafana alerting]
assumes: [Error budgets, Grafana Explore]
tools: ["victoriametrics:grafana", "victoriametrics:explore"]
checks:
  - id: rule
    type: backend
    backend: victoriametrics
    verify: grafana_alert_rule
    title: "A Grafana alert rule with “burn rate” in its title"
    title_contains: burn rate
  - id: ratio
    type: backend
    backend: victoriametrics
    verify: grafana_alert_rule
    title: "Its queries compute the storefront's 5xx ratio from rates"
    title_contains: burn rate
    expr_contains: ["rate(", "5..", "storefront"]
  - id: windows
    type: backend
    backend: victoriametrics
    verify: grafana_alert_rule
    title: "It checks a long window (`[1h]`) and a short window (`[5m]`)"
    title_contains: burn rate
    expr_contains: ["[1h]", "[5m]"]
hints:
  - "Alerting → Alert rules → New alert rule. The title must contain “burn rate”, for example “Storefront burn rate”."
  - "Query A uses `[1h]`, query B the same with `[5m]`. Set both to **Instant**."
  - "Remove the default Reduce and Threshold expressions, add a **Math** expression `$A > 14.4 && $B > 14.4`, and make it the alert condition."
  - "Nothing is checked until you **Save rule and exit**."
---

An SLO gives you a better thing to alert on than CPU or error counts: **how
fast the error budget is being spent**. That speed is the **burn rate**:

```text
burn rate = observed error ratio / allowed error ratio      # allowed = 1 - SLO
```

A burn rate of 1 spends the budget exactly over the SLO window. At 14.4, a
30-day budget is gone in about two days (30 ÷ 14.4 ≈ 2.1), and one hour at
that rate uses 2% of it. That's worth waking someone for.

## Why not alert on CPU or a fixed error count?

- **CPU at 90%** is a cause, not a symptom. It might be harmless, or the
  target your autoscaler aims for, and it misses failures that don't use CPU
  at all, such as a dependency returning errors.
- **"More than 10 errors a minute"** means something different at 20 and at
  20,000 requests a minute, so it's either noisy at peak or blind at night.
- **A burn rate** is tied to what users experience (failed requests), scales
  with traffic, and says how urgent things are: a slow burn becomes a ticket,
  a fast burn a page.

## Two windows

A 1-hour window alone is slow to fire and slow to clear: after the problem
is fixed, it keeps firing until the bad hour has scrolled out. A 5-minute
window alone is noisy. Requiring **both** gives an alert that fires when
the long window has seen real budget loss, and stops as soon as the short
window shows it's over. This is the multi-window approach from Google's SRE
workbook.

## Build it in Grafana

Open **Grafana → Alerting → Alert rules → New alert rule**.

**1. Name:** `Storefront burn rate` (the title must contain “burn rate”).

**2. Query A**, data source *VictoriaMetrics*, in **Code** mode, type
**Instant**: the 1-hour burn rate for a 99% SLO.

```promql
(
  sum(rate(http_server_request_duration_seconds_count{service_name="storefront", http_response_status_code=~"5.."}[1h]))
  /
  sum(rate(http_server_request_duration_seconds_count{service_name="storefront"}[1h]))
) / 0.01
```

**3. Query B:** **Add query**, the same expression with `[5m]` in both
places, also **Instant**.

**4. Condition.** Delete the default *Reduce* and *Threshold* expressions.
Add a **Math** expression:

```text
$A > 14.4 && $B > 14.4
```

and set it as the alert condition.

**5. Folder and evaluation.** Pick the *Signal Lab* folder, create an
evaluation group (for example `slo`, every 1m), and set the pending period
to `2m`.

**6.** **Save rule and exit**, then press **Check** here.

> [!TIP]
> Does it fire? Probably not: the storefront normally fails 1 to 2% of
> requests, a burn rate of 1 or 2. Watch query A and B in the rule's preview,
> or in Explore. If a chaos lesson or someone else on this lab injects
> errors into checkout, both climb, B first.

> [!NOTE]
> The SRE workbook pairs several of these: 14.4 over 1h and 5m pages,
> 6 over 6h and 30m pages, and 1 over 3 days and 6h opens a ticket. One rule
> is enough to see the idea.
