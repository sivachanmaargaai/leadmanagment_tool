# Common Staff role permissions — 2026-11-06

## Use

Open **Settings → Roles & permissions** as either Admin. Admin **Full access** is checked and locked. Under **Staff**, tick/untick **Quotations**, then click **Save permissions**. The single rule applies to all current and future Staff accounts. Individual Staff switches were removed from Users & access.

Staff quotation access starts OFF. ON enables the module and its PDFs/reports for Staff, while retaining assigned-record scope. OFF hides and blocks the module everywhere. Access changes sign all Staff out; they sign in again to see the new menu. Admin sessions remain active. Owner-only account creation, role/password/activation rules remain unchanged.

## Backend contract

- `role_permissions` stores the Staff rule, version and updated timestamp. Missing policy fails closed. Admin access is fixed in server code and cannot be unchecked by an API request.
- Admin-only `GET /api/permissions` returns the shared role matrix and version. Admin-only `PUT /api/permissions/staff` accepts `{quotations: boolean, expectedVersion: integer}`. Changes lock/version-check the role, audit before/after values and revoke all Staff sessions in the same transaction. Conflicts return 409.
- Auth checks join the current role policy into the existing token/session/user query; permissions are not cached in tokens or trusted from the browser. Login/refresh/account responses resolve the same policy.
- Existing `users.quotation_access` values are retained for schema compatibility but are ignored. The retired individual `PUT /api/users/{id}/quotation-access` returns 410 to Admins and 403 to Staff. Generic account/profile APIs cannot change role permissions.
- New Staff and demoted Admin accounts inherit the common Staff rule. There are no individual overrides.
- Every quotation/PDF/upload/revision/download route is guarded. Disabled Staff receive 403; revoked sessions receive 401; enabled Staff still receive 404 for another assignee's quotation.
- OFF removes quotation totals/alerts from workspace responses, quotation counts/accepted values from report summaries, and quotation defaults from Staff settings. Sales reports are denied. Sidebar, report/customer quotation tabs, export data sources, quotation settings and expiry controls follow the same rule.
- General CRM notes and lead requirements continue to follow their own assignment rules; this feature restricts the quotation module and its derived data.

## Migration and verification

Migration `20261106_0013` was applied to the configured PostgreSQL database. It initializes the common Staff rule OFF and revokes existing Staff sessions to refresh their UI/auth state. User fields/passwords, Admin sessions and CRM record counts were verified preserved. Individual flags are no longer authoritative.

Verified checks:

- **126 backend tests**, including common role defaults, ignored legacy grants, all-Staff grant/revoke, both Admins, assignment scope, aggregate redaction, version conflicts, audit, future/demoted account inheritance and migration preservation.
- **59 frontend service tests**, ESLint and production build.
- **24 isolated Chrome UI tests**, including checked/unchecked role saving, locked Admin access, absent individual switches, Staff-hidden controls, responsive layouts and existing navigation/loading behavior.
- Actual PostgreSQL API tests in a disposable `qa_quote_permissions_<uuid>` schema: both Staff update together, real PDF reads and assignment denial, old tokens rejected, sales/settings/summary redaction, no self-grant and retired individual API rejection. QA accounts/PDFs/schema were removed and absence verified. The real shared Staff rule remains OFF after initial migration; QA never toggles the live policy.

Repeat from `backend` with appropriate database privileges:

```powershell
.\venv\Scripts\python.exe -B scripts\verify_quotation_permissions.py
```

Refresh the local browser to load the new tab. Staff must sign in again after permission changes. Render needs the updated backend/frontend deployed to enforce this new role policy in the deployed application; this task did not deploy code or change Render service settings.
