"""On-site applications and CV files.

Without bucket credentials, files stay under api/data/cvs. When BUCKET_NAME,
BUCKET_ACCESS_KEY, and BUCKET_SECRET_KEY are all set, new files go to that
S3-compatible bucket (same variables as ingress-academy). Existing local files
remain readable.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.apply_form import parse_stored
from app.cabinet_store import CabinetError, _LOCK, _connect, _now
from app.cv_queue import enqueue_parse
from app.object_storage import bucket_config, delete_object, get_object, put_object

CV_ROOT = Path(__file__).resolve().parents[1] / "data" / "cvs"
MAX_CV_BYTES = 5 * 1024 * 1024
MAX_MESSAGE = 2000
MAX_ANSWER = 2000
MAX_REASON = 400
_MESSAGE = "Qısa müraciət yazılmalıdır"
_CV = "CV faylı PDF, DOC və ya DOCX olmalıdır və 5 MB-dan böyük ola bilməz"
_DUPLICATE = "Bu elana artıq müraciət etmisiniz"
_FIELDS = "Yalnız seçilmiş sahələr doldurulmalıdır"
_REQUIRED = "Məcburi sahələr doldurulmalıdır"
_PHONE = "Telefon nömrəsi düzgün deyil"
_PHONE_MISSING = "Telefon nömrəsi yazılmalıdır"
_EMAIL = "E-poçt düzgün deyil"
_EMAIL_MISSING = "E-poçt yazılmalıdır"
_ANSWER = "Cavab çox uzundur"
_STATUS = "Status yalnız baxıldı və ya rədd edildi ola bilər"
_REASON = "Rədd səbəbi çox uzundur"
_FORBIDDEN = "Müraciətin statusunu dəyişmək olmaz"
_WITHDRAW = "Müraciəti geri götürmək olmaz"
_STATUSES = {"submitted", "seen", "rejected"}
_STORED = re.compile(r"^[a-f0-9]{32}\.(?:pdf|doc|docx)$")
_EXTS = {".pdf", ".doc", ".docx"}
_CV_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_PHONE_RE = re.compile(r"^[0-9+\-() ]{5,40}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(max_length=32)
    reason: str = Field(default="", max_length=2000)


def _answers(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        answer = item.get("answer")
        if isinstance(question, str) and isinstance(answer, str):
            items.append({"question": question, "answer": answer})
    return items


def _status_events(conn: sqlite3.Connection, app_ids: list[int]) -> dict[int, list[dict]]:
    if not app_ids:
        return {}
    placeholders = ",".join("?" for _ in app_ids)
    rows = conn.execute(
        f"""
        SELECT application_id, kind, reason, created_at
        FROM notifications
        WHERE application_id IN ({placeholders})
          AND kind IN ('application_seen', 'application_rejected')
        ORDER BY id ASC
        """,
        app_ids,
    ).fetchall()
    by_id: dict[int, list[dict]] = {app_id: [] for app_id in app_ids}
    for row in rows:
        app_id = int(row["application_id"])
        kind = row["kind"] or ""
        status = "seen" if kind == "application_seen" else "rejected"
        step = {"status": status, "at": row["created_at"] or ""}
        note = " ".join((row["reason"] or "").split())
        if note:
            step["note"] = note
        by_id.setdefault(app_id, []).append(step)
    return by_id


def _timeline(row: sqlite3.Row, events: list[dict] | None = None) -> list[dict]:
    status = (row["status"] or "submitted").strip().lower()
    if status not in _STATUSES:
        status = "submitted"
    steps: list[dict] = [{"status": "submitted", "at": row["created_at"] or ""}]
    history = list(events or [])
    if history:
        steps.extend(history)
    elif status in {"seen", "rejected"}:
        step: dict = {"status": status, "at": ""}
        if status == "rejected":
            reason = " ".join((row["decision_reason"] or "").split())
            if reason:
                step["note"] = reason
        steps.append(step)
    if status == "rejected":
        reason = " ".join((row["decision_reason"] or "").split())
        if reason:
            for step in reversed(steps):
                if step["status"] == "rejected":
                    step["note"] = reason
                    break
            else:
                steps.append({"status": "rejected", "at": "", "note": reason})
    elif status == "seen" and steps[-1]["status"] != "seen":
        # Current status may have cleared a prior rejection; keep history, mark seen.
        if not any(step["status"] == "seen" for step in steps):
            steps.append({"status": "seen", "at": ""})
    return steps


def _view(row: sqlite3.Row, *, reviewer: bool, events: list[dict] | None = None) -> dict:
    status = (row["status"] or "submitted").strip().lower()
    if status not in _STATUSES:
        status = "submitted"
    payload = {
        "id": int(row["id"]),
        "job_id": int(row["job_id"]),
        "job_title": row["job_title"] or "",
        "status": status,
        "message": row["message"] or "",
        "phone": row["phone"] or "",
        "email": row["email"] or "",
        "answers": _answers(row["answers"] or "[]"),
        "has_cv": bool(row["cv_stored"] or ""),
        "cv_name": row["cv_name"] or "",
        "created_at": row["created_at"] or "",
        "timeline": _timeline(row, events),
    }
    reason = " ".join((row["decision_reason"] or "").split())
    if status == "rejected" and reason:
        payload["reason"] = reason
    if reviewer:
        payload["candidate_subject"] = row["candidate_subject"] or ""
    return payload


_SELECT = """
SELECT
    a.id,
    a.job_id,
    a.candidate_subject,
    a.message,
    a.phone,
    a.email,
    a.answers,
    a.cv_name,
    a.cv_stored,
    a.status,
    a.decision_reason,
    a.created_at,
    j.title AS job_title,
    COALESCE(j.language, '') AS job_language,
    COALESCE(j.owner_subject, '') AS owner_subject
FROM applications a
JOIN jobs j ON j.id = a.job_id
"""


def _onsite_job(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT id, COALESCE(apply_form, '') AS apply_form
        FROM jobs
        WHERE id = ?
          AND status = 'published'
          AND COALESCE(owner_subject, '') != ''
          AND COALESCE(hidden, 0) = 0
          AND (merged_into IS NULL OR merged_into = 0)
        """,
        (job_id,),
    ).fetchone()


def _message(value: str, *, enabled: bool, required: bool) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not enabled:
        if text:
            raise CabinetError(422, _FIELDS)
        return ""
    if (required and not text) or len(text) > MAX_MESSAGE:
        raise CabinetError(422, _MESSAGE)
    return text


def _phone(value: str, *, enabled: bool, required: bool) -> str:
    text = " ".join((value or "").split())
    if not enabled:
        if text:
            raise CabinetError(422, _FIELDS)
        return ""
    if not text:
        if required:
            raise CabinetError(422, _PHONE_MISSING)
        return ""
    digits = sum(char.isdigit() for char in text)
    if digits < 5 or not _PHONE_RE.fullmatch(text):
        raise CabinetError(422, _PHONE)
    return text


def _email(value: str, *, enabled: bool, required: bool) -> str:
    text = (value or "").strip().lower()
    if not enabled:
        if text:
            raise CabinetError(422, _FIELDS)
        return ""
    if not text:
        if required:
            raise CabinetError(422, _EMAIL_MISSING)
        return ""
    if len(text) > 120 or not _EMAIL_RE.fullmatch(text):
        raise CabinetError(422, _EMAIL)
    return text


def _question_answers(form: dict, raw: list) -> str:
    if not isinstance(raw, list) or len(raw) > 5:
        raise CabinetError(422, _FIELDS)
    by_id: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict) or any(key not in {"id", "answer"} for key in item):
            raise CabinetError(422, _FIELDS)
        qid = item.get("id")
        answer = item.get("answer")
        if not isinstance(qid, str) or not isinstance(answer, str) or qid in by_id:
            raise CabinetError(422, _FIELDS)
        by_id[qid] = answer.replace("\r\n", "\n").replace("\r", "\n").strip()
    known = {question["id"] for question in form["questions"]}
    if any(qid not in known for qid in by_id):
        raise CabinetError(422, _FIELDS)
    stored = []
    for question in form["questions"]:
        answer = by_id.get(question["id"], "")
        if len(answer) > MAX_ANSWER:
            raise CabinetError(422, _ANSWER)
        if question["required"] and not answer:
            raise CabinetError(422, _REQUIRED)
        stored.append({"question": question["text"], "answer": answer})
    return json.dumps(stored, ensure_ascii=False, separators=(",", ":"))


def _cv_parts(filename: str, data: bytes) -> tuple[str, str, bytes]:
    ext = Path(filename or "").suffix.lower()
    if ext not in _EXTS or not data or len(data) > MAX_CV_BYTES:
        raise CabinetError(422, _CV)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[:80] or f"cv{ext}"
    if not safe.lower().endswith(ext):
        safe = f"cv{ext}"
    return safe, ext, data


def _object_key(stored: str) -> str:
    return f"cvs/{stored}"


def normalize_cv_key(value: str) -> str:
    """Strip optional cvs/ prefix; return stored filename or empty when invalid."""
    key = (value or "").strip()
    if key.startswith("cvs/"):
        key = key[4:]
    return key if _STORED.fullmatch(key) else ""


def _delete_stored(stored: str) -> None:
    key = normalize_cv_key(stored)
    if not key:
        return
    if bucket_config() is not None:
        try:
            delete_object(_object_key(key))
        except Exception:
            pass
    root = CV_ROOT.resolve()
    path = (root / key).resolve()
    if path.parent == root:
        path.unlink(missing_ok=True)


def read_stored_cv(stored: str) -> bytes | None:
    """Return CV bytes for a stored filename, or None when missing/invalid."""
    key = normalize_cv_key(stored)
    if not key:
        return None
    data = None
    if bucket_config() is not None:
        try:
            data = get_object(_object_key(key))
        except Exception:
            data = None
    if data is not None:
        return data if isinstance(data, bytes) else None
    root = CV_ROOT.resolve()
    path = (root / key).resolve()
    if path.parent == root and path.is_file():
        return path.read_bytes()
    return None


def delete_stored_cv(stored: str) -> None:
    _delete_stored(stored)


def _write_cv(ext: str, data: bytes) -> str:
    stored = f"{uuid.uuid4().hex}{ext}"
    if bucket_config() is not None:
        try:
            put_object(_object_key(stored), data, _CV_TYPES.get(ext, "application/octet-stream"))
        except Exception as exc:
            raise CabinetError(503, "CV saxlanmadı") from exc
        return stored
    root = CV_ROOT
    root.mkdir(parents=True, exist_ok=True)
    (root / stored).write_bytes(data)
    return stored


def store_uploaded_cv(filename: str, data: bytes) -> tuple[str, str]:
    """Validate and persist a CV upload. Returns (original_name, stored_key)."""
    original, ext, payload = _cv_parts(filename, data)
    return original, _write_cv(ext, payload)


def _checked(form: dict, fields: dict, cv: tuple[str, bytes] | None) -> tuple[str, str, str, str, str, bytes]:
    message = _message(fields.get("message") or "", enabled=form["message"]["enabled"], required=form["message"]["required"])
    phone = _phone(fields.get("phone") or "", enabled=form["phone"]["enabled"], required=form["phone"]["required"])
    email = _email(fields.get("email") or "", enabled=form["email"]["enabled"], required=form["email"]["required"])
    answers = _question_answers(form, fields.get("answers") or [])
    original = ""
    ext = ""
    data = b""
    if not form["cv"]["enabled"]:
        if cv is not None:
            raise CabinetError(422, _FIELDS)
    elif cv is None:
        if form["cv"]["required"]:
            raise CabinetError(422, _CV)
    else:
        original, ext, data = _cv_parts(cv[0], cv[1])
    return message, phone, email, answers, original, ext, data


def create_application(subject: str, job_id: int, fields: dict, cv: tuple[str, bytes] | None) -> dict:
    stored_name = ""
    note = None
    with _LOCK:
        conn = _connect()
        try:
            job = _onsite_job(conn, job_id)
            if job is None:
                raise CabinetError(404, "Elan tapılmadı")
            taken = conn.execute(
                """
                SELECT 1 FROM applications
                WHERE job_id = ? AND candidate_subject = ?
                """,
                (job_id, subject),
            ).fetchone()
            if taken is not None:
                raise CabinetError(409, _DUPLICATE)
            message, phone, email, answers, original, ext, data = _checked(
                parse_stored(job["apply_form"]),
                fields,
                cv,
            )
            if data:
                stored_name = _write_cv(ext, data)
            note = None
            try:
                cur = conn.execute(
                    """
                    INSERT INTO applications (
                        job_id, candidate_subject, message, cv_name, cv_stored, created_at,
                        status, decision_reason, phone, email, answers
                    ) VALUES (?, ?, ?, ?, ?, ?, 'submitted', '', ?, ?, ?)
                    """,
                    (job_id, subject, message, original, stored_name, _now(), phone, email, answers),
                )
                app_id = int(cur.lastrowid)
                if stored_name:
                    enqueue_parse(
                        conn,
                        user_id=subject,
                        cv_file_key=stored_name,
                        cv_name=original,
                        application_id=app_id,
                    )
                meta = conn.execute(
                    "SELECT title, language, owner_subject FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
                if meta is not None:
                    from app.notifications import insert_notification

                    note = insert_notification(
                        conn,
                        recipient=meta["owner_subject"] or "",
                        kind="application_new",
                        job_id=job_id,
                        job_title=meta["title"] or "",
                        application_id=app_id,
                        status="submitted",
                        reason="",
                        language=meta["language"] or "",
                    )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                if stored_name:
                    _delete_stored(stored_name)
                    stored_name = ""
                raise CabinetError(409, _DUPLICATE) from exc
            row = conn.execute(f"{_SELECT} WHERE a.id = ?", (app_id,)).fetchone()
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note)
    if row is None:
        if stored_name:
            _delete_stored(stored_name)
        raise CabinetError(404, "Elan tapılmadı")
    return _view(row, reviewer=False)


def _rows(where: str, params: tuple, *, reviewer: bool) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            f"{_SELECT} WHERE {where} ORDER BY a.id DESC",
            params,
        ).fetchall()
        events = _status_events(conn, [int(row["id"]) for row in rows])
    finally:
        conn.close()
    return [_view(row, reviewer=reviewer, events=events.get(int(row["id"]), [])) for row in rows]


def list_for_candidate(subject: str) -> list[dict]:
    return _rows("a.candidate_subject = ?", (subject,), reviewer=False)


def list_for_owner(subject: str) -> list[dict]:
    return _rows("j.owner_subject = ? AND j.owner_subject != ''", (subject,), reviewer=True)


def list_all() -> list[dict]:
    return _rows("1 = 1", (), reviewer=True)


def _one(conn: sqlite3.Connection, application_id: int) -> sqlite3.Row | None:
    return conn.execute(f"{_SELECT} WHERE a.id = ?", (application_id,)).fetchone()


def set_status(application_id: int, *, subject: str, staff: bool, status: str, reason: str) -> dict:
    cleaned_status = (status or "").strip().lower()
    if cleaned_status not in {"seen", "rejected"}:
        raise CabinetError(422, _STATUS)
    cleaned_reason = " ".join((reason or "").split())
    if cleaned_status == "seen":
        cleaned_reason = ""
    elif len(cleaned_reason) > MAX_REASON:
        raise CabinetError(422, _REASON)
    note = None
    fallback_email = ""
    events: list[dict] = []
    with _LOCK:
        conn = _connect()
        try:
            row = _one(conn, application_id)
            if row is None:
                raise CabinetError(404, "Müraciət tapılmadı")
            owner = row["owner_subject"] or ""
            if not staff and not (owner and owner == subject):
                raise CabinetError(403, _FORBIDDEN)
            previous = (row["status"] or "submitted").strip().lower()
            conn.execute(
                """
                UPDATE applications
                SET status = ?, decision_reason = ?
                WHERE id = ?
                """,
                (cleaned_status, cleaned_reason, application_id),
            )
            if previous != cleaned_status:
                from app.notifications import insert_notification

                note = insert_notification(
                    conn,
                    recipient=row["candidate_subject"] or "",
                    kind="application_seen" if cleaned_status == "seen" else "application_rejected",
                    job_id=int(row["job_id"]),
                    job_title=row["job_title"] or "",
                    application_id=application_id,
                    status=cleaned_status,
                    reason=cleaned_reason,
                    language=row["job_language"] or "",
                )
                fallback_email = row["email"] or ""
            conn.commit()
            saved = _one(conn, application_id)
            events = _status_events(conn, [application_id]).get(application_id, [])
        finally:
            conn.close()
    if note:
        from app.notifications import deliver_email

        deliver_email(note, fallback_email=fallback_email)
    return _view(saved, reviewer=True, events=events)


def withdraw(application_id: int, subject: str) -> None:
    stored = ""
    with _LOCK:
        conn = _connect()
        try:
            row = _one(conn, application_id)
            if row is None:
                raise CabinetError(404, "Müraciət tapılmadı")
            if (row["candidate_subject"] or "") != subject:
                raise CabinetError(403, _WITHDRAW)
            stored = row["cv_stored"] or ""
            conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
            conn.commit()
        finally:
            conn.close()
    _delete_stored(stored)


def application_cv(application_id: int, *, subject: str, staff: bool) -> tuple[bytes, str]:
    conn = _connect()
    try:
        row = _one(conn, application_id)
    finally:
        conn.close()
    if row is None:
        raise CabinetError(404, "Müraciət tapılmadı")
    owner = row["owner_subject"] or ""
    allowed = staff or row["candidate_subject"] == subject or (owner and owner == subject)
    if not allowed:
        raise CabinetError(403, "CV-ni oxumaq olmaz")
    stored = row["cv_stored"] or ""
    if not _STORED.fullmatch(stored):
        raise CabinetError(404, "CV tapılmadı")
    data = None
    if bucket_config() is not None:
        try:
            data = get_object(_object_key(stored))
        except Exception as exc:
            raise CabinetError(503, "CV tapılmadı") from exc
    if data is None:
        root = CV_ROOT.resolve()
        path = (root / stored).resolve()
        if path.parent == root and path.is_file():
            data = path.read_bytes()
    if not data:
        raise CabinetError(404, "CV tapılmadı")
    return data, row["cv_name"] or stored
