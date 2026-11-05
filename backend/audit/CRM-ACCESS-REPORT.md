# Staff CRM permissions — 2026-11-05

Implemented stable User-ID assignments for leads, customer profiles and quotations. Follow-ups inherit access from their linked lead. User names, email strings and legacy `assignedTo` labels never grant record access. Customers and quotations are assigned independently: matching customer names/aliases do not automatically reveal a profile or PDF history.

| Action | Owner / second Admin | Staff |
| --- | --- | --- |
| List/read CRM records | All | Assigned records only |
| Create records | Assigned to creator | Assigned to self |
| Edit CRM details | All | Assigned records only |
| Schedule/complete follow-ups | All leads | Assigned leads only |
| Reports/dashboard/export source data | All | Assigned records only |
| PDF/latest revision/history download | All | Assigned quotations only |
| Delete/archive | Allowed, existing history protections apply | Denied |
| Assign/unassign/reassign records | Allowed | Denied |
| Create/manage login accounts | Owner only, existing two-Admin policy | Denied |

Quotation status actions continue to honor the existing Owner-approval setting. Assigning a quotation grants access to its entire retained PDF history. This phase does not introduce a separate quotation approval inbox or per-field permissions.

## Management UI and API

Settings → Users & access now contains **CRM record access** for both Admins, independently of the Owner-only account editor. Choose Leads/Customers/Quotations, then an active account, or Unassigned (Admin-only). The directory is paginated (25 per page; API allows 1–100). Inactive accounts remain identifiable on existing assignments but cannot receive new assignments. No assignment occurs by matching potentially duplicated staff names.

- GET `/api/access/assignments?module=leads&offset=0&limit=25`
- PUT `/api/access/assignments/{module}/{recordId}` with required `assigneeUserId` and `expectedAssigneeUserId` (each can be null). Stale assignments return 409. Invalid/inactive targets return 422.

Assignment changes create server-generated audit events. Mutation routes check record ownership on the server, with row locks protecting assignment checks against concurrent reassignment. Quotation assignment advances the quotation version. Staff deletes and assignment APIs return 403; another Staff member's record/detail/PDF returns 404. Assignment IDs are output-only on normal CRUD payloads, preventing mass assignment.

Migration `20261105_0008` adds nullable indexed user foreign keys using RESTRICT deletion behavior. Existing logins, password hashes, roles and CRM records are preserved. Legacy records remain **unassigned and Admin-only** until an Admin deliberately assigns them. Existing legacy display labels are not interpreted as authorization. Follow-up views/reports display the linked lead's current account name when assigned; old task labels remain retained as fallback history.

Normal customer/follow-up forms direct reassignment to Settings, instead of offering a name field that looks like a permission control. Staff delete/archive controls are hidden while edit actions remain available. API checks remain authoritative even if a caller bypasses the UI.

## Verification

- Six access scenarios cover Owner/second Admin/2 Staff with identical Staff display names: lists/details/updates; self-assigned creation and denied deletion; inherited follow-ups/reassignment; customer/PDF/revision isolation; scoped reports/summary; stale/invalid/inactive assignment targets.
- Existing API/auth/settings/quotation/migration suites pass alongside access tests.
- Three assignment service tests cover pagination, stable-ID CAS payloads, null unassignment, permission errors and invalid directory responses. Customer form tests cover retained fields/contacts, aliases/history on rename, referral data and validation. A reference-registry test verifies separation between account pickers while preserving the old shared key. ESLint and production build pass.
- Local PostgreSQL migration matches ORM metadata. Existing table counts and full login-account rows were compared before/after; legacy assignments were confirmed null.
- PostgreSQL integration passed for Staff isolation, direct requests, summary reports, reassignment, conflict rejection and forbidden deletion. The temporary schema and accounts were rolled back.

The customer form was restored after an encoding error during editing; profile/referral payload regression tests were added. Referral pickers now use per-account browser keys and do not automatically read the old shared registry. This preserves legacy data for the separate reviewed migration phase.

## Remaining limits

Browser interaction/responsive QA is still pending; service tests/build are not visual sign-off. Already displayed/downloaded data cannot be recalled after reassignment; refresh open CRM screens to load current access. Subsequent API requests enforce current assignments. Customer/quotation assignments must be maintained explicitly until stable customer relationships are introduced. Assignment and follow-up report display names may be identical even though access uses distinct IDs.

This completes the selected initial permission policy, not public deployment readiness. General/login rate limits, request limits, backend CRM pagination, wider concurrent-edit protection, durable notifications, legacy imports, backup/restore, monitoring, cleanup, load testing and staging/production configuration remain separate work. SMTP activation/delivery verification remains pending from password recovery.
