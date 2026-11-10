# Docker Hub release — 2026-11-06

> Historical release record. The images documented here were built at migration head `20261106_0015`; the current source head is `20261110_0017`. Build and deploy both services from the current source before using the new division migrations.

Both existing v1.1 tags were rebuilt from the current workspace and pushed to the user's existing Docker Hub repositories, as explicitly requested. No v1.2 tag was created. Docker Hub manifests were queried after the pushes and matched the local build outputs.

| Image | Published manifest digest |
|---|---|
| chan0345/leadmanagement-backend:v1.1 | sha256:3692a619fd88b1cd50d4fc7f3e941c755df677c41b80d2d1e56688af6a4bdd50 |
| chan0345/leadmanagement-frontend:v1.1 | sha256:49a5b7ea732e9f61c8b2da39ba9b868e1cef52ae7be75698a5d0b65344bba3d0 |

Previously recorded v1.1 digests: backend `sha256:395a174953b06ce0e5e56c224fe27dee47f05696379b73ac36608ce11df94ef8`; frontend `sha256:56df69f8e41621bd95030886bdfb5d02dfdc725104a62b4d2aa3ad97e15df18d`.

## Logo follow-up

The same backend v1.1 tag was subsequently rebuilt/pushed with the packaged ENGEN quotation logo; the current digest is listed above. The preceding OTP-only backend digest was `sha256:2e5c12bbcf717644273756fe018cc81049f399566b656f47cf81a19238c85a68`. Frontend v1.1 is unchanged. Backend PDF branding tests and all disposable container checks pass, including HTTPS proxying to the correct backend hostname `leadmanagement-backend-v1-1.onrender.com`. See backend/audit/QUOTATION-LOGO-REPORT.md. Redeploy the backend to activate this later logo fix; existing stored PDF bytes are not modified.

## Container verification

- Linux amd64 builds succeeded; the frontend production build ran in its real Node build stage.
- Backend container starts Uvicorn and serves health/OpenAPI, includes the OTP verification route, and contained migration head 20261106_0015 when this release was built.
- Local .env/.env.local files and nested .bak source backups are absent from the final backend image. Nested backup/archive exclusions were added to backend/.dockerignore.
- Frontend Nginx startup/template substitution and `nginx -t` pass with API_UPSTREAM_HOST supplied. HTTP index/assets include the new OTP frontend flow.
- Disposable smoke containers used no real database or mailbox credentials and were removed afterward.
- The initial proxy check to the older hostname timed out; the later check against leadmanagement-backend-v1-1.onrender.com passed. Authenticated role/load checks remain separate.
- Reproducible checks: `backend/venv/Scripts/python.exe -B -X utf8 scripts/verify_docker_release.py` (requires Docker Desktop).

## Render follow-up

Build and redeploy both services from the current source. Ensure the frontend service has API_UPSTREAM_HOST set to the actual backend hostname without a scheme/path. Retain the configured Gmail variables and MAIL_PROVIDER=gmail / PASSWORD_RECOVERY_ENABLED=true on the backend service only. Confirm migration head 20261110_0017 before using recovery and the expanded division set.

The Docker operations pushed images without invoking a Render redeploy, changing Render environment variables, sending further emails, or modifying CRM accounts. The subsequent logo/source release includes the separately requested GitHub synchronization. Any existing auto-deploy hooks were not inspected. Live readiness requires checking the deployed services after the image pull.
