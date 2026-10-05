"""Candidate consent storage + copy (Phase 1.3).

Plan §12: consent(user_id, kind, granted, version, ts, ip, ua)
Plan §13.1: GET/PUT /api/consents
Copy source: docs/cv-ai/consent-copy-v1.json (stub pending legal review).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

CONSENT_KINDS = ("matching", "emails", "recruiter_visibility")
VISIBILITY_LEVELS = ("hidden", "anonymous", "public")
LOCALES = ("az", "en", "ru")

COPY_PATH = Path(__file__).resolve().parents[2] / "docs" / "cv-ai" / "consent-copy-v1.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS consent (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    granted INTEGER NOT NULL DEFAULT 0,
    version TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL,
    ip TEXT NOT NULL DEFAULT '',
    ua TEXT NOT NULL DEFAULT '',
    UNIQUE (user_id, kind)
);

CREATE INDEX IF NOT EXISTS consent_user ON consent(user_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_consent_tables(conn) -> None:
    conn.executescript(SCHEMA)


@lru_cache(maxsize=1)
def load_consent_copy() -> dict:
    with COPY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("consent copy must be an object")
    return data


def _pick_locale(lang: str | None) -> str:
    code = (lang or "az").strip().lower()[:2]
    return code if code in LOCALES else "az"


def _localized(value: object, lang: str) -> str:
    if isinstance(value, dict):
        text = value.get(lang) or value.get("az") or value.get("en") or ""
        return text if isinstance(text, str) else ""
    return value if isinstance(value, str) else ""


def _client_meta(request) -> tuple[str, str]:
    if request is None:
        return "", ""
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "") or ""
    ua = (request.headers.get("user-agent") or "")[:500]
    return ip[:80], ua


def _visibility_for(conn, user_id: str, defaults: dict) -> str:
    ensure_consent_tables(conn)
    from app.cv_queue import ensure_cv_queue_tables

    ensure_cv_queue_tables(conn)
    row = conn.execute(
        "SELECT visibility FROM candidate_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is not None:
        value = row["visibility"] if "visibility" in row.keys() else row[0]
        if value in VISIBILITY_LEVELS:
            return value
    default = defaults.get("visibility") if isinstance(defaults, dict) else None
    return default if default in VISIBILITY_LEVELS else "anonymous"


def _grants_for(conn, user_id: str) -> dict[str, dict]:
    ensure_consent_tables(conn)
    rows = conn.execute(
        """
        SELECT kind, granted, version, ts
        FROM consent
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    out: dict[str, dict] = {}
    for row in rows:
        kind = row["kind"] if "kind" in row.keys() else row[0]
        if kind not in CONSENT_KINDS:
            continue
        granted = row["granted"] if "granted" in row.keys() else row[1]
        version = row["version"] if "version" in row.keys() else row[2]
        ts = row["ts"] if "ts" in row.keys() else row[3]
        out[kind] = {
            "granted": bool(int(granted)),
            "version": version or "",
            "ts": ts or None,
        }
    return out


def read_consents(*, user_id: str, lang: str | None = None) -> dict:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return consents_payload(conn, user_id=user_id, lang=lang)
        finally:
            conn.close()


def write_consents(
    *,
    user_id: str,
    grants: dict[str, bool],
    visibility: str | None = None,
    request=None,
    lang: str | None = None,
) -> dict:
    from app.cabinet_store import _LOCK, _connect

    with _LOCK:
        conn = _connect()
        try:
            return save_consents(
                conn,
                user_id=user_id,
                grants=grants,
                visibility=visibility,
                request=request,
                lang=lang,
            )
        finally:
            conn.close()


def consents_payload(conn, *, user_id: str, lang: str | None = None) -> dict:
    copy = load_consent_copy()
    locale = _pick_locale(lang)
    defaults = copy.get("defaults") if isinstance(copy.get("defaults"), dict) else {}
    grants = _grants_for(conn, user_id)
    items = []
    for entry in copy.get("consents") or []:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind not in CONSENT_KINDS:
            continue
        stored = grants.get(kind) or {}
        default_granted = bool(entry.get("default_granted", defaults.get(kind, False)))
        items.append(
            {
                "kind": kind,
                "granted": bool(stored["granted"]) if "granted" in stored else default_granted,
                "default_granted": default_granted,
                "checkbox_label": _localized(entry.get("checkbox_label"), locale),
                "short_help": _localized(entry.get("short_help"), locale),
                "detail": _localized(entry.get("detail"), locale),
                "version": stored.get("version") or "",
                "ts": stored.get("ts"),
            }
        )
    levels = []
    for level in copy.get("visibility_levels") or []:
        if not isinstance(level, dict):
            continue
        level_id = level.get("id")
        if level_id not in VISIBILITY_LEVELS:
            continue
        levels.append(
            {
                "id": level_id,
                "label": _localized(level.get("label"), locale),
                "description": _localized(level.get("description"), locale),
            }
        )
    rights = []
    for entry in copy.get("privacy_rights") or []:
        if not isinstance(entry, dict):
            continue
        right_id = str(entry.get("id") or "").strip()
        if not right_id:
            continue
        rights.append(
            {
                "id": right_id,
                "label": _localized(entry.get("label"), locale),
                "description": _localized(entry.get("description"), locale),
            }
        )
    return {
        "version": str(copy.get("version") or ""),
        "status": str(copy.get("status") or ""),
        "lang": locale,
        "intro": _localized(copy.get("cv_upload_intro"), locale),
        "legal_disclaimer": _localized(copy.get("legal_disclaimer"), locale),
        "retention_stub": _localized(copy.get("retention_stub"), locale),
        "consents": items,
        "visibility": _visibility_for(conn, user_id, defaults),
        "visibility_levels": levels,
        "privacy_rights": rights,
    }


def _set_visibility(conn, *, user_id: str, visibility: str) -> None:
    from app.cv_queue import ensure_cv_queue_tables

    ensure_cv_queue_tables(conn)
    now = _now()
    existing = conn.execute(
        "SELECT id FROM candidate_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if existing is not None:
        conn.execute(
            """
            UPDATE candidate_profile
            SET visibility = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (visibility, now, user_id),
        )
        return
    conn.execute(
        """
        INSERT INTO candidate_profile (
            user_id, cv_file_key, data, headline, seniority, total_years,
            status, parse_method, confidence, visibility, updated_at
        ) VALUES (?, '', '{}', '', '', NULL, 'draft', '', NULL, ?, ?)
        """,
        (user_id, visibility, now),
    )


def save_consents(
    conn,
    *,
    user_id: str,
    grants: dict[str, bool],
    visibility: str | None = None,
    request=None,
    lang: str | None = None,
) -> dict:
    ensure_consent_tables(conn)
    subject = (user_id or "").strip()
    if not subject:
        raise ValueError("user_id")
    copy = load_consent_copy()
    version = str(copy.get("version") or "1.0")
    ip, ua = _client_meta(request)
    now = _now()
    for kind, granted in grants.items():
        if kind not in CONSENT_KINDS:
            raise ValueError(f"kind:{kind}")
        conn.execute(
            """
            INSERT INTO consent (user_id, kind, granted, version, ts, ip, ua)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, kind) DO UPDATE SET
                granted = excluded.granted,
                version = excluded.version,
                ts = excluded.ts,
                ip = excluded.ip,
                ua = excluded.ua
            """,
            (subject, kind, 1 if granted else 0, version, now, ip, ua),
        )
    if visibility is not None:
        if visibility not in VISIBILITY_LEVELS:
            raise ValueError("visibility")
        _set_visibility(conn, user_id=subject, visibility=visibility)
    conn.commit()
    return consents_payload(conn, user_id=subject, lang=lang)
