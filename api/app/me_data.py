"""Candidate data export + hard-delete (plan §10.3).

GET  /api/v1/me/export — JSON + original CV files (zip)
DELETE /api/v1/me     — hard-delete profile/skills/CV/email prefs;
                        audit rows keep a pseudonymous id only.

Account identity stays on GET /api/v1/me (collision with plan path → /export).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone

from app.applications import delete_stored_cv, normalize_cv_key, read_stored_cv
from app.cabinet_store import _LOCK, _connect
from app.consents import ensure_consent_tables
from app.cv_profile import ensure_profile_tables, read_profile
from app.cv_queue import ensure_cv_queue_tables
from app.profiles import candidate_profile_for, contact_email_for


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit_pseudonym(user_id: str) -> str:
    digest = hashlib.sha256(f"ingress-job-audit:{user_id}".encode("utf-8")).hexdigest()
    return f"anon_{digest[:32]}"


def _collect_cv_keys(conn, user_id: str) -> list[tuple[str, str]]:
    """Return unique (stored_key, original_name) pairs for the user."""
    ensure_cv_queue_tables(conn)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(stored: str, name: str) -> None:
        key = normalize_cv_key(stored)
        if not key or key in seen:
            return
        seen.add(key)
        found.append((key, (name or key).strip() or key))

    row = conn.execute(
        "SELECT cv_file_key FROM candidate_profile WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is not None:
        add(row[0] or "", "profile-cv")

    for stored, name in conn.execute(
        """
        SELECT cv_stored, cv_name FROM applications
        WHERE candidate_subject = ?
        """,
        (user_id,),
    ):
        add(stored or "", name or "")

    for stored, name in conn.execute(
        """
        SELECT cv_file_key, cv_name FROM parse_cv_queue
        WHERE user_id = ?
        """,
        (user_id,),
    ):
        add(stored or "", name or "")

    return found


def build_export_payload(*, user_id: str) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            ensure_consent_tables(conn)
            ensure_profile_tables(conn)
            cv_meta = [
                {"stored": key, "name": name, "zip_path": f"cvs/{key}"}
                for key, name in _collect_cv_keys(conn, user_id)
            ]
            apps = []
            for row in conn.execute(
                """
                SELECT id, job_id, message, phone, email, answers, cv_name, cv_stored,
                       status, decision_reason, created_at
                FROM applications
                WHERE candidate_subject = ?
                ORDER BY id
                """,
                (user_id,),
            ):
                apps.append(
                    {
                        "id": int(row[0]),
                        "job_id": int(row[1]),
                        "message": row[2] or "",
                        "phone": row[3] or "",
                        "email": row[4] or "",
                        "answers": row[5] or "[]",
                        "cv_name": row[6] or "",
                        "has_cv": bool(normalize_cv_key(row[7] or "")),
                        "status": row[8] or "",
                        "decision_reason": row[9] or "",
                        "created_at": row[10] or "",
                    }
                )
            grants = conn.execute(
                """
                SELECT kind, granted, version, ts FROM consent
                WHERE user_id = ?
                ORDER BY kind
                """,
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

    consents = [
        {
            "kind": row[0],
            "granted": bool(row[1]),
            "version": row[2] or "",
            "ts": row[3],
        }
        for row in grants
    ]
    return {
        "exported_at": _now(),
        "user_id": user_id,
        "contact_profile": candidate_profile_for(user_id),
        "contact_email": contact_email_for(user_id),
        "cv_profile": read_profile(user_id=user_id),
        "consents": consents,
        "applications": apps,
        "cv_files": cv_meta,
    }


def build_export_zip(*, user_id: str) -> bytes:
    payload = build_export_payload(user_id=user_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "export.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        for item in payload["cv_files"]:
            data = read_stored_cv(item["stored"])
            if data:
                zf.writestr(item["zip_path"], data)
    return buffer.getvalue()


def _clear_accounts(user_id: str) -> None:
    from app.profiles import _LOCK as accounts_lock, _connect as accounts_connect

    with accounts_lock:
        conn = accounts_connect()
        try:
            conn.execute("DELETE FROM candidate_profiles WHERE subject = ?", (user_id,))
            conn.execute("DELETE FROM contact_emails WHERE subject = ?", (user_id,))
            conn.execute("DELETE FROM academy_identities WHERE subject = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()


def delete_my_data(*, user_id: str) -> dict:
    """Hard-delete candidate personal data; leave audit under a pseudonym."""
    subject = (user_id or "").strip()
    if not subject:
        return {"deleted": False, "pseudonym": ""}

    pseudo = audit_pseudonym(subject)
    cv_keys: list[str] = []

    with _LOCK:
        conn = _connect()
        try:
            ensure_consent_tables(conn)
            ensure_profile_tables(conn)
            cv_keys = [key for key, _ in _collect_cv_keys(conn, subject)]

            before = {}
            row = conn.execute(
                "SELECT data, status FROM candidate_profile WHERE user_id = ?",
                (subject,),
            ).fetchone()
            if row is not None:
                before = {"data": row[0] or "{}", "status": row[1] or ""}

            conn.execute(
                """
                UPDATE profile_edit_log
                SET user_id = ?
                WHERE user_id = ?
                """,
                (pseudo, subject),
            )
            conn.execute(
                """
                INSERT INTO profile_edit_log (
                    user_id, profile_id, action, before_data, after_data,
                    before_status, after_status, ts
                ) VALUES (?, NULL, 'delete_account_data', ?, '{}', ?, '', ?)
                """,
                (
                    pseudo,
                    json.dumps(before, ensure_ascii=False) if before else "{}",
                    before.get("status") or "",
                    _now(),
                ),
            )

            # Live email/matching prefs removed; not kept as audit under real id.
            conn.execute("DELETE FROM consent WHERE user_id = ?", (subject,))
            try:
                conn.execute("DELETE FROM email_prefs WHERE user_id = ?", (subject,))
            except Exception:
                pass
            try:
                conn.execute("DELETE FROM email_log WHERE user_id = ?", (subject,))
            except Exception:
                pass
            try:
                conn.execute("DELETE FROM match_feedback WHERE user_id = ?", (subject,))
            except Exception:
                pass
            conn.execute("DELETE FROM candidate_profile WHERE user_id = ?", (subject,))
            conn.execute("DELETE FROM parse_cv_queue WHERE user_id = ?", (subject,))
            conn.execute(
                """
                UPDATE applications
                SET candidate_subject = ?,
                    message = '',
                    phone = '',
                    email = '',
                    answers = '[]',
                    cv_name = '',
                    cv_stored = ''
                WHERE candidate_subject = ?
                """,
                (pseudo, subject),
            )
            conn.execute(
                "DELETE FROM notifications WHERE recipient_subject = ?",
                (subject,),
            )
            conn.commit()
        finally:
            conn.close()

    _clear_accounts(subject)
    for key in cv_keys:
        delete_stored_cv(key)

    return {"deleted": True, "pseudonym": pseudo}
