# Backend pagination/search and concurrent edits — 2026-11-05

Implemented bounded, permission-scoped SQL pagination/search for Leads, Customers, Follow-ups and Quotations, including Upcoming/Overdue collections. Lead/customer edits, deletes and CRM assignments now use version preconditions; Follow-up version checks are mandatory on HTTP mutations. Quotation/settings/user concurrency checks remain enforced.

## Collection contract

Use `GET /api/leads?paged=true&page=1&pageSize=25&q=firmware&division=MMC` (same pagination parameters on the other collection routes).

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 25,
  "pages": 1,
  "hasMore": false
}
```

Default page size is 100; accepted size is 1–100, page 1–100000, search text at most 120 characters. Empty and out-of-range pages return empty items with the filtered total; an empty result has one page. For existing clients, omitting `paged=true` retains an array response, **bounded to the requested/default page**. It no longer returns an unbounded register. New clients should always request metadata.

| Module | Additional filters |
| --- | --- |
| Leads | division, assigneeUserId, status, priority, source, exact customer |
| Customers | division, assigneeUserId, Company/Individual type |
| Follow-ups | division, assigneeUserId (lead owner), status, leadId, customer, assignedTo, ISO date, view |
| Quotations | division, assigneeUserId, status, Created/Uploaded source, customer |

Follow-up views are All/Today/Overdue/Upcoming/Completed. Calendar days use IST; Upcoming view means dates after today, while the existing `/upcoming` endpoint retains its instant-based meaning (pending at or after now). Archived follow-ups/quotations are excluded. Quotation status filtering applies effective Expired status to past-validity Sent documents.

Search is case-insensitive SQL substring matching over relevant names, contacts/reference JSON, descriptions/purpose and quotation numbers. `%`, `_` and backslashes are escaped as literal search characters, not wildcard syntax. Unknown query fields and invalid enum/date/page values return 422. Scope applies before pagination/counting, so requesting another Staff ID never broadens access or exposes hidden totals. Lists use deterministic timestamp + unique-ID sorting and corresponding ordering indexes. Count queries remain in SQL; the backend does not load all records to slice a list.

## Mutation contract

- Lead/Customer PUT: include positive integer `expectedVersion` from the record originally opened.
- Lead/Customer/Follow-up DELETE: include `?expectedVersion=N`.
- Follow-up PUT: include `expectedVersion`, including completion/rescheduling.
- CRM assignment PUT: send `expectedVersion` as well as the previous assignee ID. Assignment directory rows and mutation responses include `version`.

Missing HTTP preconditions return **428**; a stale version returns **409**. Ownership is checked before record-specific preconditions, preserving 403/404 behavior for forbidden or hidden records. Changes claim the version with an atomic conditional UPDATE, retain row locks until commit and then save details in the same transaction. Failed validation rolls the claim back. Deletes claim the matching version before removal/archive. Reassignment advances the record version, invalidating previously opened forms even if an assignee changes back to the original account (ABA).

Trusted direct Python service calls keep an optional-version compatibility path; this is not available through HTTP because the authenticated CRM dependency supplies the actor. Explicit invalid/null versions still fail validation. Existing Quote/User/Settings APIs retain their original versioned contracts.

The frontend captures the opened Lead/Customer version, preserves it through form submission, and sends versions for deletion/assignment. It does not fetch the newest version to force a stale save through, and never automatically retries a conflicting mutation. Reload the record and review the other editor's changes before retrying. Follow-up completion and optional next task remain atomic, so a duplicate completion cannot create another next task.

## Frontend integration and practical limits

The **Leads register uses server pagination and debounced server search**, with Settings-controlled page size, reset-to-first-page when filters change, request cancellation, out-of-range-page recovery and reload controls. Its totals come from the filtered server count.

Other existing full-data consumers (Dashboard, customer directory/related activity, quotation and follow-up views, picker data) explicitly traverse bounded pages through the shared API helper. This preserves existing complete totals/derived profiles instead of silently treating page one as the whole dataset. The helper rejects duplicate IDs/changing totals or malformed pages rather than presenting a partial list as complete. Those consumers still retain full result sets in browser memory and their current UI pagination remains local. Full UI migration to targeted server queries/aggregates is still needed for very large datasets; this work completes the selected **backend** collection contract, not end-to-end large-dataset optimization. Reporting/export routes remain separate full-result endpoints.

Offset pagination is deterministic when data is unchanged, not a transactional snapshot across requests. Concurrent inserts/deletes/reassignment can change page membership; the full-list helper detects common count/duplicate inconsistencies and asks for reload, but cannot guarantee a cross-request snapshot. Deep offsets/counts and substring/JSON searches require later capacity measurement; a leading substring search is not a full-text index. Retained per-record histories/PDF revision metadata are not separately paginated here. Existing request budgets still apply when full consumers load multiple pages.

## Verification and migration

- **94 backend tests**, including seven new scenarios: bounded stable/scoped pages and wildcard escaping; customer/module filters; follow-up time views and quotation expiry; stale Lead changes/deletes; stale Customer contacts/history; completion duplication; assignment version/ABA protection.
- **53 frontend tests** cover query encoding, complete page traversal, inconsistent/malformed results and original-version mutation payloads. ESLint and production build pass. Browser click/responsive QA is still pending.
- Migration `20261105_0010` applied to local PostgreSQL: Lead/Customer versions start at 1, list ordering indexes are added. ORM/schema comparison found no differences. Existing table counts, full login-account rows and all previous lead/customer fields/assignments were preserved.
- PostgreSQL pagination returned 125 unique results as **50 / 50 / 25**. Separate physical connections raced Lead edits, Customer full-form edits and Follow-up completion: each race produced **one 200 and one 409**, with the winning fields preserved and exactly one next task.
- Integration QA used a generated schema and test account, then removed the exact schema and verified its absence. No real account/CRM record was edited. Re-run with `venv/Scripts/python.exe -B scripts/verify_pagination_versions.py` from backend.

Next operational priority remains backups/restore and monitoring, followed by realistic load testing, staging and production setup. Counter/session cleanup, durable notifications, SMTP activation, reviewed old-data migration and the optional product/logo/signature features remain pending. Stable customer foreign keys are still needed to replace legacy name-based relationship checks; this version policy does not fix that separate relationship race.

References: [FastAPI query parameter models](https://fastapi.tiangolo.com/tutorial/query-param-models/) and [SQLAlchemy version-counter principles](https://docs.sqlalchemy.org/en/21/orm/versioning.html).
