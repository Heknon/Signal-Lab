---
title: The four golden signals
summary: Latency, traffic, errors and saturation, how they map to RED and USE, and why you alert on symptoms rather than causes.
kind: quiz
minutes: 8
concepts: [golden signals, symptoms vs causes, alerting, RED, USE]
assumes: [The RED method, The USE method]
quiz:
  questions:
    - id: mapping
      prompt: "Google's SRE book lists four golden signals: latency, traffic, errors and saturation. Which RED letter has no counterpart among them?"
      options:
        - {id: none, label: "None: RED is the first three golden signals; saturation is the extra one, from USE"}
        - {id: rate, label: "Rate"}
        - {id: duration, label: "Duration"}
      answer: none
      explanation: "Traffic is Rate, Errors is Errors, Latency is Duration. The fourth, saturation, is the S of USE: how full the service's most constrained resource is. The golden signals are RED plus one look underneath."
      hint: Match traffic, errors and latency to R, E and D.
    - id: failed-latency
      prompt: "A dependency is down, so checkout fails fast: errors return in 3 ms instead of the usual 80 ms. What happens to an overall p95 latency panel?"
      options:
        - {id: up, label: "It goes up"}
        - {id: down, label: "It can go down, and the service looks faster while it's broken"}
        - {id: same, label: "Nothing: failed requests aren't counted in latency"}
      answer: down
      explanation: "Fast failures pull the distribution down. That's why the SRE book says to track the latency of successful and failed requests separately, for example by filtering on `http_response_status_code`. A latency panel on its own can look better during an outage."
      hint: What do many 3 ms requests do to a percentile?
    - id: symptom
      prompt: "Which of these is a **symptom**, in the sense the golden-signals advice uses it? Choose every one."
      multiple: true
      options:
        - {id: errors, label: "2% of checkout requests return 5xx"}
        - {id: cpu, label: "Inventory CPU at 95%"}
        - {id: latency, label: "p95 for `/api/products` is above 500 ms"}
        - {id: pool, label: "The DB pool has 10 of 10 connections in use"}
        - {id: restart, label: "A pod restarted"}
      answer: [errors, latency]
      explanation: "A symptom is something a user experiences: failed or slow requests. High CPU, a full pool or a restart are possible causes. They might hurt users, or they might be harmless (a pool at 10/10 with no queue is just busy). Page on symptoms, then use causes to diagnose."
      hint: Would a user notice it directly?
    - id: page-on
      prompt: "Which alert should wake someone up at 3 a.m.?"
      options:
        - {id: cpu, label: "CPU above 90% for 5 minutes on any pod"}
        - {id: slo, label: "Checkout is failing fast enough to use up a month's error budget in two days"}
        - {id: restart, label: "Any pod restarted"}
        - {id: log, label: "Any ERROR log line"}
      answer: slo
      explanation: "It's tied to user impact and to urgency. CPU at 90% may be fine or may be the very thing a well-sized autoscaler aims for; restarts and single error lines happen in healthy systems. Cause-based alerts like those page people for nothing, and people learn to ignore pages. The last two lessons in this module build that error-budget alert."
      hint: Which one says users are affected, and that it's urgent?
    - id: saturation-why
      prompt: "If you page on symptoms, why watch saturation at all?"
      options:
        - {id: leading, label: "It is a leading indicator: it tells you a symptom is coming, while there's time to act"}
        - {id: page, label: "It should be paged on too, as a fifth symptom"}
        - {id: none, label: "You shouldn't; it's only for capacity planning"}
      answer: leading
      explanation: "Latency rises when a resource saturates, but only once the queue has formed. Saturation (a filling pool, a growing queue, memory heading for its limit) shows the problem earlier. Put it on dashboards and in low-urgency tickets, not pages, and use it to explain the symptom when one fires."
      hint: Which comes first, the queue or the slow requests?
    - id: traffic-drop
      prompt: "Errors and latency are both perfect, but storefront traffic dropped 70% in the last ten minutes, at 2 p.m. on a weekday. What is the likely state of things?"
      options:
        - {id: good, label: "Healthy: fewer requests, no errors"}
        - {id: bad, label: "Something upstream is broken, such as DNS, the load balancer or the app, and requests are not reaching you"}
        - {id: chaos, label: "The latency chaos was turned off"}
      answer: bad
      explanation: "Requests that never arrive can't fail. A sudden traffic drop with no seasonal reason is often the clearest sign of an outage in front of you. That's why traffic is a golden signal even though it isn't a sign of trouble on its own."
      hint: Can a request that never arrives return an error?
hints:
  - "Golden signals = RED (traffic, errors, latency) + saturation."
  - "A symptom is what a user sees. A cause is what you find when you look for why."
---

The Google SRE book's chapter on monitoring distributed systems suggests
that if you can only measure four things about a user-facing system,
measure these:

| Golden signal | Means | RED | USE |
| --- | --- | --- | --- |
| **Latency** | How long requests take, successful and failed separately | Duration | |
| **Traffic** | How much demand there is | Rate | |
| **Errors** | The share of requests that fail, explicitly (5xx) or implicitly (wrong content, too slow) | Errors | Errors, for resources |
| **Saturation** | How full the most constrained resource is | | Saturation |

The three methods overlap on purpose. RED is the golden signals minus
saturation, written for microservices. USE is the view from underneath, one
resource at a time.

## Symptoms and causes

The most useful idea in that chapter isn't the list. It's the split
between **symptoms** (what users experience: errors, slowness, nothing
loading) and **causes** (why: a full pool, a bad deploy, a dead node).

- **Alert on symptoms.** There are few of them, they always matter, and
  they catch causes you never thought to monitor.
- **Diagnose with causes.** Dashboards of resources, traces and logs are
  for the investigation that follows the page.

A system with a hundred cause-based alerts pages people for things users
never notice, and still misses the outage nobody predicted.
