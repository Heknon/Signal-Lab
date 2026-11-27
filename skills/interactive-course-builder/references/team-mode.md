# Multi-user and team mode

A course runs in one of two modes.

| | Open mode | Accounts mode |
|---|---|---|
| For | one person on their own machine | a team on a shared deployment |
| Login | none: a built-in local user | username and password, session cookie |
| Storage | memory or a local database | a real database (Postgres) |
| Who controls faults | the learner | everyone, or admins only (configurable) |

## Requirements

- **Per-person state:** progress (done / known per lesson, last lesson), editor
  drafts (saved as you type, debounced, also cached locally), and run history
  (status, checks, counts; not raw output).
- **Accounts:** the first account becomes an admin; sign-up open or closed;
  admin bootstrap from environment variables or a secret; passwords hashed with
  a slow KDF (scrypt or argon2); session tokens stored hashed, with expiry;
  `HttpOnly` and `SameSite=Lax` cookies, `Secure` behind TLS.
- **Authorisation:** runs are visible only to their owner (and admins). Admin
  endpoints and pages are admin-only. Shared-environment writes can be
  restricted to admins.
- **Run fairness:** at most one active run per person; a concurrency limit on the runner.
- **Shared environment:** the scenario is shared. Record who changed what,
  show it in the UI, and expire faults injected by lessons after a TTL so the
  lab heals itself. Only one experiment or incident runs at a time; everyone
  else can watch it.
- **Game days:** an admin starts an incident; everyone investigates the same
  system; a board shows, per person and question, the time from start to the
  correct answer.
- **Admin page:** people with progress, runs, last lesson and last seen; role
  changes; password reset; delete.

## Data model (minimum)

```text
users(id, username unique, display_name, role, password_hash, created, last_seen)
sessions(token_hash, user_id, created, expires)
progress(user_id, lesson, state, at)            -- state: done | known
last_lesson(user_id, lesson, at)
drafts(user_id, lesson, code, updated)
runs(id, user_id, lesson, code, status, exit_code, duration_ms, checks json, counts json, created)
```

Apply schema migrations at start-up, in order, recorded in a version table.

## Tests

The full flow runs against the real database in CI: sign up (first user is
admin), progress updates (and "known" never downgrades "done"), drafts, admin
listing, logout, wrong password, non-admin forbidden, closed sign-up.

## Scaling note

Live observations (the inspector's data) can stay in process memory, which
means one app replica. That is enough for a team. Document it rather than
pretending to scale.
