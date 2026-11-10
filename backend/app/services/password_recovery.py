import logging
import math
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.config import settings
from app.core.security import now, token_hash, utc
from app.db.database import SessionLocal
from app.models.password_reset import PasswordResetToken, RecoveryRateBucket
from app.models.user import User
from app.services.mailer import send_otp_message

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
    return allowed, window_wait if bucket.count >= maximum else max(1, cooldown_wait)


def deliver_password_reset(email, challenge):
    """Persist only hashes. Challenge is a random secret, separately delivered to the browser."""
    reset_id = None
    try:
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)).with_for_update())
            if user is None:
                return
            at = now()
            db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id,
                PasswordResetToken.consumed_at.is_(None)).values(consumed_at=at))
            code = f"{secrets.randbelow(1000000):06d}"
            token = PasswordResetToken(user_id=user.id, user_version=user.version, token_hash=token_hash(challenge),
                recovery_kind="otp", otp_hash=token_hash(challenge + ":" + code),
                expires_at=at + timedelta(minutes=settings.OTP_MINUTES))
            db.add(token)
            db.commit()
            reset_id = token.id
            send_otp_message(user.email, code, settings.OTP_MINUTES)
            # Do not revive a challenge invalidated by a resend/account change.
            db.execute(update(PasswordResetToken).where(PasswordResetToken.id == reset_id,
                PasswordResetToken.consumed_at.is_(None)).values(delivery_status="sent"))
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
