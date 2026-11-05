# Backups, restore and monitoring — 2026-11-05

Manual tools and application monitoring are implemented and tested. **Real backup activation, automatic scheduling and offsite destinations remain deferred at the user's request.** No scheduled task/automation was installed, no real CRM backup/key was created, and no live database was restored or switched. The existing secret `.env` was preserved.

## Monitoring available now

- Owner-only **Settings → Workspace → System health & backups**: database/schema readiness, backup freshness/restore marker, current worker request/error/slow counts and manual refresh. Staff and the second Admin cannot call its status API.
- GET `/api/health`: lightweight public liveness, independent of database readiness.
- GET `/api/ready`: generic ready/not-ready response with 200/503. Checks database connectivity and migration head; no URLs, roles or schema details are exposed. Existing IP budgets still apply before this probe.
- GET `/api/ops/status`: authenticated Owner-only status. Includes low operations-volume space warnings, missing/stale backup warnings, last CLI backup job failure and recent worker server-error threshold.
- JSON request logs at `backend/var/logs/api-{pid}.jsonl`, rotating at 5 MiB with 3 previous files per process by default. The directory is private. Raw Uvicorn access logging is disabled while structured logging is active; deployment commands should also use `--no-access-log`.
- Logs contain UTC timestamp, validated/generated request ID, fixed route template, method, status, duration and exception class only. Raw paths, query strings, bodies, Authorization/cookies, passwords, reset links, SQL parameters and customer identity are not recorded by this logger. Unexpected errors before response start become safe JSON 500 responses. The UI shows a support request ID on 5xx responses without retrying writes.
- Per-worker in-memory metrics are bounded (maximum 128 route buckets, five recent minute buckets). They reset on restart and are not aggregate multi-worker or historical metrics. Log filenames isolate workers; configure an external collector/old-process-log retention when deploying.

Manual monitor check, from `D:/CRM-TOOL/backend`:

```powershell
.\venv\Scripts\python.exe -B -m app.commands.monitor
```

Checks database/schema, backup state, local storage and the configured HTTP readiness endpoint (`OPS_HEALTH_BASE_URL`, default `http://127.0.0.1:8000`). Exit codes: **0 local checks passed / 1 warnings / 2 critical database or API availability failure**. The CLI does not misrepresent its own fresh metrics as server metrics; server counters are available in the Owner panel. Missing backup configuration deliberately produces a warning. No email/webhook notifications or background monitoring schedule is configured.

## Manual backup tools — configure/run later

Install pinned dependencies (`cryptography==50.0.2` is added). PostgreSQL `pg_dump`/`pg_restore` must be compatible with the server; `PG_BIN_DIRECTORY` can select them. Local verification used PostgreSQL 18.4 and installed version-18 tools.

```powershell
# Read-only; does not generate a key or backup:
.\venv\Scripts\python.exe -B -m app.commands.backups status

# When ready to activate backups: encrypted backup + isolated restore drill:
.\venv\Scripts\python.exe -B -m app.commands.backups create --verify

# Recheck an existing backup; substitute its emitted identifier:
.\venv\Scripts\python.exe -B -m app.commands.backups restore-check BACKUP_ID
```

First create generates a random 256-bit key at `backend/var/keys/backup.key`, separate from `backend/var/backups`. Directories are restricted to the current Windows account (or mode 0700 on POSIX); key/pass files use private creation modes and inherit the private directory. Do not run the web service or backup job under a different identity without deliberately granting the necessary access.

`pg_dump` custom-format archive and public-table fingerprints share an exported, read-only repeatable-read snapshot. That includes app users/password hashes, settings, CRM rows, sessions, PDF binaries and migration data consistently, even while live requests continue. It does not back up server-wide PostgreSQL roles, `.env`, application code, certificates or the encryption key.

Archives are streamed through AES-256-GCM with a fresh nonce; archive keys and manifest-authentication keys use separate derived purposes. Signed JSON sidecars contain ciphertext checksum/size and public-table row counts/fingerprints. PDF content SHA-256/size columns are checked against actual stored bytes. Encryption/decryption works in bounded chunks. Passwords never appear in subprocess arguments; short-lived private pass files are removed on completion. PostgreSQL stderr and raw exceptions are not printed.

The final backup set is **both** `BACKUP_ID.dump.enc` and `BACKUP_ID.json`. Keep these together, but keep a protected recovery copy of `backup.key` separately. Losing that key prevents recovery; changing/deleting it does not rotate existing archives. The tool refuses to generate a replacement key over existing archives. `.gitignore` excludes secrets, runtime files and archives. Nothing under `backend/var` is served by HTTP.

Plain custom dumps exist only in the private work directory during dump/restore, and normal success/failure removes them. An OS/process crash may leave work files; use OS disk encryption and inspect private work storage after a crash, with no active job, before removing remnants. A cross-process OS file lock prevents overlapping backup/restore commands and releases on process exit.

Retention keeps the newest 7 authenticated backup sets by default **and preserves the most recent restore-verified set** even if older. Only strictly named, authenticated sets in the backup directory are pruned; unrelated or invalid files are preserved for review. Retention runs after successful creation/optional verification, not after a failed restore. API freshness checks authenticate the manifest/check size; they intentionally do not reread large archives on every panel refresh. Full archive checksum/GCM/table checks happen during restore drills, so freshness is not a new full integrity check.

## Recovery runbook — never executed against live data here

```powershell
# Creates and keeps a fresh engen_recovered_<uuid> database only:
.\venv\Scripts\python.exe -B -m app.commands.backups restore-new BACKUP_ID
```

This command cannot overwrite an existing or configured source database and does not modify `.env` or point the app at the result. It authenticates/decrypts the archive, restores with exit-on-error/single-transaction/no-owner/no-privileges, compares every public-table fingerprint and PDF integrity, then invalidates restored sessions/access/refresh/reset tokens. The emitted database name identifies the new recovery database. Credentials are not printed. Failed new targets are removed; a successful `restore-new` deliberately retains its new database.

The restore operator needs CREATEDB privileges on the restore cluster. Optionally set `BACKUP_RESTORE_ADMIN_URL` in the environment to a separate operator connection; otherwise the configured database connection is used for drills. A restricted runtime app role should not be granted CREATEDB merely to make this work. Recovery into another cluster also needs suitable PostgreSQL compatibility and role/network configuration.

After a real incident, an operator must review the restored database, provision least-privilege application-role access, preserve any needed incident/newer data, and approve a deliberate application connection cutover. Take a final backup of the existing environment before any destructive cleanup. Users must sign in again after recovery. No cutover, old-database deletion or destructive restore command is automated here.

## Verification

- **104 backend tests pass**: existing CRM/auth/permission/rate/pagination cases plus streamed encryption/tamper detection, existing-target preservation, signed metadata/path validation, key stability, missing/fresh/stale status, pass-file cleanup, retention/verified-copy protection, Owner-only operations/readiness, bounded metrics, privacy-safe failures and offline API monitoring.
- **55 frontend tests**, lint and production build pass, including monitoring payload/permission errors and support request IDs.
- Real PostgreSQL integration used a **disposable source database**, not the live CRM. It generated a PDF plus user/CRM/session/reset fixtures, created an encrypted archive, restored fresh drill/recovery databases, compared public-table fingerprints/PDF bytes, confirmed session/reset invalidation on recovery, rejected a same-length corrupted archive, and verified readiness/Owner status APIs.
- Generated QA databases, temporary key, archives, work files and logs were removed. No real backup/schedule was configured, matching the user's request. No schema migration was needed; current migration head remains `20261105_0010`.

Repeat isolated verification with `venv/Scripts/python.exe -B scripts/verify_backup_monitoring.py` from backend. It requires local PostgreSQL tools/CREATEDB and removes only exact internally generated QA databases/storage paths.

## Deferred work / practical limits

Daily automation, missed-run policy, offsite/encrypted cloud copy, independent key recovery storage and external alert delivery are **not active**. Configure these before relying on the system for disaster recovery. Current logs/metrics and CLI checks are a monitoring foundation, not a hosted always-on monitoring service. Configure proxy logs to avoid sensitive query strings as well. Current public-table verification does not claim checks for unrelated non-public schemas/global roles.

Still pending: browser/mobile interaction QA; full server-driven UI queries for bulk views; stable customer relationship IDs; least-privilege production database/service identities; realistic load/capacity tests; counter/session/old-process-log cleanup; staging/HTTPS/proxy configuration and production cutover. Background business notifications, SMTP activation, reviewed legacy imports and optional product/logo/signature features remain separate work.

References: [PostgreSQL pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [PostgreSQL pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html), [Cryptography GCM documentation](https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/).
