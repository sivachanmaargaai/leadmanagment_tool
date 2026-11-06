from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.security import get_current_user, now
from app.db.database import get_db
from app.db.operations import database_operation
from app.models.role_permissions import RolePermissions
from app.models.user import AuthSession, User, UserAuditEvent

router = APIRouter(prefix="/api/permissions", tags=["Roles & permissions"])


def require_admin(user: User = Depends(get_current_user)):
    if user.role != "Admin":
        raise HTTPException(403, "Only administrators can manage role permissions")
    return user


class StaffPermissionsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quotations: StrictBool
    expectedVersion: int = Field(ge=1)


def payload(row):
    return {"version": row.version if row else 1,
            "roles": {"Admin": {"quotations": True, "readOnly": True},
                      "Staff": {"quotations": bool(row and row.quotations), "readOnly": False}}}


@router.get("")
def get_permissions(response: Response, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    with database_operation(db):
        response.headers["Cache-Control"] = "no-store"
        return payload(db.get(RolePermissions, "Staff"))


@router.put("/staff")
def save_staff_permissions(data: StaffPermissionsUpdate, response: Response, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    with database_operation(db):
        row = db.scalar(select(RolePermissions).where(RolePermissions.role == "Staff").with_for_update().execution_options(populate_existing=True))
        if (row.version if row else 1) != data.expectedVersion:
            raise HTTPException(409, "Role permissions changed. Reload before saving")
        previous = bool(row and row.quotations)
        if previous != data.quotations:
            if row is None:
                row = RolePermissions(role="Staff", quotations=data.quotations, version=2)
                db.add(row); db.flush()
            else:
                result = db.execute(update(RolePermissions).where(RolePermissions.role == "Staff", RolePermissions.version == data.expectedVersion)
                    .values(quotations=data.quotations, version=RolePermissions.version + 1, updated_at=now()).execution_options(synchronize_session=False))
                if result.rowcount != 1:
                    raise HTTPException(409, "Role permissions changed. Reload before saving")
            db.execute(update(AuthSession).where(AuthSession.user_id.in_(select(User.id).where(User.role == "Staff")), AuthSession.revoked_at.is_(None)).values(revoked_at=now()))
            db.add(UserAuditEvent(actor_id=user.id, target_id=user.id, action="Role permissions changed",
                changes={"role": "Staff", "before": {"quotations": previous}, "after": {"quotations": data.quotations}, "staffSessionsRevoked": True}))
            db.commit(); db.refresh(row)
        response.headers["Cache-Control"] = "no-store"
        return payload(row)
