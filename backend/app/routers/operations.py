from fastapi import APIRouter, Depends, HTTPException, Response
from app.core.security import get_current_user
from app.services.operations import operations_status, probe_database

router = APIRouter(prefix="/api", tags=["Operations"])


@router.get("/ready")
def ready(response: Response):
    result = probe_database()
    response.headers["Cache-Control"] = "no-store"
    if not result["reachable"] or not result["schemaCurrent"]:
        response.status_code = 503
        return {"status": "not-ready"}
    return {"status": "ready"}


@router.get("/ops/status")
def status(response: Response, user=Depends(get_current_user)):
    if not user.is_owner:
        raise HTTPException(403, "Only the workspace Owner can view operations status")
    response.headers["Cache-Control"] = "no-store"
    return operations_status()
