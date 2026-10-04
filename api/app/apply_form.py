"""Application form chosen on an ad. Old answers are not stored here."""

from __future__ import annotations

import json
import re
import uuid

from pydantic import BaseModel, ConfigDict, Field

_QID = re.compile(r"^q[a-f0-9]{8}$")
_KEYS = ("message", "cv", "phone", "email")
_FORM = "Müraciət forması düzgün deyil"
_QUESTION = "Sual yazılmalıdır"
_LIMIT = "Ən çox 5 sual ola bilər"
_EMPTY = "Müraciət formasında ən azı bir sahə seçilməlidir"
MAX_QUESTIONS = 5
MAX_QUESTION = 200


class FormError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def default_form() -> dict:
    return {
        "message": {"enabled": True, "required": True},
        "cv": {"enabled": True, "required": False},
        "phone": {"enabled": False, "required": False},
        "email": {"enabled": False, "required": False},
        "questions": [],
    }


def normalize_form(data: dict) -> dict:
    if not isinstance(data, dict) or any(key not in {* _KEYS, "questions"} for key in data):
        raise FormError(_FORM)
    out: dict = {}
    chosen = 0
    for key in _KEYS:
        spec = data.get(key, {})
        if not isinstance(spec, dict) or any(name not in {"enabled", "required"} for name in spec):
            raise FormError(_FORM)
        enabled = bool(spec.get("enabled"))
        out[key] = {"enabled": enabled, "required": bool(spec.get("required")) and enabled}
        if enabled:
            chosen += 1
    raw = data.get("questions", [])
    if not isinstance(raw, list):
        raise FormError(_FORM)
    if len(raw) > MAX_QUESTIONS:
        raise FormError(_LIMIT)
    questions = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or any(name not in {"id", "text", "required"} for name in item):
            raise FormError(_FORM)
        text = " ".join(str(item.get("text") or "").split())
        if not text:
            raise FormError(_QUESTION)
        if len(text) > MAX_QUESTION:
            raise FormError(_FORM)
        qid = item.get("id") or ""
        if not isinstance(qid, str) or not _QID.fullmatch(qid) or qid in seen:
            qid = f"q{uuid.uuid4().hex[:8]}"
            while qid in seen:
                qid = f"q{uuid.uuid4().hex[:8]}"
        seen.add(qid)
        questions.append({"id": qid, "text": text, "required": bool(item.get("required"))})
        chosen += 1
    if chosen == 0:
        raise FormError(_EMPTY)
    out["questions"] = questions
    return out


def parse_stored(raw: str | None) -> dict:
    if not raw or not str(raw).strip():
        return default_form()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return default_form()
    try:
        return normalize_form(data)
    except FormError:
        return default_form()


def dump_form(form: dict) -> str:
    return json.dumps(form, ensure_ascii=False, separators=(",", ":"))


def coerce_form(payload: dict | None, *, missing: str) -> dict | None:
    if payload is None:
        return default_form() if missing == "default" else None
    return normalize_form(payload)


class FieldIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    required: bool = False


class QuestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="", max_length=16)
    text: str = Field(default="", max_length=200)
    required: bool = False


class FormIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: FieldIn = Field(default_factory=FieldIn)
    cv: FieldIn = Field(default_factory=FieldIn)
    phone: FieldIn = Field(default_factory=FieldIn)
    email: FieldIn = Field(default_factory=FieldIn)
    questions: list[QuestionIn] = Field(default_factory=list)
