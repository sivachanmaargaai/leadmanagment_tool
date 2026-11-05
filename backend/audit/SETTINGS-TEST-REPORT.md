# Settings backend and frontend integration

Date: 4 November 2026.

## Connected sections

| Section | Storage and behavior |
| --- | --- |
| My profile | Own display name, phone, designation; verified-current-password change signs out all own sessions |
| Company & divisions | Owner-editable shared company contacts, GST, division addresses/prefixes; used in new PDF revisions |
| Users & access | Existing real account-management endpoints and Owner/two-admin rules |
| Lead settings | Shared defaults, backend required-field rules, custom sources and suggested task intervals |
| Products & quotations | Defaults, transactional auto numbering, issuer snapshots, logo/signature-area switches, Owner Sent/Accepted gate |
| Notifications | Per-user in-app priority/follow-up/overdue/quotation-expiry toggles, new-task reminder default, optional sound |
| Workspace | Per-user sidebar, default division, client-side page size and display date preferences |

## Verification

- Five new backend scenarios passed: shared permissions/persistence; personal isolation/password change; stale combined-save rollback; lead defaults/validation; quote numbering/PDF/approval.
- Full backend suite: 62 tests passed.
- Frontend suite: 36 tests passed, including five Settings/runtime/notification scenarios.
- ESLint and production build passed.
- PostgreSQL migration `20261104_0006` applied after schema comparison; existing accounts/password hashes and CRM records retained.
- PostgreSQL settings/numbering/approval integration passed inside a temporary schema; all temporary records/settings/accounts were rolled back.
- Settings-driven quotation PDF was rendered and visually checked.

## Limits

Browser click/visual QA remains pending after Computer Use could not verify the current Windows browser URL. Service/API tests do not replace browser interaction QA. Audio is subject to browser interaction/autoplay rules. Notifications require the app to stay open. Backend pagination/rate limits, background delivery, product catalogues, custom logo upload and digital signing are separate work. Existing browser-only Settings are not automatically imported. Existing PDF revisions and scheduled task defaults remain unchanged.
