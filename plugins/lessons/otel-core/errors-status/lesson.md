---
title: Errors and span status
summary: Mark failed work as failed, and keep the exception, even when you handle it.
kind: code
minutes: 6
concepts: [span status, record_exception]
assumes: [Creating a span]
runtime: {service: payments-worker}
checks:
- {id: clean-exit, type: exit, title: The program handles the failure and exits cleanly}
- id: failed
  type: span
  title: The declined charge is a `charge-card` span with status `error`
  where: {name: charge-card, status: error}
  count: 1
- id: exception
  type: span
  title: The exception is recorded on that span
  where: {name: charge-card, status: error, exception: true}
- id: others
  type: span
  title: The two successful charges are not marked as errors
  where:
    name: charge-card
    status: [unset, ok]
  count: 2
hints: ['Inside the `except` block, call `span.record_exception(e)`.', 'Then `span.set_status(Status(StatusCode.ERROR, str(e)))`.']
---

When an exception *escapes* a `start_as_current_span` block, the SDK records
it and sets the span's status to **error** for you. But real code usually
**catches** errors to retry, fall back or return a nice message, and then the
span looks perfectly healthy.

A span has a **status** with three values:

| Status | Meaning |
|---|---|
| `unset` | The default. *No opinion*: treated as success. |
| `error` | This operation failed. |
| `ok` | Explicitly successful. Rarely needed; it overrides lower layers. |

When you handle an error, mark the span yourself:

```python
from opentelemetry.trace import Status, StatusCode

except CardDeclined as e:
    span.record_exception(e)                      # adds an "exception" event with the stack trace
    span.set_status(Status(StatusCode.ERROR, str(e)))
```

## Try it

One of the three cards is declined. The code catches the error, so the run
succeeds, but the failed span hides the problem. Record it properly.

> [!NOTE]
> Backends use the status to calculate error rates and to highlight failing
> traces. Elastic marks the transaction as a failure; Jaeger flags the span in red.
