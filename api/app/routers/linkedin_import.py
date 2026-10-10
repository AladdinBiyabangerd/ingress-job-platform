"""POST /api/v1/import/linkedin-jobs for the Chrome extension (token auth)."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.linkedin_import import import_jobs

router = APIRouter(prefix="/api/v1/import", tags=["import"])

MAX_BATCH = 200


class LinkedInJobIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    linkedin_id: str = Field(max_length=20)
    title: str = Field(max_length=300)
    company: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=300)
    description: str = Field(default="", max_length=60000)
    apply_url: str = Field(default="", max_length=2000)
    posted: str = Field(default="", max_length=100)
    employment_type: str = Field(default="", max_length=100)
    remote: bool = False


class LinkedInBatchIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    jobs: list[LinkedInJobIn] = Field(max_length=MAX_BATCH)


def _token(authorization: str | None, x_import_token: str | None) -> str:
    if x_import_token:
        return x_import_token.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


@router.post("/linkedin-jobs")
def linkedin_jobs(
    body: LinkedInBatchIn,
    authorization: str | None = Header(default=None),
    x_import_token: str | None = Header(default=None, alias="X-Import-Token"),
) -> dict:
    expected = (os.environ.get("JOB_IMPORT_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="import_disabled")
    provided = _token(authorization, x_import_token)
    if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="unauthorized")
    return import_jobs([job.model_dump() for job in body.jobs])
