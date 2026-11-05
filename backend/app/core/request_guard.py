"""Pure ASGI guard: reject oversized/slow input before JSON or multipart parsing."""
import anyio
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from app.core.config import settings
from app.services.request_limits import enforce_ip_limits


class RequestGuardMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] != "http" or not (path == "/api" or path.startswith("/api/")) or scope.get("method") == "OPTIONS" or path == "/api/health":
            return await self.app(scope, receive, send)

        async def reject(status, detail, headers=None):
            response = JSONResponse({"detail": detail}, status, headers={"Cache-Control": "no-store", **(headers or {})})
            await response(scope, receive, send)

        # Count rejected, malformed, unauthorized and unknown-route requests too.
        try:
            await run_in_threadpool(enforce_ip_limits, scope)
        except HTTPException as error:
            return await reject(error.status_code, error.detail, error.headers)

        headers = scope.get("headers", [])
        if len(headers) > settings.REQUEST_MAX_HEADERS or sum(len(key) + len(value) + 4 for key, value in headers) > settings.REQUEST_HEADER_MAX_BYTES:
            return await reject(431, "Request headers are too large")
        if len(scope.get("raw_path", path.encode())) + len(scope.get("query_string", b"")) > settings.REQUEST_URL_MAX_BYTES:
            return await reject(414, "Request URL is too long")
        values = {}
        for key, value in headers:
            values.setdefault(key.lower(), []).append(value)
        lengths = values.get(b"content-length", [])
        if len(values.get(b"content-type", [])) > 1 or len(lengths) > 1 or (lengths and b"transfer-encoding" in values):
            return await reject(400, "Ambiguous request framing")
        declared = None
        if lengths:
            if not lengths[0].isdigit() or len(lengths[0]) > 20:
                return await reject(400, "Invalid Content-Length")
            declared = int(lengths[0])
        if any(value.strip().lower() not in {b"identity", b""} for value in values.get(b"content-encoding", [])):
            return await reject(415, "Compressed request bodies are not supported")
        multipart = any(value.lower().startswith(b"multipart/form-data") for value in values.get(b"content-type", []))
        is_upload = path.rstrip("/") == "/api/quotations/upload" or (path.startswith("/api/quotations/") and path.rstrip("/").endswith("/revisions"))
        maximum = settings.REQUEST_AUTH_MAX_BYTES if path.startswith("/api/auth/") else settings.REQUEST_UPLOAD_MAX_BYTES if multipart and is_upload else settings.REQUEST_JSON_MAX_BYTES
        if declared is not None and declared > maximum:
            return await reject(413, "Request body is too large")
        # Bounded prebuffer prevents handlers from mutating data before a late oversized chunk arrives.
        body = bytearray()
        oversized = False
        try:
            with anyio.fail_after(settings.REQUEST_BODY_TIMEOUT_SECONDS):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > maximum:
                        oversized = True
                        break
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408, "Request body took too long to arrive")
        if oversized:
            return await reject(413, "Request body is too large")
        if declared is not None and declared != len(body):
            return await reject(400, "Request body length does not match Content-Length")
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)
