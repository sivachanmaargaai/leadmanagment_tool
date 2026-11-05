import logging
import math
from datetime import timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.core.security import new_token, now, token_hash, utc
from app.db.database import SessionLocal
from app.models.password_reset import PasswordResetToken, RecoveryRateBucket
from app.models.user import User
from app.services.mailer import send_reset_message

logger = logging.getLogger(__name__)


def consume_limit(db, scope, identity, maximum, window_seconds, cooldown_seconds=0):
    at = now()
    key = token_hash(scope + ":" + identity)
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    db.execute(insert(RecoveryRateBucket).values(key=key, window_started_at=at, count=0)
               .on_conflict_do_nothing(index_elements=["key"]))
    bucket = db.scalar(select(RecoveryRateBucket).where(RecoveryRateBucket.key == key).with_for_update().execution_options(populate_existing=True))
    elapsed = (at - utc(bucket.window_started_at)).total_seconds()
    if elapsed >= window_seconds:
        bucket.window_started_at, bucket.count = at, 0
    window_wait = max(1, math.ceil(window_seconds - (at - utc(bucket.window_started_at)).total_seconds()))
    cooldown_wait = max(0, math.ceil(cooldown_seconds - (at - utc(bucket.last_allowed_at)).total_seconds())) if bucket.last_allowed_at else 0
    allowed = bucket.count < maximum and cooldown_wait <= 0
    if allowed:
        bucket.count += 1
        bucket.last_allowed_at = at
    db.commit()
    return allowed, cooldown_wait if cooldown_wait > 0 else window_wait


def deliver_password_reset(email):
    """Background task owns its database sessions; raw reset tokens never persist or log."""
    reset_id = None
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
            if user is None:
                return
            raw = new_token()
            token = PasswordResetToken(user_id=user.id, user_version=user.version, token_hash=token_hash(raw),
                                       expires_at=now() + timedelta(minutes=settings.RESET_LINK_MINUTES))
            db.add(token)
            db.commit()
            reset_id = token.id
            link = settings.RESET_BASE_URL.rstrip("/") + "/#reset-password?" + urlencode({"token": raw})
            send_reset_message(user.email, link, settings.RESET_LINK_MINUTES)
            token.delivery_status = "sent"
            db.commit()
    except Exception as error:
        # SMTP exceptions may contain addresses or provider data: never log their messages/tracebacks.
        logger.warning("Password recovery delivery failed (%s)", type(error).__name__)
        if reset_id:
            try:
                with SessionLocal() as db:
                    token = db.get(PasswordResetToken, reset_id)
                    if token:
                        token.delivery_status, token.consumed_at = "failed", now()
                        db.commit()
            except Exception:
                logger.warning("Password recovery delivery status could not be recorded")
