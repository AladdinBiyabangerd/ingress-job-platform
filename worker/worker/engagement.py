"""Trigger API engagement jobs (match_new / match_near).

Matching + notifications live in the API process, so the worker POSTs to
POST /api/v1/internal/engagement-jobs with INTERNAL_JOB_TOKEN.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _api_base() -> str:
    direct = (os.environ.get("JOB_API_BASE_URL") or "").strip().rstrip("/")
    if direct:
        return direct
    return (os.environ.get("API_BASE_URL") or "http://127.0.0.1:8010").strip().rstrip("/")


def trigger_engagement_jobs(*, dry_run: bool = False, timeout: float = 120.0) -> dict[str, Any]:
    token = (os.environ.get("INTERNAL_JOB_TOKEN") or "").strip()
    if not token:
        return {"skipped": True, "reason": "INTERNAL_JOB_TOKEN unset"}
    url = f"{_api_base()}/api/v1/internal/engagement-jobs"
    if dry_run:
        url += "?dry_run=true"
    req = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={
            "X-Internal-Token": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body) if body else {}
            if not isinstance(payload, dict):
                return {"ok": False, "reason": "invalid_payload"}
            payload["ok"] = True
            return payload
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:300]
        except Exception:
            detail = str(exc)
        return {"ok": False, "status": exc.code, "reason": detail or str(exc)}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
