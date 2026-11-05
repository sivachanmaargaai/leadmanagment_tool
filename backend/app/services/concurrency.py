from fastapi import HTTPException
from sqlalchemy import update
from app.services.crm_access import actor


def expected_version(db, record, expected):
    if expected is None:
        if actor(db) is not None:
            raise HTTPException(428, "Reload this record and send expectedVersion before changing or deleting it")
        # Trusted direct service calls retain compatibility; HTTP callers cannot omit the version.
        expected = record.version
    if expected != record.version:
        raise HTTPException(409, "This record changed in another session. Reload before retrying")
    return expected


def claim_version(db, model, record, expected):
    expected = expected_version(db, record, expected)
    query = update(model).where(model.id == record.id, model.version == expected)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    result = db.execute(query.values(version=model.version + 1).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        raise HTTPException(409, "This record changed in another session. Reload before retrying")
    db.refresh(record)
