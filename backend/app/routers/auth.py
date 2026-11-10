from datetime import timedelta
import secrets
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (COOKIE_NAME, COOKIE_PATH, DUMMY_HASH, bearer, get_current_user,
                               new_token, now, passwords, require_auth_request, session_active, token_hash, unauthorized, utc)
from app.db.database import get_db
from app.db.operations import database_operation
from app.models.user import AccessToken, AuthSession, RefreshToken, User
from app.models.password_reset import PasswordResetToken
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, LoginResponse, PasswordChange, ResetPasswordRequest, UserResponse, VerifyRecoveryOtpRequest
from app.services.password_recovery import consume_limit, deliver_password_reset
from app.services.request_limits import enforce_login_limits
from app.services.permissions import resolve_role_permissions

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def recovery_available():
    if not settings.PASSWORD_RECOVERY_ENABLED:
        raise HTTPException(503, "Password recovery email is not configured. Contact your workspace Owner", headers={"Cache-Control": "no-store"})


@router.post("/forgot-password", status_code=202, dependencies=[Depends(require_auth_request)])
def forgot_password(data: ForgotPasswordRequest, request: Request, response: Response,
                    background: BackgroundTasks, db: Session = Depends(get_db)):
    recovery_available()
    with database_operation(db):
        allowed, wait = consume_limit(db, "forgot-ip", request.client.host if request.client else "unknown", 10, 900)
        if not allowed:
            raise HTTPException(429, "Too many recovery requests. Try again later", headers={"Retry-After": str(wait), "Cache-Control": "no-store"})
        allowed, wait = consume_limit(db, "forgot-email", data.email, 3, 1800, 60)
        if not allowed:
            raise HTTPException(429, "Please wait before requesting another code", headers={"Retry-After": str(wait), "Cache-Control": "no-store"})
        challenge = new_token()
        # Unknown/inactive addresses get the same response and random challenge shape.
        background.add_task(deliver_password_reset, data.email, challenge)
        response.headers["Cache-Control"] = "no-store"
        return {"message": "If an active account matches that email, a password reset code will be sent. Check your inbox and spam folder.",
                "challengeId": challenge, "expiresInMinutes": settings.OTP_MINUTES, "resendAfterSeconds": 60}


@router.post("/verify-reset-otp", dependencies=[Depends(require_auth_request)])
def verify_reset_otp(data: VerifyRecoveryOtpRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    recovery_available()
    with database_operation(db):
        allowed, wait = consume_limit(db, "otp-ip", request.client.host if request.client else "unknown", 20, 900)
        if not allowed:
            raise HTTPException(429, "Too many code attempts. Try again later", headers={"Retry-After": str(wait), "Cache-Control": "no-store"})
        invalid = HTTPException(400, "Code is invalid, expired or already used. Request a new code if needed", headers={"Cache-Control": "no-store"})
        token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(data.challengeId)))
        if token is None:
            raise invalid
        user = db.scalar(select(User).where(User.id == token.user_id).with_for_update().execution_options(populate_existing=True))
        token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.id == token.id).with_for_update().execution_options(populate_existing=True))
        at = now()
        if (user is None or token is None or not user.is_active or token.recovery_kind != "otp"
                or token.consumed_at is not None or token.verified_at is not None or token.delivery_status != "sent"
                or utc(token.expires_at) <= at or token.user_version != user.version or token.failed_attempts >= 5):
            raise invalid
        if not secrets.compare_digest(token.otp_hash or "", token_hash(data.challengeId + ":" + data.code)):
            token.failed_attempts += 1
            if token.failed_attempts >= 5:
                token.consumed_at = at
            db.commit()  # Failed attempts must survive database_operation's error rollback.
            raise invalid
        grant = new_token()
        token.token_hash, token.otp_hash, token.verified_at = token_hash(grant), None, at
        token.expires_at = at + timedelta(minutes=5)
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return {"resetToken": grant, "expiresInMinutes": 5}


@router.post("/reset-password", status_code=204, dependencies=[Depends(require_auth_request)])
def reset_password(data: ResetPasswordRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    recovery_available()
    with database_operation(db):
        allowed, wait = consume_limit(db, "reset-ip", request.client.host if request.client else "unknown", 20, 900)
        if not allowed:
            raise HTTPException(429, "Too many reset attempts. Try again later", headers={"Retry-After": str(wait), "Cache-Control": "no-store"})
        invalid = HTTPException(400, "Password reset authorization is invalid, expired or already used. Request a new code", headers={"Cache-Control": "no-store"})
        token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(data.token)))
        if token is None:
            raise invalid
        # Always lock the user before token rows to avoid deadlocks between two reset links.
        user = db.scalar(select(User).where(User.id == token.user_id).with_for_update().execution_options(populate_existing=True))
        token = db.scalar(select(PasswordResetToken).where(PasswordResetToken.id == token.id).with_for_update().execution_options(populate_existing=True))
        at = now()
        if (user is None or token is None or not user.is_active or token.consumed_at is not None
                or utc(token.expires_at) <= at or token.user_version != user.version
                or (token.recovery_kind == "otp" and token.verified_at is None)):
            raise invalid
        changed = db.execute(update(User).where(User.id == user.id, User.version == token.user_version)
            .values(password_hash=passwords.hash(data.newPassword), version=user.version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise invalid
        db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None)).values(consumed_at=at))
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=at))
        from app.models.user import UserAuditEvent
        db.add(UserAuditEvent(actor_id=user.id, target_id=user.id, action="Password recovered", changes={"sessionsRevoked": True}))
        db.commit()
        clear_cookie(response)


def clear_cookie(response):
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=settings.COOKIE_SECURE, httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


def denied_refresh():
    response = JSONResponse({"detail": "Sign in to continue"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
    clear_cookie(response)
    return response


def issue_tokens(db, session, user, response, at):
    access, refresh = new_token(), new_token()
    expires_at = min(at + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES), utc(session.expires_at))
    db.add(AccessToken(session_id=session.id, token_hash=token_hash(access), expires_at=expires_at))
    db.add(RefreshToken(session_id=session.id, token_hash=token_hash(refresh)))
    db.commit()
    response.set_cookie(COOKIE_NAME, refresh, max_age=max(0, int((utc(session.expires_at) - at).total_seconds())),
                        expires=utc(session.expires_at), path=COOKIE_PATH, httponly=True, secure=settings.COOKIE_SECURE, samesite="strict")
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(access_token=access, expires_in=int((expires_at - at).total_seconds()), user=UserResponse.model_validate(resolve_role_permissions(db, user)))


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(require_auth_request)])
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_login_limits(request, data.email)
    with database_operation(db):
        user = db.scalar(select(User).where(User.email == data.email))
        verified, replacement = passwords.verify_and_update(data.password, user.password_hash if user else DUMMY_HASH)
        if not verified or user is None or not user.is_active:
            raise unauthorized()
        if replacement:
            user.password_hash = replacement
        at = now()
        session = AuthSession(user_id=user.id, expires_at=at + timedelta(days=settings.SESSION_DAYS))
        db.add(session)
        db.flush()
        return issue_tokens(db, session, user, response, at)


@router.post("/refresh", response_model=LoginResponse, dependencies=[Depends(require_auth_request)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE_NAME)
    if not raw or len(raw) > 256:
        return denied_refresh()
    with database_operation(db):
        # The consumed marker is retained so any old refresh-token replay revokes its session.
        token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw)).with_for_update())
        if token is None:
            return denied_refresh()
        session = db.scalar(select(AuthSession).where(AuthSession.id == token.session_id).with_for_update())
        user = db.get(User, session.user_id) if session else None
        at = now()
        if not session_active(session, user, at):
            return denied_refresh()
        if token.consumed_at is not None:
            session.revoked_at = at
            db.commit()
            return denied_refresh()
        token.consumed_at = at
        return issue_tokens(db, session, user, response, at)


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204, dependencies=[Depends(require_auth_request)])
def logout(request: Request, response: Response,
           credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: Session = Depends(get_db)):
    with database_operation(db):
        session_ids = set()
        raw = request.cookies.get(COOKIE_NAME)
        if raw and len(raw) <= 256:
            token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(raw)))
            if token:
                session_ids.add(token.session_id)
        if credentials and len(credentials.credentials) <= 256:
            token = db.scalar(select(AccessToken).where(AccessToken.token_hash == token_hash(credentials.credentials)))
            if token:
                session_ids.add(token.session_id)
        if session_ids:
            db.execute(update(AuthSession).where(AuthSession.id.in_(session_ids)).values(revoked_at=now()))
            db.commit()
        clear_cookie(response)


@router.post("/logout-all", status_code=204, dependencies=[Depends(require_auth_request)])
def logout_all(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with database_operation(db):
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
        db.commit()
        clear_cookie(response)


@router.post("/change-password", status_code=204, dependencies=[Depends(require_auth_request)])
def change_password(data: PasswordChange, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with database_operation(db):
        if not passwords.verify(data.currentPassword, user.password_hash):
            raise HTTPException(400, "Current password is incorrect")
        changed = db.execute(update(User).where(User.id == user.id, User.version == user.version)
            .values(password_hash=passwords.hash(data.newPassword), version=user.version + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            raise HTTPException(409, "Account changed. Sign in again before changing your password")
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
        from app.models.user import UserAuditEvent
        db.add(UserAuditEvent(actor_id=user.id, target_id=user.id, action="Password changed", changes={"sessionsRevoked": True}))
        db.commit()
        clear_cookie(response)
