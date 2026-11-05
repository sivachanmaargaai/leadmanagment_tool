from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.security import get_current_user, now
from app.db.database import get_db
from app.db.operations import database_operation
from app.models.settings import UserPreferences, WorkspaceSettings
from app.models.user import User, UserAuditEvent
from app.schemas.settings import PersonalData, SettingsUpdate, SharedData
from app.services.settings import personal_settings, settings_response, shared_settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
def get_settings(response: Response, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with database_operation(db):
        response.headers["Cache-Control"] = "no-store"
        return settings_response(db, actor)


@router.get("/divisions")
def get_divisions(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with database_operation(db):
        shared, _ = shared_settings(db)
        return [value.model_dump() for value in shared.divisions.values()]


@router.put("")
def update_settings(data: SettingsUpdate, response: Response, actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    with database_operation(db):
        shared_fields = [key for key in ["company", "divisions", "leads", "quotation"] if getattr(data, key) is not None]
        if shared_fields and not actor.is_owner:
            raise HTTPException(403, "Only the Owner can change company and business settings")
        if shared_fields:
            shared, row = shared_settings(db)
            if (row.version if row else 1) != data.expectedSharedVersion:
                raise HTTPException(409, "Shared settings changed. Reload saved settings before retrying")
            values = shared.model_dump(mode="json")
            values.update({key: getattr(data, key).model_dump(mode="json") if key != "divisions" else {name: item.model_dump() for name, item in data.divisions.items()} for key in shared_fields})
            validated = SharedData.model_validate(values)
            if data.quotation and validated.quotation.nextNumber < shared.quotation.nextNumber:
                raise HTTPException(409, "Next quotation number cannot be decreased")
            if row is None:
                db.add(WorkspaceSettings(id=1, data=validated.model_dump(mode="json"), version=2))
                db.flush()
            else:
                changed = db.execute(update(WorkspaceSettings).where(WorkspaceSettings.id == 1, WorkspaceSettings.version == data.expectedSharedVersion)
                    .values(data=validated.model_dump(mode="json"), version=data.expectedSharedVersion + 1, updated_at=now()).execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    db.rollback()
                    raise HTTPException(409, "Shared settings changed. Reload and try again")
                db.refresh(row)
        if any(getattr(data, key) is not None for key in ["profile", "notifications", "workspace"]):
            personal, row = personal_settings(db, actor.id)
            if (row.version if row else 0) != data.expectedPersonalVersion:
                db.rollback()
                raise HTTPException(409, "Your preferences changed. Reload saved settings before retrying")
            values = personal.model_dump()
            for key in ["notifications", "workspace"]:
                if getattr(data, key) is not None:
                    values[key] = getattr(data, key).model_dump()
            if data.profile:
                values.update(phone=data.profile.phone, designation=data.profile.designation)
                if actor.version != data.expectedProfileVersion:
                    db.rollback()
                    raise HTTPException(409, "Your profile changed. Reload saved settings before retrying")
                if data.profile.name != actor.name:
                    changed = db.execute(update(User).where(User.id == actor.id, User.version == data.expectedProfileVersion)
                        .values(name=data.profile.name, version=actor.version + 1).execution_options(synchronize_session=False))
                    if changed.rowcount != 1:
                        db.rollback()
                        raise HTTPException(409, "Your profile changed. Reload and try again")
                    db.refresh(actor)
            values = PersonalData.model_validate(values).model_dump(mode="json")
            if row is None:
                db.add(UserPreferences(user_id=actor.id, data=values, version=1))
                db.flush()
            else:
                changed = db.execute(update(UserPreferences).where(UserPreferences.user_id == actor.id, UserPreferences.version == data.expectedPersonalVersion)
                    .values(data=values, version=data.expectedPersonalVersion + 1, updated_at=now()).execution_options(synchronize_session=False))
                if changed.rowcount != 1:
                    db.rollback()
                    raise HTTPException(409, "Your preferences changed. Reload and try again")
                db.refresh(row)
        db.add(UserAuditEvent(actor_id=actor.id, target_id=actor.id, action="Settings updated",
                             changes={"sharedSections": shared_fields, "personalUpdated": data.expectedPersonalVersion is not None}))
        db.commit()
        response.headers["Cache-Control"] = "no-store"
        return settings_response(db, actor)
