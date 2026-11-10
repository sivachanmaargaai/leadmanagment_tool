# Code and OTP integration review — 2026-11-06

## Outcome

Gmail API transport and email OTP recovery are implemented across backend and frontend. The application OpenAPI contains 58 documented operations including health, operations, user management, role permissions and the new OTP verification route; the original 35-API estimate is no longer the implemented route count. This inventory does not claim that every route or deployment configuration has been independently penetration tested.

## Findings addressed

- The original recovery path sent links through SMTP. The new default UI requests a code, verifies it and sets a new password; Gmail API HTTPS works without SMTP ports.
- Unverified challenges cannot reset passwords, codes/grants cannot be replayed, and five wrong guesses lock a challenge. Account version changes and deactivation invalidate recovery.
- Resend replaces old codes/grants, and persistent cooldown/rate windows survive errors and multiple workers. Fixed Retry-After selection when the email budget is exhausted; UI respects the returned wait while retaining the previous valid challenge.
- Gmail response reads and network waits are bounded; TLS is verified and provider error payloads/credentials are not exposed in mail delivery exceptions.
- A pre-existing PostgreSQL schema drift left lead customer names at VARCHAR(100) while the model and 0011 migration specify VARCHAR(120). Added an additive repair that preserves names and skips already-aligned databases. Migration test databases require portable batch operations; repaired that compatibility before final sign-off.
- Tests explicitly isolate SMTP/Gmail transports so locally configured real Gmail credentials are not used during automated checks.

## Verification evidence

- Frontend: 61 service tests, 30 Chrome UI scenarios, lint and production build passed. Recovery UI covers mobile/tablet/desktop, wrong code, confirmation mismatch, disabled recovery, resend cooldown and server throttling. API fixtures intercept every browser request.
- Backend: final full regression suite passed 135 tests after resolving SQLite migration compatibility. Gmail/SMTP transport and password recovery tests use mocked delivery.
- PostgreSQL head: 20261106_0015. Metadata matches the actual database after migration, existing accounts/password fields and table counts were preserved, and disposable QA schemas were removed.
- Real PostgreSQL transactions verified concurrent failed-guess increments, exactly one successful OTP exchange, exactly one successful password reset, replay rejection and session revocation. Only disposable QA accounts were reset; mail was mocked.
- Local `.env.local` has the expected Gmail sender and all three credential fields populated; values were not printed. Configuration presence does not prove credential validity. Recovery remains disabled.
- Git ignores local dotenv files; they are not tracked. Docker contexts exclude dotenv files.

## Release work still required

1. Rotate any client secret exposed in screenshots, if not already done. Confirm OAuth sender authorization, Gmail API enablement and production publishing/verification state.
2. Deploy matching frontend/backend builds. Add backend-only Gmail variables and MAIL_PROVIDER=gmail to Render; apply migrations before starting the new backend. Enable PASSWORD_RECOVERY_ENABLED only when ready to test delivery. Do not configure secrets in the frontend.
3. Authorize a real email smoke test and verify the complete deployed HTTPS OTP/reset/login flow. This task sent no actual email. The local backend was not reachable in the current liveness check; the Render OpenAPI request timed out, so active deployment version could not be confirmed.
4. Prior production review still requires actual Docker runtime/proxy tests, realistic multi-user/load testing, backups/restore and external monitoring configuration. They were not completed by this code/OTP task.

## Deferred limitations

Email is sent using in-process FastAPI BackgroundTasks; process restarts can lose a send and there is no durable retry/bounce tracking. Expired auth/recovery/rate record cleanup is not scheduled. Reports still materialize scoped data in memory despite paged core registers. Durable notifications, catalogue, uploaded branding/signatures and legacy browser data import remain separate work.

See PASSWORD-RECOVERY-REPORT.md for configuration and detailed recovery behavior, and PREDEPLOY-REVIEW-20261106.md for the earlier Docker/staging release checklist. The earlier review's test counts and migration head are historical and superseded by this review.
