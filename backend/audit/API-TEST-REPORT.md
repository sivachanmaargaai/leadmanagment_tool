# Live CRM API test report

Result: **PASS**
Tested: 2026-11-04T04:49:29.682644+00:00
Checks: 172/172
Endpoint coverage: 28/28 (including health)

## Visible test data

| Module | Demo records | Total active records |
| --- | --- | --- |
| customers | 5 | 6 |
| leads | 5 | 6 |
| followUps | 5 | 5 |
| quotations | 5 | 5 |

## Endpoint checks

| Method | Endpoint | Result |
| --- | --- | --- |
| DELETE | `/api/customers/{customer_id}` | PASS |
| DELETE | `/api/follow-ups/{follow_up_id}` | PASS |
| DELETE | `/api/leads/{lead_id}` | PASS |
| DELETE | `/api/quotations/{quotation_id}` | PASS |
| GET | `/api/customers` | PASS |
| GET | `/api/customers/{customer_id}` | PASS |
| GET | `/api/db-health` | PASS |
| GET | `/api/follow-ups` | PASS |
| GET | `/api/follow-ups/overdue` | PASS |
| GET | `/api/follow-ups/upcoming` | PASS |
| GET | `/api/follow-ups/{follow_up_id}` | PASS |
| GET | `/api/health` | PASS |
| GET | `/api/leads` | PASS |
| GET | `/api/leads/{lead_id}` | PASS |
| GET | `/api/quotations` | PASS |
| GET | `/api/quotations/{quotation_id}` | PASS |
| GET | `/api/quotations/{quotation_id}/pdf` | PASS |
| GET | `/api/quotations/{quotation_id}/versions/{version_id}/pdf` | PASS |
| POST | `/api/customers` | PASS |
| POST | `/api/follow-ups` | PASS |
| POST | `/api/leads` | PASS |
| POST | `/api/quotations` | PASS |
| POST | `/api/quotations/upload` | PASS |
| POST | `/api/quotations/{quotation_id}/revisions` | PASS |
| PUT | `/api/customers/{customer_id}` | PASS |
| PUT | `/api/follow-ups/{follow_up_id}` | PASS |
| PUT | `/api/leads/{lead_id}` | PASS |
| PUT | `/api/quotations/{quotation_id}` | PASS |

## Notes

- Only synthetic QA data was created/updated/deleted.
- Five active demo records are retained per implemented module.
- DELETE checks archive a temporary follow-up and two temporary quotations per run; their histories remain stored by design.
- Pending modules have no implemented API routes to test.
- No email, SMS or other external messages were sent.

Pending: Reports, Authentication & Users, Settings, Notification delivery.
