# ENGEN CRM API

## Current source state - 2026-11-10

Email OTP recovery and Gmail API delivery are implemented and verified; the user confirmed the deployed reset flow works. Backend/frontend source must be released together. Database migration head is `20261110_0017`. See [current recovery behavior](audit/PASSWORD-RECOVERY-REPORT.md) and [remaining work](audit/PENDING-WORK-REVIEW-20261106.md); earlier counts and pending lists below are historical implementation notes.

Quotation PDFs use the packaged backend asset `app/assets/engen-logo.png`, copied unchanged from the ENGEN frontend logo. The backend Docker build includes it without depending on a frontend directory. The existing show-logo toggle and company-text fallback remain supported. Only newly generated PDFs/revisions use this asset; previously stored PDF bytes remain unchanged. Tests verify logo embedding on every page, disabled-logo rendering and the missing-asset fallback.

Run commands from `D:/CRM-TOOL/backend`.

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
# Local setup: copy .env.example to .env.local once, then set your local DATABASE_URL.
.\venv\Scripts\python.exe -m alembic upgrade head
# For the first administrator, run once in your own interactive terminal:
.\venv\Scripts\python.exe -m app.commands.create_admin
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Local development reads `backend/.env.local` using an absolute path. The old `.env` is preserved but is no longer loaded. Render/production reads process environment variables only, including `DATABASE_URL`; it never loads local dotenv files. See [local and Render configuration](audit/ENVIRONMENT-CONFIGURATION.md).

When local development intentionally uses the Render database, network round trips still add latency. Duplicate Settings/startup reads and unnecessary sequential SQL were reduced; [measurements, checks and remaining network overhead](audit/CLOUD-DATABASE-LATENCY.md) document the improvement. Restart the backend after updating the code.

## Existing databases

The initial migration creates the two tables; it does not modify or erase an existing installation. If tables already exist without Alembic history, compare all columns/types/nullability/indexes against the initial models and migration first. Only after confirming an exact match, baseline with `python -m alembic stamp 20261104_0001` instead of applying the initial create-table migration, then upgrade head. If the schema differs, prepare a targeted migration.

On 2026-11-04 the configured local PostgreSQL database was upgraded transactionally through `20261104_0006` (persistent Settings). Existing accounts, password hashes, roles and all CRM records were retained. Schema/model comparison returned no differences. Do not re-baseline this database. No default credentials are installed. On a fresh installation, create the first Owner using the interactive command above; after an Owner exists, manage additional accounts from Settings > Users & access.

## Checks

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The 104 automated tests exercise CRUD handlers, schemas, migrations, quotation/report HTTP requests, authentication, user management and five Settings scenarios against isolated SQLite databases. Settings checks cover Owner permissions, personal-data isolation, stale-save atomic rollback, live lead requirements, automatic quotation numbering, PDF issuer snapshots, approval gates and self-service password changes. Business HTTP tests sign in through the real login endpoint rather than disabling authentication. On Windows, the FastAPI test client requires local socket-pair access; restrictive sandboxes can block its event loop before any request executes. `/api/health` is public; `/api/db-health` requires a session and returns 503 if the database is unavailable.

PostgreSQL integration checks verified authentication, user management, Settings privacy/permissions, quotation defaults/numbering and approval rules in rolled-back temporary schemas. No temporary integration accounts, schemas, settings or sessions remained. The separate live demo script retains labelled sample CRM data. Frontend checks: 55 service/date/export/auth/user/settings tests, ESLint and production build. Updated Settings-driven quotation PDFs were rendered and visually checked. Isolated headless Chrome UI checks now pass with synthetic API data; see audit/UI-RESPONSIVE-REPORT.md. Real-account browser flows against the live backend remain unverified, and the native Windows browser URL restriction still applies.

## Current scope

Leads (5), Customers (5), Follow-ups (7), Quotations (9), Reports (4), Authentication (8), User management (4), Settings (3) and CRM assignment (2) and Owner operations status (1) APIs are implemented: 48 business/auth/settings/operations endpoints plus three health/readiness endpoints. Owner-only account/shared-settings permissions are enforced; durable background delivery and other production-readiness work remain pending. The client uses same-origin `/api` requests; Vite proxies them to `127.0.0.1:8000` in development, and production must configure its HTTPS reverse proxy. Stable customer/user foreign keys for legacy business-name links remain future work.

## Authentication: first readiness step

The local migration has added `users`, `auth_sessions`, `access_tokens` and `refresh_tokens`. Old browser Settings staff entries are not automatically imported into login accounts. On a fresh installation, create the first administrator/Owner with `python -m app.commands.create_admin`. It asks for email, display name and an 8-128-character password twice through a hidden prompt, hashes it with Argon2id and refuses to overwrite an existing email. Password whitespace is significant. No further administrators can be created with that command after an Owner exists; the Owner uses Settings > Users & access. There is no public registration or first-admin HTTP endpoint.

| Method | Path                        | Purpose                                                               |
| ------ | --------------------------- | --------------------------------------------------------------------- |
| POST   | `/api/auth/login`           | JSON email/password; issue an access token and refresh cookie         |
| POST   | `/api/auth/refresh`         | Rotate refresh cookie and issue a new access token                    |
| GET    | `/api/auth/me`              | Current active user's profile                                         |
| POST   | `/api/auth/logout`          | Revoke the current session and remove its cookie                      |
| POST   | `/api/auth/logout-all`      | Revoke all sessions belonging to the current user                     |
| POST   | `/api/auth/change-password` | Verify current password, change own password, revoke all own sessions |

Access tokens are random opaque Bearer tokens, not JWTs. They live only in frontend memory and expire after 15 minutes by default; database queries check session revocation and user activation on every authenticated request. Refresh tokens use a host-only HttpOnly, SameSite=Strict cookie scoped to `/api/auth`, expire after an absolute seven days by default, and rotate on each use. Only SHA-256 token hashes are stored in the database. Consumed refresh hashes remain recorded so replay revokes that session. Multiple short-lived access tokens may coexist within one session to support multiple tabs; logout invalidates them all immediately. The frontend deduplicates simultaneous refresh attempts and uses Web Locks when available to serialize cookie rotation across tabs. Lost refresh responses or races on browsers without Web Locks may require signing in again.

Cookie-based auth POST endpoints require `X-CRM-Request: 1`; browser Origins must match `ALLOWED_ORIGINS`. CLI clients omit Origin but must send the header. Business routes accept Bearer access tokens, not cookie-only authentication. All CRM data, report and PDF endpoints plus database health now require authentication; application health remains public. Swagger is available locally and describes Bearer auth. The browser automatically restores a valid session, refreshes/retries an expired API request once, and returns to login after session expiry. A failed logout does not pretend that the server session was revoked.

Local development uses `ENVIRONMENT=development`, `COOKIE_SECURE=false` and explicit localhost origins. For production, set `ENVIRONMENT=production`, `COOKIE_SECURE=true` and `ALLOWED_ORIGINS=["https://your-crm-domain"]`; startup rejects insecure production cookie/origin settings. Serve UI and `/api` under the same HTTPS origin. Do not use Vite's development server in production. The actual `.env` was preserved; examples show configurable values without real credentials.

Owner-only user-management permissions and self-service password changes are implemented. Password changes require the current password and sign out all of that user's sessions. Login/API budgets and request-size/time guards are implemented. Session/counter cleanup jobs, monitoring and load tests remain pending. Keep the installation local until those steps are complete. Old browser-only settings/referral registries and legacy IndexedDB records are not authentication sources. Logout-all has an API; its separate account-settings button remains pending.

## Users & access: Owner and two-admin policy

Settings > Users & access now displays actual login accounts and saves changes immediately through the API. Its old browser-only staff-entry form is removed.

- Owner (first administrator): sees all Admin/Staff accounts; creates accounts, edits details, resets other users' passwords, changes roles and activates/deactivates users.
- Second administrator: sees a staff-only directory and can manage common Staff module access in Roles & permissions; cannot create accounts or modify roles/details/passwords.
- Staff: sees only their own login profile and cannot manage any accounts.
- Maximum two Admin accounts, counting the Owner and including inactive administrators. Once both slots are occupied, new users default to Staff and the Admin option is disabled. Demoting the second administrator frees that slot.
- The Owner row is protected from all edits/deactivation on this page. Owner transfer/self-service profile changes are outside this feature.

GET `/api/users` returns the server-controlled directory scope, management capability and visible accounts. GET `/api/users/{id}` enforces the same read permissions (with own-profile access). POST `/api/users` and PUT `/api/users/{id}` require the Owner. PUT requires `expectedVersion`; stale edits return 409. Passwords are write-only, require 8-128 characters and are never listed. Account deletion is not offered; deactivate instead. Email/role/password/activation changes revoke the target's existing sessions; they must sign in again.

Migration `20261104_0005` designates the earliest existing Admin by created date/id as Owner. It refuses installations with more than two Admins or an inactive first Admin, rather than silently demoting or enabling anyone. Distinct database Admin slots 1/2, unique/check constraints, and Owner constraints prevent concurrent requests or alternate creation paths from introducing a third administrator. Slot 1 is reserved for the active Owner. Server-generated `user_audit_events` record actor, target and before/after details, without plaintext passwords or password hashes.

These account rules do not yet restrict staff to assigned CRM leads. Users can edit their own display name/phone/designation in My profile and change their own password after current-password verification; email/role/activation are not editable through that endpoint. Existing login credentials were retained. Refresh the page to load updated profiles/directories.

## Persistent Settings and connected defaults

GET `/api/settings` returns the signed-in user's profile/preferences plus shared company, divisions, lead and quotation defaults. PUT `/api/settings` saves versioned changes; GET `/api/settings/divisions` returns the six fixed divisions: MMC, nemilink, ClearCode Labs, ENGEN, Visotonics and Overview. All require login. Migration `20261104_0006` adds singleton `workspace_settings` and user-keyed `user_preferences`. Old localStorage settings are preserved but are not imported automatically; review and enter needed values in Settings. Settings now follow a login across devices. Refresh/reload saved settings to receive changes made from another device.

- Owner: edits company/division details and business defaults. Other users can read them but cannot change them, including through direct API calls.
- Each user: edits their own display name, phone, designation, in-app alert preferences and workspace display preferences. Login email is read-only here. Roles/passwords are never accepted by the profile Settings payload.
- Optimistic versions cover shared, personal and profile data. A stale save returns 409; combined saves roll back fully rather than partially applying data. Reload saved settings before retrying. Setting changes add server-generated audit records.
- Lead default status/priority apply to omitted API fields and new-lead forms. Contact/description requirements are enforced by the backend on creation and relevant field edits. A contact requirement means nonempty contact-person/details text, not a phone/email parser. Suggested follow-up days and reminder minutes initialize new task forms. Existing tasks retain their explicit dates/reminder values. Custom sources are shown alongside Direct Enquiry/Referral/Known Network/Other. The staff pickers use visible active real accounts.
- Blank structured quotation numbers allocate a database-locked counter using division prefix, or the fallback prefix, plus issue year and sequence. Numbers are assigned when saved; imported PDFs still require their original number. Counters cannot be decreased; archived numbers remain reserved. Allocation and quotation/PDF storage commit together. Allocating a number advances the shared Settings version, so an open Settings form may require reloading before saving.
- New quotation forms/API defaults use configured currency, validity, tax and standard terms. Explicit per-quote values remain editable. Generated PDF revisions snapshot company contact details, division address/GST, and logo/signature-area preferences. Existing PDF revisions remain unchanged. The signature option adds an empty signing area, not a digital signature. When Owner approval is required, only the Owner can mark quotes Sent or Accepted; edits/uploads return to Draft. This is an Owner status gate, not a separate approval-inbox workflow.
- Sidebar mode/default division apply to the user's workspace; display date formats apply to follow-ups, quotations and report timestamps. Rows per page applies to the main CRM registers and report tables; it is client-side pagination, not the future backend traffic/pagination work.
- In-app toggles filter high-priority lead alerts, upcoming/overdue task reminders and Sent/Expired quotation alerts. Quote expiry considers the next two days and already expired quotes. Sound requires a browser interaction/audio support. CRM must stay open; background email/WhatsApp/push delivery is not implemented. The old unsupported lead-assignment toggle is replaced with the actually supported priority-alert toggle.

Product catalogue management, arbitrary division creation/renaming, custom logo uploads, digital signatures, background delivery and public production hardening are outside these existing Settings fields. Business schemas use MMC, nemilink, ClearCode Labs, ENGEN, Visotonics and Overview. The app blocks data entry if initial Settings cannot load rather than silently applying defaults after a server error.

Follow-ups has seven endpoints under `/api/follow-ups`: POST/GET collection, GET/PUT/DELETE by ID, GET `/upcoming`, GET `/overdue`. Completion and an optional next task are committed atomically by PUT; its response is `{record, nextFollowUp}`. Send `expectedVersion` to reject stale edits. History is generated by the server. DELETE archives the task, and linked lead deletion is blocked to retain history. Upcoming means pending tasks at or after the current instant, including later today; the UI's Upcoming tab means dates after today in IST.

Migration `20261104_0002` adds follow-ups; `20261104_0003` adds quotations and PDF revisions. Browser-only follow-ups and quotations remain untouched; no automatic import is performed. Bell reminders currently require the app to be open; scheduled background delivery is still pending.

## Live demo data and full API verification

```powershell
.\venv\Scripts\python.exe -B scripts/seed_and_verify.py
```

This checks the running local API at `http://127.0.0.1:8000`, asks for an existing login, adds/reuses five labelled records per CRM module, and retains them for UI testing. It signs its own QA session out afterwards and never saves credentials. Coverage is the 30 CRM/report endpoints plus two health endpoints; authentication, user management and Settings have separate isolated tests to avoid changing real account/preferences data. Older saved reports retain their original endpoint count until rerun. Use an Owner test login if quotation approval is enabled. Background delivery and record assignment permissions remain pending.

## Reports API and UI

Four read-only endpoints are implemented: GET `/api/reports/summary`, `/api/reports/leads`, `/api/reports/sales`, `/api/reports/follow-ups`. Shared query parameters are optional `startDate`, `endDate`, `division`, and `includeTestData` (false by default). Date ranges are inclusive in IST. Leads use created date, quotations use their quotation issue date, and follow-ups use due date. Each detail endpoint accepts its own `status` values. Summary ignores detail status filters so its comparison cards use all statuses in the selected period/division.

Conversion is Won / (Won + Lost), returning zero when there are no closed leads. Accepted quotation value is not received revenue: currencies and One-time/Monthly/Yearly amounts stay separate. Only the current quotation totals count; archived quotations/follow-ups and prior PDF revisions are excluded. Sent quotations become Expired after valid-until in IST. Completed follow-ups are never overdue. `[QA TEST]`, `QA-DEMO-`, and `QA-CHECK-` labels identify demo/temporary records; prefix-based test-data exclusion is a prototype convention, not an explicit database flag.

The responsive Reports page has five tabs: Leads, Divisions, Follow-ups, Quotations and Lead sources, with status/priority/trend bars, staff workload and referral contacts. It supports date presets/custom dates, division/status filters, test-data toggle, reset/retry, clickable chart filters, searchable paginated desktop tables/mobile cards, CSV for Excel and PDF export. Exports include all API-filtered report rows; local table search is for browsing only. PDF export runs in the browser. No report storage migration is needed. The implementation aggregates the small CRM dataset in application memory; server-side aggregation/pagination is future scaling work.

Run five additional read-only live scenarios against the existing sample records:

```powershell
.\venv\Scripts\python.exe -B scripts/verify_reports.py
```

The last pre-authentication live run passed five scenarios / 57 checks and wrote `audit/REPORTS-TEST-REPORT.md` and `.json` without changing data. The script now prompts for a real account and logs its QA session out afterwards; authenticate before rerunning it. Browser interaction verification remains pending for the Computer Use reason above.

## Quotation API reference

| Method | Path                                            | Purpose                                                |
| ------ | ----------------------------------------------- | ------------------------------------------------------ |
| POST   | `/api/quotations`                               | Create structured quotation and generate PDF           |
| GET    | `/api/quotations`                               | List active records with revision metadata             |
| GET    | `/api/quotations/{id}`                          | Read a record                                          |
| PUT    | `/api/quotations/{id}`                          | Update status, or edit details and generate a revision |
| DELETE | `/api/quotations/{id}?expectedVersion=N`        | Archive; retain PDF history                            |
| GET    | `/api/quotations/{id}/pdf`                      | Latest PDF; `?download=true` returns attachment        |
| POST   | `/api/quotations/upload`                        | Import existing PDF with metadata                      |
| POST   | `/api/quotations/{id}/revisions`                | Upload replacement PDF; retain previous revisions      |
| GET    | `/api/quotations/{id}/versions/{versionId}/pdf` | Read/download a specific PDF revision                  |

Create accepts `number`, `customer`, `division`, `date`, `validUntil`, optional contact/address, currency (INR/USD/EUR/GBP), tax (0-100), terms, and up to 100 items containing `description`, `quantity`, `rate`, `billing` (One-time/Monthly/Yearly). Totals use server-side decimal arithmetic: round each line to two decimals, then tax per billing period. Client-supplied totals/IDs/history are rejected. Quotation numbers are case-insensitively unique per division, including archived records; blank structured quotation numbers use the Settings-controlled transactional sequence; manual numbers remain supported.

PUT requires `expectedVersion` and either `status` or a complete `document`. Atomic version checks reject stale writes with 409. Editing a generated document saves a new PDF and resets its status to Draft. Status-only edits retain the exact original PDF bytes. Uploaded documents are revised by uploading a replacement PDF rather than regenerating their content.

Uploads use multipart `metadata` (JSON string) and `file`. Imported metadata has no line items, zero additional tax, and an inclusive `amount` plus `billing`. It is entered manually and is not extracted from the PDF. Revisions require multipart `expectedVersion` and `file`; optional complete `metadata` can update imported quote details. File-only revisions retain existing amounts/dates. Revision uploads reset status to Draft. File signatures and PDF structure are checked; encrypted/empty/invalid PDFs and files over 10 MB are rejected.

PDF bytes, SHA-256, original safe name and the document snapshot are retained together in PostgreSQL in the same transaction. Binary content is deferred during list/metadata queries. There are no public filesystem paths. Archive hides a quotation and its download endpoints while preserving records. Retained quotations block customer deletion by current name or aliases, including archived quotations. Customer-name links require manual care when names change; stable foreign-key links remain pending.

Frontend Quotations and Customer PDF views now use these APIs rather than IndexedDB. Legacy browser-only quotations are preserved in the earlier IndexedDB database but are not automatically imported or shown in the server register. Re-upload their PDFs with reviewed metadata if needed. Generated PDFs use ENGEN branding, division, customer, date, currency, items, tax, billing totals and terms. Company/GST, default terms, logo visibility and signature-area settings now apply to generated revisions; custom template editing remains separate work. Back up PDF tables together with quotation records.

The frontend does not silently migrate or erase profiles saved in the earlier browser-only prototype. Transfer useful legacy profiles deliberately after reviewing duplicates. Authentication and Owner account-management rules are implemented; CRM assignment permissions are enforced; the remaining production-readiness steps are still pending.

## Forgot-password recovery (2026-11-05)

Password recovery now uses an email OTP: `POST /api/auth/forgot-password` returns a generic accepted response with a random browser challenge; `POST /api/auth/verify-reset-otp` verifies the 6-digit code and returns a single-use 5-minute reset authorization; `POST /api/auth/reset-password` changes the password and revokes all sessions. New codes expire after 10 minutes (configurable 5–15), allow at most five wrong attempts, and invalidate previous recovery challenges. All requests require `X-CRM-Request: 1` and an allowed Origin when present. Existing unexpired reset links remain compatible during rollout.

For Render, set `MAIL_PROVIDER=gmail`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_SENDER=engenwebsite@gmail.com`, and `PASSWORD_RECOVERY_ENABLED=true` only after configuration and migrations. Gmail uses HTTPS OAuth token refresh and the Gmail API, without SMTP ports or a Gmail account password. Store secrets in backend Render Environment; local development uses `backend/.env.local`. Never put these values in frontend variables or Git. Google OAuth Testing mode issues Gmail refresh tokens that expire after seven days; configure production publishing and any applicable verification requirements before live use.

Migrate before starting the new backend: `python -m alembic upgrade head`. Migration `20261106_0014` adds OTP metadata; `20261106_0015` safely aligns legacy lead customer name columns with the 120-character model; `20261110_0016` adds ENGEN, Visotonics and Overview settings defaults; and `20261110_0017` normalizes the historical `Nemilinks` lead division value to `nemilink`. Follow-up verification: `python -B scripts/verify_password_recovery.py` uses mocked mail and disposable QA schemas, verifies migration/account preservation, single-use reset and PostgreSQL concurrency. It sends no real email and does not reset real accounts.

See [recovery configuration, checks and limitations](audit/PASSWORD-RECOVERY-REPORT.md). Email delivery uses an in-process FastAPI background task, not a durable worker. Real Gmail delivery and the deployed HTTPS flow still need an explicit smoke test after release configuration.

## Staff CRM access (2026-11-05)

Migration `20261105_0008` adds stable indexed User-ID assignments. Owner/second Admin see all records; Staff see/edit only assigned leads, customer profiles and quotations. Follow-ups inherit the linked lead assignment. Reports, dashboard data and all PDF revision routes enforce the same scope. Staff cannot delete/archive or reassign. Normal creation assigns records to the signed-in creator. Existing quotation Owner-approval rules still apply.

Manage assignments in Settings > Users & access > CRM record access. Customer/quotation access is assigned separately; name matches never grant access. Legacy records remain unassigned/Admin-only until reviewed and assigned; migration preserves all existing logins and CRM data. CRM assignment changes are audited and use expected previous User IDs to reject stale saves.

[Policy, endpoints, verification and limits](audit/CRM-ACCESS-REPORT.md). Local PostgreSQL migration/integration checks passed in a rolled-back QA schema. Browser interaction QA remains pending. Referral contact pickers now use per-account browser keys; the old shared registry remains untouched for reviewed migration rather than being displayed to every login.

## Login/API request protection (2026-11-05)

Migration `20261105_0009` adds shared database-backed budgets. Defaults: API IP 600/minute and 100/10 seconds, user 300/minute, user writes 60/minute; login IP 20/15 minutes and normalized email 10/15 minutes. Unknown/malformed/unauthorized API requests count toward IP budgets. Budget transactions survive failed requests, and blocked responses use 429 with Retry-After; the UI displays the wait without automatically resubmitting writes. Rate-store failure returns a safe 503. Production cannot disable general rate limiting.

A pure ASGI guard checks complete request bodies before handlers: JSON 1 MiB, authentication 16 KiB, quotation multipart total 12 MiB (individual PDF remains 10 MiB), headers 16 KiB/100 fields, raw path+query 4096 bytes and body-read timeout 30 seconds. Actual received bytes are bounded even without a reliable Content-Length. Compressed/ambiguous framing is rejected. Defaults apply automatically; `.env.example` lists optional overrides. The existing secret `.env` was preserved.

[Configuration, verification and operational limits](audit/REQUEST-LIMITS-REPORT.md). All 87 backend and 49 frontend tests, lint/build and PostgreSQL checks pass. Twenty concurrent PostgreSQL quota attempts allowed exactly five for a five-request budget. Existing login/account/CRM assignment data was preserved. QA accounts/schema were removed. Trust forwarding headers only from an explicitly configured proxy; ingress/concurrency sizing, counter cleanup, actual load testing and production deployment remain pending.

## Bounded lists and concurrent edits (2026-11-05)

Migration `20261105_0010` adds Lead/Customer versions and list-order indexes. All four CRM collection modules accept `paged=true&page=1&pageSize=25&q=...` plus validated module filters. Maximum page size is 100. Paged responses contain items/total/page/pageSize/pages/hasMore. Legacy array responses are also capped to a page. Counts/search/pagination run in SQL after Staff access scope. The frontend Leads register now uses server pages/search; existing full-data consumers explicitly traverse pages to preserve totals and derived views. Those full-data browser views and reports still need further large-dataset optimization.

Lead/Customer updates require `expectedVersion`; their deletes and Follow-up deletes require the version query parameter. Follow-up updates and assignment edits also require versions through HTTP. Missing preconditions return 428, stale changes return 409. Atomic version claims prevent stale full forms or reassignment from overwriting another edit; duplicate completion cannot schedule another next task. The frontend submits the version originally opened and never forces a conflict through with a newly fetched version.

[Contracts, checks and remaining limits](audit/PAGINATION-CONCURRENCY-REPORT.md). All 94 backend and 53 frontend tests, lint/build and PostgreSQL pagination/race checks pass. Each simultaneous edit race produced exactly one saved change and one conflict; existing live records/accounts were preserved and QA data removed. Browser interaction QA, full server-driven UI migration, relational customer IDs, backups/restore, monitoring and load testing remain pending.

## Manual backup/restore tools and monitoring (2026-11-05)

Owner-only Settings > Workspace > System health & backups now shows database/schema readiness, local backup freshness/restore status and current-worker request/error/slow counts. Public `/api/ready` returns generic 200/503, separate from lightweight liveness. Owner `/api/ops/status` includes storage/job warnings. Structured per-worker rotating JSON logs use request IDs and fixed route templates; raw query/body/credential/customer details are excluded. The frontend shows request references for server errors.

Manual encrypted backup, isolated restore-check and restore-new commands are available under `python -m app.commands.backups`; `python -m app.commands.monitor` checks database/backup/storage and HTTP readiness with exit codes 0/1/2. Restore-new keeps a fresh verified database and revokes old sessions/reset links; it never switches or overwrites live configuration. Retention preserves the latest verified copy. PostgreSQL tools and cryptography are required.

**Real backup configuration, scheduling and offsite copies were deferred by the user.** No real CRM backup/key or scheduled task was created. Disposable PostgreSQL data verified full public-table/PDF restore and tamper rejection; all QA databases/files were removed. Monitoring exists, but no always-on external alerting service is configured. See [commands, recovery runbook, privacy and verification](audit/BACKUP-MONITORING-REPORT.md). All 104 backend and 55 frontend tests plus lint/build pass; browser interaction QA remains pending.

## Responsive UI verification (2026-11-05)

Settings content-column grouping, mobile section navigation, account-row widths and assignment spacing are fixed. Sidebar mouse navigation collapses hover expansion; an invisible logo no longer blocks the touch width control, and touch expansion has a close action. Twelve isolated Chrome browser tests cover 320/375/768/1024/1440-pixel layouts, all Settings sections/main registers, dialogs, notification placement, hover/keyboard/touch navigation, focus trapping and body-scroll restoration. The 55 frontend tests, lint and production build also pass. No real CRM/API mutations were made by browser tests.

See [coverage, fixture screenshots and remaining limits](audit/UI-RESPONSIVE-REPORT.md). Run `npm run test:ui` from crm-ui to repeat using installed Chrome. Live-backend browser flows, physical-device/cross-browser staging checks and subsequent data-link/query/load-test stages remain pending.

## Customer IDs and large-data UI (2026-11-06)

Stable Customer foreign keys, conservative legacy backfill, Admin link review, scoped SQL dashboard/card totals, server-driven core registers and 20-result record pickers are implemented. Quotation list summaries avoid downloading all PDF revisions; full details load on demand. Migration `20261105_0011` must run before deploying these changes. Live PostgreSQL verification/migration is pending because the configured database hostname cannot resolve from this PC; connection configuration was left untouched. See [contracts, checks, deployment step and limits](audit/CUSTOMER-LINKS-LARGE-DATA-REPORT.md).


## Staff role permissions (2026-11-06)

Settings > Roles & permissions now controls common Staff access with checkboxes. Admin Full access is locked ON; Staff Quotations starts OFF. Tick/untick and Save permissions applies to every current/future Staff account. Individual staff switches were removed and their legacy grants are ignored. The same policy guards API/PDF access, summaries, reports, alerts and customer activity. Saving revokes Staff sessions while retaining Admin sessions and assignment restrictions. Migration `20261106_0013` is applied; updated Render code deployment remains pending. See [usage, contracts and verification](audit/QUOTATION-ACCESS-REPORT.md).
