# Local UI with remote Render PostgreSQL — 2026-11-06

## Measured cause

The UI/backend run on the workstation while PostgreSQL is on Render. A warmed `SELECT 1` round trip measured approximately **0.309 seconds**; a fresh connection measured **5.384 seconds**. Multiple sequential SQL statements amplify this delay even with empty CRM registers. These observations are from this connection/session, not a promised service latency.

The original dashboard handler performed 20 SQL statements and took 6.295 seconds, excluding HTTP/authentication/rate-limit work. Metrics performed 11 statements and took 3.569 seconds. The Settings screen also fetched settings a second time after the authenticated provider had already loaded them. Development StrictMode replayed startup effects and generated additional duplicate reads. Waiting for the staff directory unnecessarily blocked opening the whole workspace.

## Changes

- Settings opens immediately from the provider's saved snapshot. The existing **Reload saved settings** action still fetches explicitly; version checks still reject stale saves.
- Settings and staff-directory startup requests are shared within a provider during StrictMode replay. They are scoped to the user/retry, not stored in a global or persistent account cache. Slow staff-directory requests no longer block workspace display, and old roster labels are cleared on provider initialization.
- Overview requests are deferred one event-loop turn so StrictMode can cancel its first setup before any request is sent.
- Metrics use four scoped aggregate SQL statements instead of eleven. Active/high lead totals share a grouped query; follow-up view totals share one conditional aggregate; customer totals/conversions share one query. IST day boundaries are converted to UTC consistently for PostgreSQL and SQLite.
- Settings shared/personal data load in one SQL statement. Empty customer/quotation/follow-up batches skip unnecessary enrichment queries. Empty overview now uses nine SQL statements instead of twenty; populated previews remain bounded and batch-enriched.
- PostgreSQL rate budgets are claimed in a sorted, conditional `INSERT ... ON CONFLICT ... RETURNING` batch. A successful batch uses one claim statement; timeout configuration uses one statement instead of two. Denied budgets retain their count/window, successful budgets still count even if another budget blocks the request, and expiry/retry behavior is preserved. SQLite and unusual duplicate-key budget inputs retain the previous path. Database-backed limits, fail-closed storage handling, login enforcement and per-request authentication remain enabled.

## Verification

Read-only CRM measurements on the same Render connection after optimization:

| Handler | SQL statements before → after | Timing before → after |
| --- | --- | --- |
| Settings response | 2 → 1 | 0.637s → 0.426–0.685s |
| Metrics | 11 → 4 | 3.569s → 1.234–1.497s |
| Empty overview | 20 → 9 | 6.295s → 2.997–3.192s |

These are handler timings, not complete browser/HTTP response timings. Connection setup, authentication, security budgets, transfers and network variation add overhead. A local backend connected to a remote database will still experience WAN latency; a genuinely local PostgreSQL database or a backend colocated with the Render database avoids those workstation-to-database round trips.

Checks passed:

- 117 existing backend tests plus two new query-count/IST-boundary/Staff-scope tests.
- 55 frontend service tests, ESLint and production build.
- 19 isolated Chrome UI tests, including a deliberately unresolved staff roster, one settings startup request, no additional GET on Settings entry/re-entry, and explicit Reload behavior.
- Actual PostgreSQL batch checks for acceptance, exact limits, denied counters, mixed windows and expiry. Twelve concurrent attempts across independent connections allowed exactly five and limited seven, with no storage errors.

The rate-limit integration check used an internally generated `qa_latency_<uuid>` schema containing only its test budget table; it was removed and absence verified. CRM handler measurements were read-only. Existing customers, leads, quotations, follow-ups, accounts and their assignments were not edited. No schema migration, real login or production deployment was performed.

Repeat PostgreSQL timing/security checks from `backend` with database access and schema-creation privileges:

```powershell
.\venv\Scripts\python.exe -B scripts\verify_latency_optimizations.py
```

Restart the local backend if it is not running with reload, then refresh the browser to use the updated code.

SQL reference: [SQLAlchemy PostgreSQL conditional upsert](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert).
