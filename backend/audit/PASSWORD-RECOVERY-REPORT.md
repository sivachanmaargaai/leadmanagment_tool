# Password recovery review — 2026-11-06

## Implemented flow

1. `POST /api/auth/forgot-password` accepts the normalized login email and returns a generic 202 with `challengeId`, expiry and resend cooldown. Unknown/inactive accounts receive the same response shape. The browser challenge is generated from 32 cryptographically random bytes; it is not the emailed code.
2. The background sender locks the account, invalidates previous outstanding recovery records and generates a zero-padded cryptographic 6-digit OTP. Only `SHA256(challenge)` and `SHA256(challenge + ":" + code)` persist. The separately held random challenge prevents brute-forcing an OTP using a database dump alone. Codes and raw challenges never appear in application logs.
3. `POST /api/auth/verify-reset-otp` checks the challenge and code, account status/version, successful provider submission, expiry and failed attempts. Five wrong codes consume the challenge. Verification atomically removes the code hash and rotates the challenge into a new 5-minute reset grant. The same code/challenge cannot be verified again.
4. `POST /api/auth/reset-password` rejects an unverified OTP challenge. A verified grant changes the password (8–128 characters), increments account version, invalidates all recovery records, revokes all sessions and writes an audit event. Owner/role permissions remain unchanged. The user signs in again.

OTP expiry defaults to 10 minutes and is configurable between 5 and 15. A resend invalidates previous OTPs and verified grants. Existing legacy unexpired reset links remain compatible during deployment.

## Email transport and secrets

`MAIL_PROVIDER=gmail` uses Google's fixed HTTPS OAuth token and Gmail `messages.send` endpoints. It refreshes an access token using the backend-only client ID, client secret and refresh token, then sends MIME content from the configured Gmail sender. Calls use verified TLS, a bounded response size and timeouts; there are no automatic send retries that could duplicate messages. Google HTTP error payloads are suppressed. Sender configuration and required credentials are validated at startup when recovery is enabled.

SMTP with verified STARTTLS/SSL remains available through `MAIL_PROVIDER=smtp`. Gmail API uses no Gmail account password, App Password or SMTP ports. Google credentials are not required in the frontend.

Local configuration: `backend/.env.local`. Render configuration: backend service Environment. Never commit actual credentials. The example file documents every field. Recovery remains OFF until explicitly enabled after credentials and migration checks.

```dotenv
MAIL_PROVIDER=gmail
GMAIL_CLIENT_ID=YOUR_CLIENT_ID
GMAIL_CLIENT_SECRET=YOUR_NEW_CLIENT_SECRET
GMAIL_REFRESH_TOKEN=YOUR_REFRESH_TOKEN
GMAIL_SENDER=engenwebsite@gmail.com
OTP_MINUTES=10
PASSWORD_RECOVERY_ENABLED=false
```

For release, deploy both frontend and backend, run `python -m alembic upgrade head`, set valid backend secrets and then set `PASSWORD_RECOVERY_ENABLED=true`. The frontend consumes the new OTP response contract; old and new frontend/backend builds must not be mixed. Render Free blocks normal SMTP ports; Gmail HTTPS avoids that restriction.

Google OAuth must be configured with only `https://www.googleapis.com/auth/gmail.send`. External apps left in Testing receive Gmail refresh tokens with a seven-day lifetime. Complete production publishing and applicable Google verification requirements. Even production tokens can be revoked or invalidated and may need reauthorization. Any previously exposed client secret should be rotated before use.

## Request and concurrency protection

All recovery mutation endpoints retain `X-CRM-Request: 1` and Origin checks. Responses carrying challenges/grants set `Cache-Control: no-store`. OTP, challenge and reset grant remain only in React state; none is placed in URLs or browser storage.

Persistent budgets: 10 send requests/IP/15 minutes, 3 requests/email/30 minutes, 60 seconds between requests for that email, 20 OTP verification attempts/IP/15 minutes and 20 password reset attempts/IP/15 minutes. These apply to unknown emails as well. Send throttling returns 429 with accurate `Retry-After`; the UI preserves the active challenge and disables resend for the wait. Per-code failures commit before error rollback. Existing general API/login limits and request size limits also apply.

Account locks precede recovery-row locks across send/verify/reset. PostgreSQL verification covers concurrent failures with no lost increments, exactly one successful grant exchange, and exactly one successful reset. A process may fail after provider acceptance but before the database records success; such a code fails closed and the user must request another.

## Database and verification

- Migration `20261106_0014` adds recovery kind, OTP hash, failed attempts and verification timestamp; user/password rows are not changed.
- Migration `20261106_0015` fixes pre-existing drift: some databases still have a 100-character lead customer column while the model allows 120. Upgrade only widens legacy databases and skips already-aligned databases. Downgrade keeps the canonical 120-character width specified by 0011; 0011 owns the guarded shrink to 100.
- Final full backend regression: 135 tests passed, including migration upgrade/downgrade, Gmail error sanitization and accurate resend wait timing.
- Frontend service tests: 61 passed.
- Chrome UI suite: 30 passed, including six recovery scenarios across mobile/tablet/desktop, wrong-code errors, password confirmation, disabled recovery and resend cooldown. Fixtures intercept all APIs; no actual credentials or mailboxes are used.
- Frontend lint and production build passed.
- PostgreSQL migration/account-preservation and disposable-schema concurrency verification passed. Head is `20261106_0015`, lead customer width is 120 and zero temporary OTP/recovery QA schemas remain. Existing accounts and row counts were preserved.

## Remaining release checks

No actual Gmail message was sent during automated checks. Presence of configured credentials does not establish that the Google grant, Gmail API enablement or sender authorization works. Verify delivery to an authorized test recipient and complete the deployed HTTPS recovery flow before declaring live readiness. Do not enable recovery based only on placeholder/configured variable presence.

Delivery still uses an in-process FastAPI BackgroundTasks task, not a durable queue. A restart can lose a pending send; there are no worker retries or provider delivery/bounce tracking. Automatic recovery-row cleanup remains pending. These limitations are explicit; durable background notifications were deferred by the user.
