"""Candidate's own applications, and CV download for people allowed to read it."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response

from app.account import VerifiedAccess, current_user
from app.applications import application_cv, list_for_candidate, withdraw
from app.cabinet_store import CabinetError

router = APIRouter(prefix="/api/v1", tags=["applications"])

_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _run(action):
    try:
        return action()
    except CabinetError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


@router.get("/applications")
def mine(user: VerifiedAccess = Depends(current_user)) -> dict:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Müraciətlər namizəd hesabı tələb edir")
    return {"items": list_for_candidate(user.subject)}


@router.get("/applications/{application_id}/cv")
def download_cv(application_id: int, user: VerifiedAccess = Depends(current_user)):
    data, name = _run(
        lambda: application_cv(
            application_id,
            subject=user.subject,
            staff="job:staff" in user.scopes,
        )
    )
    media = _TYPES.get(Path(name).suffix.lower(), "application/octet-stream")
    safe = Path(name).name.replace('"', "") or "cv"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.delete("/applications/{application_id}", status_code=204)
def withdraw_mine(application_id: int, user: VerifiedAccess = Depends(current_user)) -> Response:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Müraciətlər namizəd hesabı tələb edir")
    _run(lambda: withdraw(application_id, user.subject))
    return Response(status_code=204)
