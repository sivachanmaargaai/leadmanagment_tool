import hashlib
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.operations import database_operation
from app.models.user import AccessToken, AuthSession, User
from app.models.role_permissions import RolePermissions
from app.services.permissions import attach_role_permissions
from app.services.request_limits import enforce_user_limits

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
COOKIE_NAME = "engen_refresh"
COOKIE_PATH = "/api/auth"


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)


def unauthorized():
    return HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})


def session_active(session, user, at):
    return session is not None and user is not None and user.is_active and session.revoked_at is None and utc(session.expires_at) > at


def get_current_user(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
                     db: Session = Depends(get_db)):
    if credentials is None or len(credentials.credentials) > 256:
        raise unauthorized()
    with database_operation(db):
        result = db.execute(select(AccessToken, AuthSession, User, RolePermissions).select_from(AccessToken).join(AuthSession, AuthSession.id == AccessToken.session_id)
                            .join(User, User.id == AuthSession.user_id).outerjoin(RolePermissions, RolePermissions.role == "Staff").where(
                                AccessToken.token_hash == token_hash(credentials.credentials))).first()
        if result is None:
            raise unauthorized()
        token, session, user, policy = result
        attach_role_permissions(user, policy)
        at = now()
        if not session_active(session, user, at) or utc(token.expires_at) <= at:
            raise unauthorized()
        enforce_user_limits(request, user.id)
        return user


def require_auth_request(request: Request):
    # Cookie endpoints require a non-simple request header; browsers must preflight it.
    if request.headers.get("X-CRM-Request") != "1":
        raise HTTPException(403, "Missing authentication request header")
    origin = request.headers.get("Origin")
    if origin is not None and origin not in settings.ALLOWED_ORIGINS:
        raise HTTPException(403, "Authentication origin is not allowed")


def require_quotation_user(user: User = Depends(get_current_user)):
    from app.services.permissions import require_quotations
    require_quotations(user)
    return user
