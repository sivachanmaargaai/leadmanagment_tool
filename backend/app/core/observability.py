"""Bounded per-worker metrics and privacy-safe request logs."""
from collections import deque
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from threading import Lock
import time
from uuid import UUID, uuid4

from starlette.responses import JSONResponse
from app.core.config import settings
from app.services.ops_files import root_path, secure_directory

logger = logging.getLogger("engen.operations")
logger.addHandler(logging.NullHandler())
logger.propagate = False
_logging_lock = Lock()
_handler = None
_logging_users = 0
_previous_access_disabled = False


def start_logging():
    global _handler, _logging_users, _previous_access_disabled
    if not settings.OPS_LOG_ENABLED:
        return False
    with _logging_lock:
        if _handler is None:
            root = secure_directory(root_path())
            directory = secure_directory(root / "logs")
            _handler = RotatingFileHandler(directory / f"api-{os.getpid()}.jsonl", maxBytes=settings.OPS_LOG_MAX_BYTES,
                                          backupCount=settings.OPS_LOG_BACKUP_COUNT, encoding="utf-8")
            _handler.setFormatter(logging.Formatter("%(message)s"))
            logger.setLevel(logging.INFO)
            logger.propagate = False
            logger.addHandler(_handler)
            access_logger = logging.getLogger("uvicorn.access")
            _previous_access_disabled = access_logger.disabled
            access_logger.disabled = True  # Raw access logs may contain query strings/customer searches.
        _logging_users += 1
    return True


def stop_logging(enabled):
    global _handler, _logging_users
    if not enabled:
        return
    with _logging_lock:
        _logging_users -= 1
        if _logging_users == 0 and _handler is not None:
            logger.removeHandler(_handler)
            _handler.close()
            _handler = None
            logging.getLogger("uvicorn.access").disabled = _previous_access_disabled


class Metrics:
    def __init__(self):
        self.lock = Lock()
        self.started = time.monotonic()
        self.requests = self.errors = self.limited = self.oversized = self.slow = 0
        self.latency_total = 0
        self.routes = {}
        self.recent = deque(maxlen=5)

    def record(self, route, status, seconds):
        minute = int(time.monotonic() // 60)
        with self.lock:
            self.requests += 1
            self.errors += status >= 500
            self.limited += status == 429
            self.oversized += status == 413
            self.slow += seconds >= settings.OPS_SLOW_REQUEST_SECONDS
            self.latency_total += seconds
            if route not in self.routes and len(self.routes) >= 127:
                route = "other"
            self.routes[route] = self.routes.get(route, 0) + 1
            if not self.recent or self.recent[-1][0] != minute:
                self.recent.append([minute, 0, 0])
            self.recent[-1][1] += 1
            self.recent[-1][2] += status >= 500

    def snapshot(self):
        minute = int(time.monotonic() // 60)
        with self.lock:
            return {"scope": "current-worker", "uptimeSeconds": round(time.monotonic() - self.started),
                    "requests": self.requests, "serverErrors": self.errors, "rateLimited": self.limited,
                    "oversizedRequests": self.oversized, "slowRequests": self.slow,
                    "averageLatencyMs": round(self.latency_total * 1000 / self.requests, 2) if self.requests else 0,
                    "recentServerErrors": sum(item[2] for item in self.recent if item[0] > minute - 5),
                    "routes": dict(self.routes)}


metrics = Metrics()


class ObservabilityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            return await self.app(scope, receive, send)
        request_id = str(uuid4())
        supplied = next((value for key, value in scope.get("headers", []) if key.lower() == b"x-request-id"), b"")
        if len(supplied) == 36:
            try:
                request_id = str(UUID(supplied.decode("ascii")))
            except (ValueError, UnicodeError):
                pass
        scope["request_id"] = request_id
        started, status, sent, error_type = time.monotonic(), 500, False, None

        async def observed_send(message):
            nonlocal status, sent
            if message["type"] == "http.response.start":
                status, sent = message["status"], True
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", request_id.encode())]}
            await send(message)
        try:
            await self.app(scope, receive, observed_send)
        except Exception as error:
            error_type = type(error).__name__
            status = 500
            if sent:
                raise
            response = JSONResponse({"detail": "Unexpected server error. Contact the administrator with the request ID.", "requestId": request_id},
                                    500, headers={"Cache-Control": "no-store"})
            await response(scope, receive, observed_send)
        finally:
            seconds = time.monotonic() - started
            route = getattr(scope.get("route"), "path", "unmatched")
            # Fixed route templates only: never raw path/query/body/headers/user identity.
            if not route.startswith("/api/") or len(route) > 160:
                route = "unmatched"
            metrics.record(route, status, seconds)
            event = {"at": datetime.now(timezone.utc).isoformat(), "event": "api_request", "requestId": request_id,
                     "route": route, "method": scope.get("method") if scope.get("method") in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"} else "OTHER",
                     "status": status, "durationMs": round(seconds * 1000, 2)}
            if error_type:
                event["errorType"] = error_type
            logger.log(logging.ERROR if status >= 500 else logging.WARNING if status == 429 else logging.INFO, json.dumps(event, separators=(",", ":")))
