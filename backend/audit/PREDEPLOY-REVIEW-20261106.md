# Deployment review — 2026-11-06

## Decision

The core CRM is ready for a Docker/staging verification pass. **Production sign-off is still pending.** No images were pushed, services deployed, accounts changed or CRM records edited during this review.

## Verified now

- Fresh checks: **126 backend tests, 59 frontend tests, 24 isolated Chrome UI tests, lint and production build pass.**
- The configured PostgreSQL database is reachable over TLS and its migration `20261106_0013` matches the current code.
- Live backend liveness at `https://leadmanagement-backend-v1.onrender.com/api/health` returned OK. Its public OpenAPI does **not** yet include `/api/permissions` and `/api/permissions/staff`, so that deployed backend has not received the new common-role implementation.
- Local `.env` / `.env.local` files are gitignored and Docker contexts exclude local dotenv files. Backend operations/backups are excluded from the image context.
- Existing Render business tables/settings contain no division values requiring conversion from the current `nemilink` rename. This check was read-only; legacy browser data is a separate import concern.

## Required before production

1. **Docker build and runtime verification.** Docker CLI is installed, but its Linux engine is not running (`dockerDesktopLinuxEngine` pipe absent). Neither actual image has been built/started in this review. Start Docker Desktop, then build with the correct contexts:

   ```powershell
   docker build -t engen-crm-backend:staging ./backend
   docker build -t engen-crm-ui:staging ./crm-ui
   ```

   Check backend startup/readiness and Nginx startup/proxying. Local Python/Node tests do not prove the Linux image runtime.

2. **Production environment values.** Verify the backend service has its Render database URL, `ENVIRONMENT=production`, `COOKIE_SECURE=true`, explicit HTTPS `ALLOWED_ORIGINS` matching the frontend, and the correct reset-link origin if recovery is enabled. The frontend Docker service requires `API_UPSTREAM_HOST` containing the public backend hostname only. Do not deploy local dotenv files. See [environment setup](ENVIRONMENT-CONFIGURATION.md).

3. **Real HTTPS staging flows.** Test Admin and Staff sign-in, refresh after browser reload, logout, common Staff quotation checkbox ON/OFF, old-session rejection, other-assignee denial, quotation creation/upload/view/download and reports through the actual Nginx → backend path. Existing browser tests use isolated fixtures; PostgreSQL integration tests do not exercise this deployed HTTPS proxy path.

4. **Recovery and operations.** Verify an actual usable database backup and restore procedure, plus external health/error alerts, before entering real customer data. Application backup scheduling/offsite configuration was deferred by the user and has not been activated by this task. A verified managed-provider backup is an alternative to app-managed backups. The current backend image does not install `pg_dump` / `pg_restore`, so app backup commands cannot be assumed to work inside that image without adding matching client tools and durable storage/key handling.

5. **Capacity and release rollback.** Run a small realistic five-user staging load test including reports/uploads; choose connection/concurrency limits from those results. Preserve the previous image tag for rollback. Required Dockerfiles/new modules/migrations remain untracked/uncommitted in the current workspace; include them deliberately in the release source and exclude local secrets/archives. The zero-byte `%~f1` batch artifact is not application source.

## Proxy correction made during review

The frontend HTTPS upstream previously configured SNI/Host without explicitly enabling certificate verification. The Nginx template now enables `proxy_ssl_verify`, supplies the CA trust bundle and verification depth, and the runtime image explicitly installs `ca-certificates`. These directives still need an actual container/staging handshake check once the Docker engine is available. [NGINX directive reference](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_ssl_verify).

## Features that can remain outside an initial pilot

- Real SMTP/reset-email delivery verification; recovery is disabled in the current local configuration, and live SMTP configuration was not inspected.
- Durable background email/push delivery and retries. Current reminders rely on the open application.
- Reviewed legacy browser-data imports, product catalogue, custom logo upload and digital signatures.
- Large report/export optimization and scheduled expired-session/rate-counter cleanup remain follow-up work. Core registers are paged, but report services still materialize scoped rows in memory.

Recommended sequence: **Docker runtime checks → protected staging → real flow/load checks and recovery verification → versioned production deployment.**
