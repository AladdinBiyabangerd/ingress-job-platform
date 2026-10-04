"""Signed-in notification list. Guests are rejected by the bearer check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.account import VerifiedAccess, current_user
from app.notifications import list_for, mark_all_read, mark_read

router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.get("/notifications")
def read_notifications(user: VerifiedAccess = Depends(current_user)) -> dict:
    return list_for(user.subject)


@router.post("/notifications/read")
def read_all(user: VerifiedAccess = Depends(current_user)) -> dict:
    return mark_all_read(user.subject)


@router.post("/notifications/{notification_id}/read")
def read_one(notification_id: int, user: VerifiedAccess = Depends(current_user)) -> dict:
    saved = mark_read(user.subject, notification_id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Bildiriş tapılmadı")
    return saved
