"""GET/PUT /api/v1/email-prefs and public unsubscribe (plan §13.1)."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.account import current_user
from app.auth_oidc import VerifiedAccess
from app.cabinet_store import _LOCK, _connect, ensure_schema
from app.digests import run_email_jobs
from app.email_prefs import (
    apply_unsubscribe,
    ensure_email_tables,
    get_prefs,
    parse_unsubscribe_token,
    save_prefs,
)

router = APIRouter(prefix="/api/v1", tags=["email"])


class EmailPrefsBody(BaseModel):
    frequency: str | None = Field(default=None, max_length=32)
    digest: bool | None = None
    high_match: bool | None = None
    profile_nudge: bool | None = None
    language: str | None = Field(default=None, max_length=8)
    send_weekday: int | None = Field(default=None, ge=0, le=6)


def _require_candidate(user: VerifiedAccess) -> None:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Namizəd hesabı tələb edir")


@router.get("/email-prefs")
def read_email_prefs(user: VerifiedAccess = Depends(current_user)) -> dict:
    _require_candidate(user)
    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            ensure_email_tables(conn)
            return get_prefs(conn, user.subject)
        finally:
            conn.close()


@router.put("/email-prefs")
def put_email_prefs(
    body: EmailPrefsBody,
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    _require_candidate(user)
    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            ensure_email_tables(conn)
            prefs = save_prefs(
                conn,
                user.subject,
                frequency=body.frequency,
                digest=body.digest,
                high_match=body.high_match,
                profile_nudge=body.profile_nudge,
                language=body.language,
                send_weekday=body.send_weekday,
                clear_unsubscribe=body.frequency is not None and body.frequency != "none",
            )
            conn.commit()
            return prefs
        finally:
            conn.close()


@router.get("/unsubscribe/{token}")
def unsubscribe_status(token: str) -> dict:
    user_id = parse_unsubscribe_token(token)
    if not user_id:
        raise HTTPException(status_code=404, detail="invalid_token")
    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            prefs = get_prefs(conn, user_id)
        finally:
            conn.close()
    return {
        "valid": True,
        "frequency": prefs.get("frequency"),
        "unsubscribed": bool((prefs.get("unsubscribed_at") or "").strip())
        or prefs.get("frequency") == "none"
        or not prefs.get("emails_consent"),
    }


@router.post("/unsubscribe/{token}")
def unsubscribe_apply(token: str) -> dict:
    user_id = parse_unsubscribe_token(token)
    if not user_id:
        raise HTTPException(status_code=404, detail="invalid_token")
    ensure_schema(create=True)
    with _LOCK:
        conn = _connect()
        try:
            prefs = apply_unsubscribe(conn, user_id)
            conn.commit()
        finally:
            conn.close()
    return {
        "ok": True,
        "frequency": prefs.get("frequency"),
        "unsubscribed": True,
    }


@router.post("/internal/email-jobs")
def trigger_email_jobs(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    dry_run: bool = Query(default=False),
) -> dict:
    """Worker trigger for digests + high-match alerts."""
    expected = (os.environ.get("INTERNAL_JOB_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="internal_jobs_disabled")
    provided = (x_internal_token or "").strip()
    if not provided or provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")
    return run_email_jobs(dry_run=dry_run)
