# ENGEN CRM — UI readiness audit

Audit date: 3 November 2026. Scope: current code in `D:/CRM-TOOL/crm-ui` and local browser preview.

## Decision

**The responsive visual foundation is ready; the frontend workflow is not complete.** Backend schema/API planning can begin, but the remaining frontend workflows should be defined before treating the UI as signed off. Do not interpret a successful build as proof that all business flows are implemented.

This audit did not change application code or create business records.

## What is implemented

| Area | Current capability | Completion limit |
| --- | --- | --- |
| Layout | ENGEN branding, compact spacing, shadows, light transitions, desktop hover rail, mobile/tablet drawer, responsive lists | Tested layouts are browser viewport checks, not physical iOS/Android device tests |
| Dashboard | Lead counts, status pipeline, scheduled follow-up queue, Today/Overdue counts, division filter | Missing quotation summary/value views, date/staff filters, explicit lost-lead summary |
| Leads | Add lead, requirement, division, priority, lead source/reference, reference contact registry, search, local persistence | No details/edit/status-update workflow; missing several core fields |
| Customers | Add/edit profiles, multiple contacts, divisions, reference, search/type filters, linked record tabs/history | Legacy records are mostly joined by customer name; no customer-prefilled quick creation flows |
| Follow-ups | Schedule, complete with outcome/notes, next follow-up, reschedule reason/history, filters, local persistence | No related-quotation picker; reminders are browser-running logic, not background delivery |
| Quotations | Create PDF, upload existing PDF, preview/download, statuses, uploaded revision history, division/status filters | No generated-draft editor, duplicate action, revision metadata editor, catalogue or configured template integration |
| Settings | Seven sections and locally saved values; staff names consumed by some forms | Many preferences are saved but do not control the rest of the app |
| Reports | Navigation entry | Placeholder only |
| Authentication | Static Admin display | Login/logout/forgot/reset screens and real sessions are absent |

## Priority 1 — finish the core workflow

### 1. Leads cannot be progressed after creation

New leads are always created with `status: "New"`. The Leads page renders status as a badge and has no edit/details/actions column. Staff cannot move a new lead to In Progress, Follow-up, Won or Lost through the UI. Consequently dashboard conversion counts can reflect seeded data but users cannot complete that workflow for a new lead.

The lead form also lacks received date, customer phone/email, assigned staff and a next-action entry point. These were part of the earlier requirements. Add a details/edit flow, status update (with appropriate notes), assignment, received date, phone/email, and links to schedule a follow-up/create a quotation. Keep task completion separate from lead Won/Lost status.

Evidence: [AddLeadModal.jsx](D:/CRM-TOOL/crm-ui/src/components/AddLeadModal.jsx:52), [LeadTable.jsx](D:/CRM-TOOL/crm-ui/src/components/LeadTable.jsx:20), [App.jsx](D:/CRM-TOOL/crm-ui/src/App.jsx:68).

### 2. Login-related UI is missing

There is no login page, forgot/reset-password flow, logout control or account menu. The app opens the dashboard directly and the header displays a static Admin identity. Authentication and authorization enforcement belong in the backend, but the frontend screens, loading/error states and role-dependent navigation should be defined now. Staff access policy still needs the previously deferred business decision.

Evidence: [App.jsx](D:/CRM-TOOL/crm-ui/src/App.jsx:19), [Header.jsx](D:/CRM-TOOL/crm-ui/src/components/Header.jsx:1).

### 3. Saved settings are not applied consistently

Examples confirmed by comparing consumers with Settings:

- Default lead priority/status and contact requirements are not used by Add Lead.
- Quotation prefix/next number, validity, currency, tax and terms are not used by QuoteForm. It generates an `ENG-year-random` number and initially sets validity to today.
- Company/division address and GST, show-logo/signature and approval settings are not used by PDF generation/quotation workflow.
- Profile name is not used by the header.
- Sidebar preference, default division, rows per page and date format are not used by layout/lists.
- Notification enable/disable preferences are not used by the alert builder.

Connect settings through shared state/adapters, or disable clearly deferred controls. Local preference wiring does not require a backend. Server-side roles, approval enforcement and concurrent quotation numbering do.

Evidence: [Settings.jsx](D:/CRM-TOOL/crm-ui/src/pages/Settings.jsx:28), [QuoteForm.jsx](D:/CRM-TOOL/crm-ui/src/components/quotations/QuoteForm.jsx:44), [quotationPdf.js](D:/CRM-TOOL/crm-ui/src/lib/quotationPdf.js:114), [Sidebar.jsx](D:/CRM-TOOL/crm-ui/src/components/Sidebar.jsx:22), [App.jsx](D:/CRM-TOOL/crm-ui/src/App.jsx:51).

### 4. Quotation correction/revision workflow is incomplete

Created PDFs can be viewed/downloaded, but saved drafts cannot be reopened to edit line items/customer details and regenerate a revision. Upload Revision appends the file and resets status to Draft while retaining old amount, dates and terms. A revised PDF containing changed prices can therefore disagree with the register and future reports.

Provide draft editing, revision creation with financial/date metadata, and a duplicate action. Define whether revisions of accepted quotations need additional review. The existing PDF must remain available in history.

Evidence: [Quotations.jsx](D:/CRM-TOOL/crm-ui/src/pages/Quotations.jsx:190), [QuoteForm.jsx](D:/CRM-TOOL/crm-ui/src/components/quotations/QuoteForm.jsx:123).

### 5. Reports remains a placeholder

The Reports menu reaches the generic “This screen will be built in the next step” panel. Define a small first release: leads by division/staff/status, follow-up completion/overdue, and quotation status/value. Keep currencies and one-time/monthly/yearly amounts separate. Alternatively explicitly defer and hide the module; it should not remain a visible unfinished screen at UI sign-off.

Evidence: [App.jsx](D:/CRM-TOOL/crm-ui/src/App.jsx:168). Browser evidence: [Reports screenshot](D:/CRM-TOOL/crm-ui/audit/reports-placeholder.jpg).

## Priority 2 — finish integrations and remaining agreed UI

### 6. Use shared customer identity across modules

Customers supports name/alias-based linkage, but new lead and quotation records do not populate `customerId`; quotations also do not populate `leadId`. The quotation customer suggestions come from leads, so a standalone customer is not automatically offered there. Selecting a company does not prefill its contact/address details. A standalone customer cannot have a follow-up until a lead exists because follow-ups require a linked lead.

Add an existing-customer selector, stable IDs, contact/address prefill and customer-level action entry points. Decide explicitly whether all follow-ups must be lead-linked. Preserve customer-level reference separately from the reference for each individual lead.

Evidence: [customers.js](D:/CRM-TOOL/crm-ui/src/lib/customers.js:7), [QuoteForm.jsx](D:/CRM-TOOL/crm-ui/src/components/quotations/QuoteForm.jsx:172), [AddLeadModal.jsx](D:/CRM-TOOL/crm-ui/src/components/AddLeadModal.jsx:44).

### 7. Finish dashboard navigation and metrics

Add quotation count/accepted-value summaries and the intended date/staff filters. The Today and Overdue cards currently both open the default All follow-ups view; carry the selected filter into the target page. Add clear drill-downs rather than requiring the user to filter again.

Evidence: [Dashboard.jsx](D:/CRM-TOOL/crm-ui/src/pages/Dashboard.jsx:117).

### 8. Complete notification interaction

There are high-priority lead alerts and scheduled follow-up reminders. There is no read/unread/dismiss lifecycle, click-through action or quotation-expiry alert. The current timer runs only while the app is open. Settings switches do not govern it. Frontend read state/navigation can be designed now; scheduled delivery, persistence and email/WhatsApp integrations require backend work.

### 9. Catalogue and quotation format details

Products & Services master is not implemented. Quotation item rows are manually entered. Discount/delivery-charge controls and dedicated delivery/warranty inputs are absent; only one tax percentage and a combined terms field exist. There is no division-specific configured PDF template. Confirm which of these are required for the first version; they are not complete merely because the settings fields exist.

### 10. Data tools, pagination and global activity

Excel import/export, module visibility and global activity history are still explanatory text in Workspace settings. Lists have no pagination, despite the saved rows-per-page option. Customer/follow-up history is not a complete audit of all lead, quotation and user changes.

## Backend work — expected after the UI decisions

- Real user accounts, sessions, password reset, role/assignment authorization.
- Shared database and persistent file storage, replacing localStorage/IndexedDB as the system of record.
- Stable relationships for customers, contacts, references, leads, follow-ups and quotation versions.
- Atomic sequential quotation numbering and versioned quotation metadata.
- Scheduled reminders, notification read state and the chosen delivery channels.
- Server-side validation, pagination/filtering, file access and change history.
- A deliberate migration path for useful browser prototype records and sample-data removal.

These are backend implementation tasks, not reasons to label an unfinished frontend complete.

## Validation performed

- Current production build: **passed**.
- Existing Node tests: **4 passed** (IST date handling, Today/Upcoming classification, reminder/overdue boundaries and linked reference resolution).
- Current browser audit: all 7 navigation pages at **390px, 768px and 1440px**, 21 combinations. No page-level horizontal overflow in the inspected state.
- Reports placeholder and missing Add Lead fields confirmed in the browser.
- No browser console errors during the sampled navigation.
- Earlier focused checks covered 320px layouts, customer forms/tabs, referral validation and sidebar expansion/collapse. This audit does not replace real device testing or full end-to-end tests with created/edited records.
- Quotation create/upload/download success paths, revision financial reconciliation, large-data pagination, real permissions and cross-device persistence are **not covered by the existing 4 tests**.

## Non-blocking cleanup

The production build warns about a roughly 785 kB main JavaScript chunk (about 242 kB gzip). Lazy-load PDF generation/pages after functionality is settled. Remove unused starter assets/styles once confirmed unreferenced. Page navigation currently lives in React state rather than URL routes; deep links/back-button behavior are a later usability improvement.

## Suggested completion order

1. Finish lead details/edit/status/assignment and customer selection.
2. Add login/account screens and settle staff access rules.
3. Wire shared settings and complete quotation editing/revision metadata/template.
4. Build basic Reports and dashboard drill-downs; finish notification interaction.
5. Decide the first-release scope for catalogue/import-export, then perform full workflow acceptance tests.
6. Connect backend accounts, database, files and scheduled jobs to those settled contracts.
