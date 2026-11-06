# Local / Render configuration — 2026-11-06

## Local PostgreSQL

`backend/.env.local` is private and gitignored. It has been created from `.env.example`; replace the placeholder database URL with your existing **local** PostgreSQL connection. No passwords need to be sent through chat. The old `backend/.env` is preserved and ignored by the application.

```dotenv
DATABASE_URL=postgresql+psycopg://YOUR_LOCAL_USER:YOUR_LOCAL_PASSWORD@localhost:5432/YOUR_LOCAL_DATABASE
ENVIRONMENT=development
ALLOW_REMOTE_DEVELOPMENT_DATABASE=false
COOKIE_SECURE=false
ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
RESET_BASE_URL=http://localhost:5173
```

Local mode is selected when the process does not explicitly set `ENVIRONMENT` and is not running on Render. Database URLs targeting a non-loopback PostgreSQL host are rejected in development unless `ALLOW_REMOTE_DEVELOPMENT_DATABASE=true` is intentionally set. Do not enable that option for normal local work. Process variables override the local file, so an old terminal-level `DATABASE_URL` must also be removed if it points at a cloud database.

The local file path is resolved from the backend code, independent of the shell's current directory. `ENVIRONMENT=test` ignores local dotenv files. Native `postgres://` / `postgresql://` URLs normalize to the installed psycopg 3 driver without changing the credentials or host.

After configuring the local URL, run from `D:/CRM-TOOL/backend`:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Use a second terminal from `D:/CRM-TOOL/crm-ui`:

```powershell
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`. Development browser requests always use this relative path even if an old `VITE_API_BASE_URL` contains a cloud URL. Port 5173 is strict, so Vite will report a conflict instead of silently switching to a port excluded from allowed origins. `crm-ui/.env.local` has an empty API base.

Existing local users/data are independent of Render users/data. No accounts or sample records are automatically created. Only a genuinely fresh database needs the interactive `python -m app.commands.create_admin` command.

## Render backend

Use the backend service's Render **Environment** settings, not a committed dotenv file:

```dotenv
ENVIRONMENT=production
DATABASE_URL=<Render PostgreSQL connection URL>
COOKIE_SECURE=true
ALLOWED_ORIGINS=["https://YOUR-FRONTEND.onrender.com"]
RESET_BASE_URL=https://YOUR-FRONTEND.onrender.com
RATE_LIMIT_ENABLED=true
```

Render's `RENDER=true` selects production automatically if `ENVIRONMENT` is absent. An explicitly conflicting development/test environment is rejected. Production requires secure cookies and explicit HTTPS origins. Use the database's internal URL only in a Render environment where that database is reachable; a workstation cannot use an internal-only Render hostname as its local PostgreSQL address.

Run `python -m alembic upgrade head` in an authorized deployment/pre-deploy step before starting the new application version. The Docker startup command continues to use Render's `$PORT`. This change does not deploy, seed, reset or copy databases. SMTP and backup configuration remain separate.

## Render Docker frontend

The frontend Docker build uses relative `/api` requests. Its Nginx runtime proxies these to the public backend HTTPS host. Set this environment variable on the **frontend Docker service**:

```dotenv
API_UPSTREAM_HOST=leadmanagement-backend-v1.onrender.com
```

Use your actual public backend hostname if different, without `https://`, a port or a path. The startup validation script refuses missing/malformed values. Nginx's official template mechanism substitutes only `API_UPSTREAM_HOST`; its own `$uri` and proxy variables remain intact.

No `VITE_API_BASE_URL` build argument is needed for this Docker setup; remove the old absolute API setting. Keeping browser requests on the frontend origin lets the existing HTTP-only, Secure, SameSite=Strict refresh cookie work through `/api/auth`. Nginx permits the existing 10 MB PDF uploads within a 12 MiB total request limit; backend-specific limits remain enforced. Upstream TLS SNI/Host use the backend hostname. Certificate verification is explicitly enabled using the runtime CA bundle; an actual container handshake check remains required.

These proxy instructions apply to the provided Docker frontend. A separately managed static frontend needs an equivalent same-origin `/api` proxy; the Vite development proxy is not part of a production build.

Both Docker contexts exclude local dotenv files; backend backups/operations data are also excluded. `.sh` files have LF line endings through `.gitattributes`.

## Verification and limits

Configuration tests cover local/cloud isolation, precedence, URL driver normalization, remote-local protection, production-cookie requirements and hidden validation input. The browser environment test deliberately starts Vite with a cloud API setting and checks that actual browser requests still target the local origin. Existing auth/API/UI regressions are also tested.

Verified: **117 backend tests, 55 frontend service tests, 18 isolated Chrome UI tests, ESLint and production build pass.** The Nginx startup shell script passes syntax and valid/missing/malformed hostname checks. Local secret files are confirmed gitignored.

Local PostgreSQL connection/migration verification requires the placeholder in `.env.local` to be replaced. Live Render deployment was not changed. Docker's Linux engine was not running on this PC, so the final image/Nginx runtime could not be exercised here; verify its build/start and login/refresh/upload flows in Render staging before production promotion.

Primary references: [Render environment variables](https://render.com/docs/environment-variables), [Render Docker services](https://render.com/docs/docker), [official Nginx template substitution](https://github.com/nginx/docker-nginx/blob/master/entrypoint/20-envsubst-on-templates.sh).
