# Customer relationships and bounded UI queries — 2026-11-06

## Implemented

- Lead and Quotation now have nullable indexed `customer_id` foreign keys. Follow-ups inherit the profile ID from their lead. Profile names remain display/document snapshots; renaming a profile does not rewrite old enquiries or retained PDFs.
- Migration `20261105_0011` matches legacy names/aliases using case folding and whitespace normalization. Only a single globally matching profile is linked. Duplicate/ambiguous names remain unlinked. Linked row versions advance so old open editors conflict safely. No profiles are auto-created or merged. Lead names support the same 120-character limit as profiles.
- New enquiries/quotation forms explicitly select a saved profile through a paged search. Free-text entries remain unlinked. A profile ID does not grant Staff access to any related enquiry, quotation or profile; existing independent assignment rules still apply.
- Customers > **Link existing records** lets administrators review paged unlinked enquiries/quotations, pick a profile explicitly and confirm. Uncheck **Unlinked only** to correct/remove existing links. The versioned `PUT /api/customer-links/{leads|quotations}/{id}` route also supports retained archived quotation metadata without rewriting PDFs. Changes are audited. Archived documents are not included in active UI registers.
- Customer deletion protects ID relationships, archived quotations and unresolved legacy name references. Foreign keys protect linked deletion races.
- Lead/quotation/follow-up collection APIs accept `customerId` and `unlinked`; access scope is applied before filtering/counting. Customer directories show saved profiles; unlinked enquiry names remain discoverable in Leads, Quotations and the Admin review screen.

## Large-data browser behavior

- Dashboard and alert polling use `/api/workspace/overview`: SQL totals/pipeline, five recent leads, three queued tasks and at most 20 alerts per category. Notification flags apply before limits; overdue tasks cannot crowd out enabled future reminders when overdue alerts are disabled. Each task's own reminder lead time is respected.
- `/api/workspace/metrics` supplies scoped SQL card counts. Register counts retain division/staff scope independently of the register's text/status/date filters.
- Customers, Quotations and Follow-ups now use server pagination/search, as Leads already did. Search requests are debounced/cancelled; pages reset when filters change. No core register, dashboard or global alert component traverses all pages into browser memory.
- Customer detail activity tabs request bounded related-record pages by ID, with pagination and exact totals. History contains profile changes; follow-up notes remain with their tasks and PDF revisions with their quotation viewer.
- Quotation lists request `summary=true`: no line items, payment terms or retained PDF snapshots/history in list payloads. Latest PDF metadata and version counts are batch-loaded. Full documents/history load only when viewing/editing one quotation. Follow-up page rendering batch-loads its lead/account references.
- Customer/lead selectors request at most 20 results and require explicit ID selection to distinguish duplicate names. Changing the free-text customer name clears its selected ID.

## Verification

- 110 backend tests pass, including six new tests that exercise duplicate names, renames, Staff scope, link conflicts, archived links, PDF preservation, bounded/scoped SQL totals, reminder settings and SQLite migration upgrade/backfill/downgrade.
- 55 frontend unit/service tests pass. Twelve existing responsive Chrome tests pass across 320/375/768/1024/1440 pixels; five additional browser tests verify bounded page requests against 10,000-record fixtures, server search/reset, on-demand 20-result selectors and explicit overview errors instead of false zero totals. Browser APIs are synthetic and cannot write real CRM records.
- Frontend lint and production build pass.

## Required deployment step / verification limit

The configured PostgreSQL address could not resolve from this PC when live verification was attempted. **No live migration was applied or PostgreSQL integration result claimed.** `.env`, credentials, accounts, assignments and real CRM records were not changed. Run from an environment with database access, before deploying code that needs the new columns:

```sh
cd backend
python -m alembic upgrade head
```

`scripts/verify_customer_links.py` can apply/check this migration with preservation assertions and then run PostgreSQL API checks in a disposable `qa_customer_links_<uuid>` schema. It requires schema-creation privileges. It checks account/assignment/document/PDF preservation and removes its QA schema. It does not modify connection configuration. PostgreSQL validation remains pending until this script succeeds against a reachable database.

The SQLite/unit/browser results do not substitute for a realistic load test, live-backend browser flows or staging. Full report/export payload optimization is a separate remaining step. Real backup scheduling/offsite configuration remains deferred as requested.

## Role permissions follow-up

The confirmed policy now uses common Staff permissions in Settings > Roles & permissions, replacing individual switches. Admin access stays ON; the Staff Quotations checkbox controls all current/future Staff accounts. See [current implementation](QUOTATION-ACCESS-REPORT.md). Existing record assignment scope remains an additional rule.
