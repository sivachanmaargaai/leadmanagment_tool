# Users & access implementation

Date: 4 November 2026.

## Account rules

| Signed-in account | Directory | Can create/edit/change roles |
| --- | --- | --- |
| First administrator / Owner | All Admin and Staff accounts | Yes, excluding the protected Owner row |
| Second administrator | Staff accounts only | No |
| Staff | Own profile only | No |

Two Admin slots are enforced by database constraints, including inactive administrators. Staff is the default new-account role; the Admin option is unavailable when the second slot is occupied. Only the Owner can promote/demote other accounts. The Owner cannot be edited or deactivated from this screen. Sensitive changes revoke the target's sessions. Passwords are never returned by the directory APIs. Changes are recorded in server-generated audit events without password material.

## Verification

- Six user-management scenarios plus two migration scenarios passed against isolated SQLite databases.
- Existing CRM/authentication/report regression tests passed with real test logins.
- Five frontend user-service tests passed; frontend suite totals 31 tests.
- ESLint and production build passed.
- PostgreSQL migration `20261104_0005` applied; existing account details/password hashes and CRM records retained.
- Local database has one Owner / one Admin after migration; no staff or additional real admin was created by these checks.
- PostgreSQL API checks passed for Owner management, third-admin rejection, second-admin staff-only scope, forbidden mutations and session revocation.
- PostgreSQL verification used an isolated temporary schema; its schema/accounts/sessions were rolled back.

Browser interaction QA remains pending after the Computer Use URL-verification blocker. Account-management permissions are implemented; staff access to individual CRM records is a separate pending feature.
