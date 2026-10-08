"""Employer talent search routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.account import VerifiedAccess, current_user
from app.profiles import account_fields_for
from app.talent import DEFAULT_PER_PAGE, MAX_PER_PAGE, search_talent

router = APIRouter(prefix="/api/v1", tags=["talent"])


def _require_employer_search(user: VerifiedAccess) -> None:
    scopes = user.scopes
    if "job:staff" in scopes:
        return
    if "job:employer" not in scopes:
        raise HTTPException(status_code=403, detail="Talent axtarışı işəgötürən hesabı tələb edir")
    fields = account_fields_for(user.subject)
    if not fields["company_profile"].get("complete"):
        raise HTTPException(
            status_code=403,
            detail="Əvvəl şirkət profilini tamamlayın",
        )


@router.get("/talent")
def get_talent(
    q: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_employer_search(user)
    return search_talent(q=q or "", page=page, per_page=per_page)
