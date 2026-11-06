# UI verification and responsive fixes — 2026-11-05

Step 1 of the remaining-work sequence is complete for the current Chrome UI coverage. Verification uses a separate headless Chrome profile and synthetic read-only API fixtures; it does not automate the user's browser or sign into/change real accounts. A dedicated Vite server runs on port 5174, leaving the normal port-5173 workspace alone. Native Windows browser verification remains restricted; these are isolated application browser tests.

## Fixes

- Settings now always has two top-level grid items: navigation and one content column. User management and CRM assignments stay together in the content column. The prior third grid item could land in the narrow navigation column, causing the screenshot's vertical text/overflow.
- Mobile/tablet Settings use a full-width section selector instead of clipped horizontal navigation labels. Desktop retains the sticky navigation card.
- Account rows use a responsive grid. Names/emails keep their width, while mobile role/status/edit controls occupy a separate row. Form labels and inputs stack consistently.
- Assignment rows stack on small screens, with bounded dropdown widths and normal text wrapping. Desktop uses one compact column heading instead of repeating the assignment label on every row.
- Mouse navigation clears hover expansion after selecting a page, preventing the expanded rail from covering Settings controls.
- The hidden logo no longer intercepts taps on the collapsed sidebar width control. Landscape tablet touch expansion has an explicit collapse button; choosing a page also closes the expanded rail.

All styling uses Tailwind classes. Existing role rules, settings persistence and business APIs remain unchanged.

## Browser verification

**12 Playwright browser tests pass**:

1–5. Settings sections and Leads/Customers/Follow-ups/Quotations/Reports at **320, 375, 768, 1024 and 1440 CSS pixels**. Verify no document-wide horizontal overflow, full-width assignment content and desktop separation from the settings navigation.

6. Repeated desktop hover open/leave close, keyboard focus expansion and Escape collapse.

7–9. Lead, customer, follow-up, quotation and login-account dialogs plus notification popover containment at 375/768/1440 pixels. Dialogs close with Escape and produce no unexpected API mutations.

10. Always-expanded preference retains the desktop content gutter.

11. Mobile drawer locks/restores body scrolling, wraps Tab/Shift+Tab focus, closes with Escape and restores the opener's focus.

12. Touch-enabled landscape tablet opens/collapses the rail and closes it after page selection. This test caught the hidden-logo pointer interception and passes after the fix.

**55 frontend service/date/form tests, ESLint and production build also pass.** Existing backend test results remain 104 passing from the prior backend stage; no backend application code changed in this UI work.

Desktop and mobile Settings screenshots were visually inspected. Stable fixture-only previews:

- [Desktop](../../crm-ui/audit/ui/settings-desktop.png)
- [Mobile](../../crm-ui/audit/ui/settings-mobile.png)

The preview accounts/records are synthetic test data. The real database, passwords, assignments, settings and backup configuration were not changed by these tests.

## Repeat

From `D:/CRM-TOOL/crm-ui` with installed Google Chrome:

```powershell
npm run test:ui
npm test
npm run lint
npm run build
```

Playwright is pinned as a development dependency; fixtures intercept `/api/**` requests, and mutation attempts other than fixture session restoration are rejected. Screenshots/failure traces go to ignored `test-results/ui`. The server is started/stopped by the test runner. Existing live UI data is not used.

## Limits and next work

This verifies rendered Chrome layouts and emulated touch/viewport behavior, not physical iOS/Safari/Firefox certification or live-backend end-to-end workflows. Browser fixtures complement the previous real API tests; they do not replace staging verification. User-provided real data and browser zoom/accessibility combinations may warrant additional staging checks.

Next implementation stage: stable customer-ID relationships and remaining large-data UI query optimization, followed by realistic load testing and staging. Automatic backups/offsite configuration stay deferred as requested.


## Customer-ID / query follow-up (2026-11-06)

Core registers now query one server page at a time; dashboard counts are SQL aggregates. Five additional browser tests verify 10,000-record fixture pagination/search, bounded customer/lead selectors and explicit overview errors. See [implementation and deployment limit](CUSTOMER-LINKS-LARGE-DATA-REPORT.md). Live PostgreSQL migration is pending database connectivity; Staff module visibility controls remain a separate next change.
