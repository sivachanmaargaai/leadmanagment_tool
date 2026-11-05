# Password recovery — 2026-11-05

Implemented `POST /api/auth/forgot-password` and `POST /api/auth/reset-password`, with Tailwind sign-in/recovery/reset forms. New passwords accept 8–128 characters, with confirmation in the UI. Reset never automatically signs in a user.

Reset links expire after 15 minutes by default, are single-use, and store only SHA-256 token hashes. Successful reset atomically changes the password, increments the user version, invalidates all reset links and revokes all sessions. User role/Owner status is preserved. Account edits/password changes invalidate older links. Unknown/inactive accounts and email cooldowns receive the same generic accepted response. Requests do not change passwords or revoke existing sessions.

Email links use the configured trusted frontend URL, not request Host headers. Tokens use URL fragments, are removed from browser history on load, and are never placed in local/session storage or API responses. The frontend sets `Referrer-Policy: no-referrer` through its HTML meta tag. Production requires HTTPS. SMTP exceptions log only the exception class, not addresses, messages or links. Failed sends invalidate their tokens.

Database-backed budgets: 10 recovery requests/IP/15 minutes, 3 accepted sends/email/30 minutes with a 60-second cooldown, 20 reset attempts/IP/15 minutes. IP-limit responses include Retry-After. Counter commits survive invalid reset attempts. Configure the reverse proxy to forward client addresses only from trusted proxies; otherwise requests may share a proxy IP. These limits do not cover login/general API traffic.

## Existing mailbox configuration

Edit `D:/CRM-TOOL/backend/.env` locally using `.env.example` as a reference; preserve DATABASE_URL and existing settings. Do not share mailbox passwords in chat or commit them.

```dotenv
PASSWORD_RECOVERY_ENABLED=true
RESET_BASE_URL=http://localhost:5173
SMTP_HOST=your-provider-smtp-host
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your-mailbox-address
SMTP_PASSWORD=your-mailbox-smtp-or-app-password
SMTP_FROM=your-authorized-sender-address
SMTP_FROM_NAME=ENGEN CRM
RESET_LINK_MINUTES=15
```

Use the mailbox provider's settings. Port 465 generally uses `SMTP_SECURITY=ssl`; both modes verify TLS certificates. Production RESET_BASE_URL must use HTTPS and its origin must appear in ALLOWED_ORIGINS. Restart the backend after configuration. Recovery stays disabled until configured; disabled endpoints return 503 without pretending to send mail. The existing secret `.env` was preserved.

## Verification

- Backend coverage: generic replies, trusted URLs/token hashes, expiry, single use, account version changes, session revocation, unchanged Owner status, inactive accounts, password length, email cooldown, database-backed IP limits, CSRF, disabled configuration, failed SMTP, TLS and invalid configuration.
- Frontend coverage: fragment parsing/history removal, public recovery requests, payloads, error handling/no refresh retries and malformed responses.
- Migration 0007 applied to local PostgreSQL. Schema matches ORM metadata; existing table row counts and full login-account rows were compared before/after and preserved.
- PostgreSQL reset/replay/session-revocation integration passed in a temporary schema that was rolled back. SMTP was mocked; no actual email was sent and no real account password was reset.

Real mailbox delivery and browser interaction QA remain unverified. Email currently uses an in-process FastAPI background task, not a durable queue; a process crash may lose a send. Automatic retry/worker monitoring and background notification/push delivery belong to the next phase. Expired token/rate-row cleanup and overall production hardening remain pending.
