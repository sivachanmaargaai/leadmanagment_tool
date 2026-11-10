# Remaining work review — 2026-11-06

This is a read-only application/deployment review. No accounts, permissions, recovery records or business data were changed. The user confirmed the live OTP/reset flow now works. Older audit files contain historical pending lists and test counts; they must not be treated as current status.

## Verified complete or working

- Gmail API transport and OTP recovery are implemented. Live OTP endpoint presence was verified and the user confirmed successful operation.
- Public frontend /api/health returns 200/ok; /api/ready returns 200/ready through the live frontend reverse proxy.
- Anonymous requests to quotations, users and sales reports return 401. This is a limited anonymous-access check, not a substitute for real Staff row-scope testing.
- Existing implemented features include authentication, Owner/Admin user rules, common Staff quotation permission, assigned-record access, CRUD modules, quotations/PDF revisions, reports, backend pagination/search, concurrent-edit guards, database-backed rate limits/request limits, stable customer links and responsive component UI.
- Latest verified regression results remain 135 backend tests, 61 frontend service tests, 30 Chrome UI tests, lint/build and isolated PostgreSQL concurrency/migration verification. These suites were not rerun for this read-only review because no application code changed.
- Existing Docker Hub backend/frontend v1.1 tags were updated and independently verified by digest. Actual Linux container startup, frontend assets and Nginx syntax were checked during that release.

## Logo/source follow-up

The requested quotation logo fix is implemented in this release: `app/assets/engen-logo.png` is packaged with the backend and the generator reads that resource. The preview was rendered and reviewed; 138 backend tests, 61 frontend tests and actual Linux container branding/proxy checks pass. Stored PDF revisions remain unchanged; new quotations/revisions receive the logo. The original missing-logo finding below is retained as historical evidence. GitHub source synchronization is part of this requested release; see the completion commit/result rather than treating the earlier git-status snapshot as current.

## Confirmed remaining issues/work

| Priority | Work | Evidence/current limitation |
|---|---|---|
| High | Fix current ENGEN quotation logo packaging | quotation_pdf.py looks for the frontend public logo outside the backend Docker context. The published backend image reports quotation_logo_available=false. Generated quotations use issuer text fallback instead of the requested logo. This is separate from deferred custom-logo upload. |
| High | Sync tested/released source to GitHub | git status still contains uncommitted application changes and untracked migration 0015/tests/release reports. Docker Hub publishing did not commit/push GitHub source. Preserve secrets and exclude temporary archives/backups when preparing a release commit. |
| High | Restrict the runtime database role | Read-only role inspection of the configured Render PostgreSQL connection reports rolsuper=false, rolcreatedb=true, rolcreaterole=true, rolbypassrls=false. Normal web requests do not need database/role creation. Separate runtime permissions from migration/backup-restore operator permissions, then verify on Render. No privileges were changed here. |
| High | Complete live Admin/Staff and small load tests | Live OTP and anonymous denial are confirmed, but a full authenticated 2–5 user production/staging pass covering row assignments, common quotation OFF/ON, PDFs/uploads, refresh/logout, concurrent edits and realistic report traffic has not been performed in this review. Use disposable data/accounts for mutation tests. |
| Operational, user-deferred | Activate backups/offsite/restore drill | Backup/restore tooling exists and was tested with disposable fixtures. Actual schedule, offsite destination/key storage and managed-provider backup/restore evidence remain unconfigured or unverified. The backend image has neither pg_dump nor pg_restore; app-managed backup commands cannot be assumed to work in that image without suitable tools and durable storage. The user explicitly deferred backup configuration earlier. |
| Operational | External monitoring and persistent log handling | Owner health/metrics and manual monitoring CLI exist. Built-in operations status reports automation/offsite as not-configured. Always-on external alerts/log retention are not implemented in the repo; any provider-side external setup was not inspected. Container-local rotating log files are not durable across replacement without external storage/drain. |
| Medium | Scheduled auth/recovery/rate cleanup | No cleanup scheduler/command was found for expired/consumed records. Read-only aggregate snapshot found 32 expired access tokens, 13 expired/revoked sessions and 3 expired/consumed recovery records. These are inactive maintenance candidates, not evidence of usable expired credentials. Cleanup must preserve refresh replay-detection records for the relevant live session lifetime and respect FK dependencies. Nothing was deleted. |
| Medium | Large report/export optimization | reports.py loads scoped records into Python memory and applies several filters/groupings there. Core register pagination is already implemented; reporting/export needs separate SQL aggregation/filtering/bounded export work as data grows. |
| Medium | Durable email/background notifications | Recovery uses FastAPI BackgroundTasks. Restarts can lose a pending delivery; no durable queue/retry/bounce tracking exists. Business reminders currently depend on the open application; background email/push was deliberately deferred. |
| Medium | Consistent release automation | No .github workflow is present. Matching frontend/backend rollout, migration execution, registry digest confirmation and post-deploy contract/readiness checks are manual. The recent old-backend/new-frontend mismatch demonstrated this gap. |
| Low | Settings sessions UI | /api/auth/logout-all exists and is callable by the service layer, but no separate sign-out-all-devices/session management control was found in the current profile UI. |
| Low | Documentation refresh | README and older audit reports still describe completed customer links, pagination, permissions, SMTP activation and old test counts as pending. Consolidate around the current review before handing off. |

## Deferred product scope

- Product/service catalogue.
- Custom/division logo upload and quotation templates.
- Actual digital signatures/seals or customer signing (the current signature preference only adds an empty signing area).
- Reviewed import of useful legacy browser/localStorage/IndexedDB data, if any exists.
- Additional common Staff module/action checkboxes beyond the implemented Quotations switch, only if requested by management.

## Provider settings not independently verified

Google OAuth production publishing/verification status and confirmation that the screenshot-exposed client secret was rotated are not visible from normal application configuration. Successful delivery today does not establish a refresh token's long-term lifetime. Render backup retention, external uptime monitoring, migration hooks and proxy/client-IP trust settings require dashboard/operator verification. This review does not claim they are all absent.

## Suggested next order

Fix the existing quotation logo asset, synchronize the released source, restrict the runtime database role, then complete a disposable-data live workflow/load pass. Add maintenance cleanup and release verification automation next. Revisit backups/monitoring when the deferred operational configuration is authorized. Optional catalogue/branding/signature/background notification work can remain later.
