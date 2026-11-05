# Login, API rate limits and request limits — 2026-11-05

Implemented shared database-backed rate budgets and a pure ASGI input guard. All existing CRM permissions and recovery-specific limits remain enforced. Existing secret `.env` was preserved; defaults are enabled without adding credentials or external services.

## Default budgets

| Scope | Budget |
| --- | --- |
| API client IP | 600 requests / 60 seconds |
| API client IP burst | 100 requests / 10 seconds |
| Authenticated user | 300 requests / 60 seconds |
| Authenticated user writes | 60 requests / 60 seconds |
| Login client IP | 20 attempts / 15 minutes |
| Normalized login email, across IPs | 10 attempts / 15 minutes |

These are fixed windows starting at the first request, not rolling windows. Login budgets count successful and unsuccessful validated sign-in attempts; passwords are not verified once a login budget is exhausted. Unknown, inactive and active accounts use the same throttling rules. Throttling does not permanently lock an account, change a password or revoke an existing session. Existing signed-in sessions remain usable subject to normal API budgets.

The IP guard runs before body parsing/authentication and covers unknown API routes, malformed JSON, unauthorized and validation-failure requests. Verified user budgets run once per authenticated request; failed writes consume their budget. CORS OPTIONS preflight and the lightweight public `/api/health` endpoint are excluded. Docs/static/frontend routes are outside these API budgets. Invalid body/CSRF requests do not consume the email-specific login budget, but still consume IP budgets.

Counters use indexed `rate_limit_buckets` rows, SHA-256 identity keys and locked short transactions shared across workers. They commit independently of business requests, so a rollback does not erase attempts. There is no in-memory-only quota or raw IP/email/token storage in the bucket keys. A blocked budget returns JSON `429`, `Retry-After` seconds and `Cache-Control: no-store`. Storage failure returns a generic `503` and Retry-After 5, while public application health remains available. PostgreSQL rate transactions use 2-second lock and 3-second statement timeouts. Existing password-recovery counters retain their separate limits/table.

## Input limits

| Input | Default limit / rejection |
| --- | --- |
| JSON/general request body | 1 MiB / 413 |
| Authentication request body | 16 KiB / 413 |
| Quotation multipart upload or revision, complete request | 12 MiB / 413 |
| Individual PDF file | Existing 10 MiB / 413 |
| Headers | 16 KiB, maximum 100 headers / 431 |
| Raw path plus query | 4096 bytes / 414 |
| Reading complete request body | 30 seconds / 408 |

Declared Content-Length is checked, and received bytes are counted even when no length is supplied or the declared length is false. A bounded body is buffered before handlers run, so a late oversized chunk cannot follow an already saved mutation. Duplicate Content-Length/Content-Type, conflicting transfer framing, invalid lengths and length mismatches return 400. Compressed request bodies are unsupported and return 415. Total upload limits include multipart boundaries/metadata; PDF validation and its individual file cap still run.

The frontend reads Retry-After and displays a wait time for 429. It does not refresh authentication or automatically resubmit a rate-limited/oversized write. CORS exposes Retry-After on allowed origins, including middleware errors.

## Configuration and verification

All settings/defaults are listed in `.env.example`; restart the backend after changing overrides. `RATE_LIMIT_ENABLED=false` is available only outside production, and never disables input-size/time limits or existing recovery-specific limits. Production configuration rejects disabled general rate limiting.

- **87 backend tests pass**, including 11 new cases covering login normalization/password-work rejection, IP/burst windows, user/write budgets, failed-write persistence, malformed/unknown routes, spoofed forwarding headers, CORS, shared concurrent quotas, storage failure, production configuration, streamed bodies, framing, size caps and body timeout.
- **49 frontend tests pass**, including Retry-After handling and oversized-request errors; lint and production build pass.
- Migration `20261105_0009` applied to local PostgreSQL; ORM/schema comparison found no differences. Existing record counts, full login-account rows and CRM assignment IDs were preserved.
- PostgreSQL API checks passed for login throttling, surviving existing sessions, oversize rejection without inserting a lead, general IP limits and CORS. A uniquely named isolated QA schema used independent physical connections, then was removed and verified absent. No real account password or role was changed.
- PostgreSQL concurrency: 20 attempts across 8 workers/separate connections with a budget of 5 produced exactly **5 allowed / 15 rejected**. This is a quota-correctness check, not a load/capacity test.

Run `venv/Scripts/python.exe -B scripts/verify_request_limits.py` from the backend directory to repeat migration/state-preservation/integration checks. Existing API tests keep the actual guards enabled and direct their sessions to isolated fixture databases.

## Deployment and remaining work

Client identity comes from the ASGI client address. This code never trusts arbitrary X-Forwarded-For/Forwarded headers. Uvicorn may already have rewritten that address, so configure its trusted proxy list explicitly. Never use a wildcard trusted list on a publicly reachable backend. The reverse proxy must overwrite incoming forwarding headers with the actual client address, and the backend port should be private. An incorrect proxy configuration can let clients spoof identities or make all users share one IP budget.

Set ingress body/header/time limits as well, because Python middleware cannot protect the network connection or HTTP parser before ASGI runs. For a single trusted Nginx proxy, suitable starting directives inside the existing `/api/` location are:

```nginx
client_max_body_size 12m;
client_body_timeout 30s;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Forwarded-Proto $scheme;
```

Set `client_header_timeout 10s;` at server/http scope. Start Uvicorn behind that local-only proxy with an explicit trusted address such as `--proxy-headers --forwarded-allow-ips=127.0.0.1`; adapt the address to the actual topology. This is configuration guidance, not a completed production deployment or a tested Nginx installation.

Budgets require short database writes per request; capacity must be measured in the later load test. Fixed windows allow bursts near window boundaries. Per-email throttling can temporarily delay a targeted user's sign-in; recovery/login rate limiting is not a permanent lockout. Requests from a shared NAT share the IP budgets. Body buffering is bounded per request, but total concurrent memory/connection capacity still needs ASGI/proxy concurrency sizing. Rate/recovery counter and expired-session cleanup are not scheduled yet.

Next priority remains backend pagination/search and broader concurrent-edit protection. Backups/restore, monitoring, load testing, browser/mobile interaction QA, staging and production configuration remain pending. SMTP activation/delivery verification, durable notifications and reviewed legacy migration are still separate work. These guards are not a public-deployment sign-off or a substitute for ingress/DDoS protection.

References: [Starlette pure ASGI middleware](https://www.starlette.io/middleware/) and [OWASP API4 resource consumption](https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/).
