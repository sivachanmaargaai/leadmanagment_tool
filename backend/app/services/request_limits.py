"""Worker-shared budgets. Own short transactions survive business-request rollback."""
import hashlib
import logging
import math
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, text, case, func, literal, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.rate_limit import RateLimitBucket

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc)


def client_identity(scope):
    # Uvicorn may replace this only when a proxy belongs to its explicit trusted list.
    # Never parse arbitrary X-Forwarded-For / Forwarded headers here.
    return str(scope.get("client", ("unknown", 0))[0]) if scope.get("client") else "unknown"


def postgres_limits(db, keyed, at):
    """Claim a sorted batch atomically; denied rows never increment or reset."""
    seconds = case({key: window for key, _, window in keyed}, value=RateLimitBucket.key)
    maximum = case({key: limit for key, limit, _ in keyed}, value=RateLimitBucket.key)
    expired = func.extract("epoch", literal(at) - RateLimitBucket.window_started_at) >= seconds
    statement = pg_insert(RateLimitBucket).values([
        {"key": key, "window_started_at": at, "count": 1} for key, _, _ in keyed
    ]).on_conflict_do_update(index_elements=["key"], set_={
        "window_started_at": case((expired, at), else_=RateLimitBucket.window_started_at),
        "count": case((expired, 1), else_=RateLimitBucket.count + 1),
    }, where=or_(expired, RateLimitBucket.count < maximum)).returning(RateLimitBucket.key)
    allowed = set(db.scalars(statement).all())
    denied = {key: window for key, _, window in keyed if key not in allowed}
    if not denied:
        return 0
    retry = 0
    for key, started in db.execute(select(RateLimitBucket.key, RateLimitBucket.window_started_at)
                                  .where(RateLimitBucket.key.in_(denied))).all():
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        retry = max(retry, max(1, math.ceil(denied[key] - (at - started).total_seconds())))
    return retry


def enforce_limits(budgets, message="Too many requests. Please try again later"):
    if not settings.RATE_LIMIT_ENABLED:
        return
    at = now()
    retry = 0
    keyed = sorted((hashlib.sha256((scope + ":" + identity).encode()).hexdigest(), maximum, seconds)
                   for scope, identity, maximum, seconds in budgets)
    if not keyed:
        return
    try:
        with SessionLocal() as db:
            if db.bind.dialect.name == "postgresql":
                db.execute(text("SELECT set_config('lock_timeout', '2s', true), set_config('statement_timeout', '3s', true)"))
            if db.bind.dialect.name == "postgresql" and len({key for key, _, _ in keyed}) == len(keyed) and all(limit >= 1 for _, limit, _ in keyed):
                retry = postgres_limits(db, keyed, at)
                db.commit()
                if retry:
                    raise HTTPException(429, message, headers={"Retry-After": str(retry), "Cache-Control": "no-store"})
                return
            insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
            for key, maximum, seconds in keyed:
                db.execute(insert(RateLimitBucket).values(key=key, window_started_at=at, count=0)
                           .on_conflict_do_nothing(index_elements=["key"]))
                bucket = db.scalar(select(RateLimitBucket).where(RateLimitBucket.key == key)
                                   .with_for_update().execution_options(populate_existing=True))
                started = bucket.window_started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                elapsed = (at - started).total_seconds()
                if elapsed >= seconds:
                    bucket.window_started_at, bucket.count = at, 0
                    elapsed = 0
                if bucket.count >= maximum:
                    retry = max(retry, max(1, math.ceil(seconds - elapsed)))
                else:
                    bucket.count += 1
            db.commit()
    except SQLAlchemyError as error:
        logger.warning("Request budget storage unavailable (%s)", type(error).__name__)
        raise HTTPException(503, "Request protection temporarily unavailable. Please retry", headers={"Retry-After": "5", "Cache-Control": "no-store"}) from None
    if retry:
        raise HTTPException(429, message, headers={"Retry-After": str(retry), "Cache-Control": "no-store"})


def enforce_ip_limits(scope):
    identity = client_identity(scope)
    enforce_limits([("api-ip-minute", identity, settings.API_IP_PER_MINUTE, 60),
                    ("api-ip-burst", identity, settings.API_IP_BURST_PER_10_SECONDS, 10)])


def enforce_login_limits(request, email):
    enforce_limits([("login-ip", client_identity(request.scope), settings.LOGIN_IP_PER_15_MINUTES, 900),
                    ("login-email", email, settings.LOGIN_EMAIL_PER_15_MINUTES, 900)],
                   "Too many sign-in attempts. Please try again later")


def enforce_user_limits(request, user_id):
    budgets = [("api-user-minute", user_id, settings.API_USER_PER_MINUTE, 60)]
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        budgets.append(("api-user-writes", user_id, settings.API_USER_WRITES_PER_MINUTE, 60))
    enforce_limits(budgets)
