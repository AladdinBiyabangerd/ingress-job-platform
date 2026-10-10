"""Format messy scraped ads for the job-detail UI.

Two paths (same output shape):
1. Sync via ``ai_gateway.complete_json`` — any chat provider, immediate.
2. OpenAI Batch API — half price, up to 24h (fallback / backlog).

Nothing runs when job_tidy is off, no provider key exists, the ad is already
structured, or a batch for it is still open. A cut-off batch reply is not saved.
AI may restructure and clean formatting only — never invent facts, salary, or links.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import urllib.request
from typing import Any

log = logging.getLogger("ingress-job.worker.tidy")

MODEL = "gpt-4.1-nano"
PER_RUN = 20
SYNC_PER_RUN = 12
INPUT_CHARS = 14000
OPEN = ("validating", "in_progress", "finalizing", "cancelling")
PURPOSE = "job_tidy"
PROMPT_VERSION = "job-tidy-v2"

_AZ = re.compile(r"[əğıöüşçƏĞİÖÜŞÇ]")
_CYR = re.compile(r"[а-яёА-ЯЁ]")

_HEADINGS = {
    "en": {
        "why": "Why this role is interesting",
        "about": "About the role",
        "do": "What you'll do",
        "need": "Requirements",
        "nice": "Nice to have",
        "offer": "Benefits",
    },
    "az": {
        "why": "Niyə bu rol maraqlıdır",
        "about": "Rol haqqında",
        "do": "Vəzifələr",
        "need": "Tələblər",
        "nice": "Üstünlük",
        "offer": "İmkanlar",
    },
    "ru": {
        "why": "Почему эта роль интересна",
        "about": "О роли",
        "do": "Обязанности",
        "need": "Требования",
        "nice": "Будет плюсом",
        "offer": "Что мы предлагаем",
    },
}

_SYSTEM = (
    "You reformat job ads for a clean detail page.\n"
    "Rules:\n"
    "- Keep the same language as the ad.\n"
    "- Do NOT invent facts, requirements, salary, benefits, links, or tech.\n"
    "- Do NOT drop real duties, requirements, or offers that appear in the ad.\n"
    "- Drop apply spam, tracking phrases, and duplicated boilerplate.\n"
    "- Split dense paragraphs into short bullet items when the source lists duties "
    "or requirements in prose or semicolon chains.\n"
    "- Put content into the schema fields that fit; use extra_sections only for "
    "leftover titled blocks that do not fit.\n"
    "- Leave a field empty when the ad has no matching content.\n"
    "- Reply with JSON only."
)

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "why_interesting",
        "about",
        "what_youll_do",
        "requirements",
        "nice_to_have",
        "benefits",
        "extra_sections",
    ],
    "properties": {
        "why_interesting": {"type": "array", "items": {"type": "string"}},
        "about": {"type": "string"},
        "what_youll_do": {"type": "array", "items": {"type": "string"}},
        "requirements": {"type": "array", "items": {"type": "string"}},
        "nice_to_have": {"type": "array", "items": {"type": "string"}},
        "benefits": {"type": "array", "items": {"type": "string"}},
        "extra_sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "items", "paragraphs"],
                "properties": {
                    "title": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                    "paragraphs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def _lang(text: str) -> str:
    sample = (text or "")[:1200]
    if _AZ.search(sample):
        return "az"
    if _CYR.search(sample):
        return "ru"
    return "en"


def messy(text: str) -> bool:
    """True when the ad needs structure work for the detail UI."""
    body = (text or "").strip()
    if len(body) < 280:
        return False
    bulletish = (
        body.count("\u2022")
        + body.count("\n- ")
        + body.count("\n* ")
        + body.count("\n• ")
        + len(re.findall(r"(?m)^\d{1,2}[.)]\s+\S", body))
    )
    if bulletish >= 4:
        return False
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if sum(1 for line in lines if line.endswith(";")) >= 4:
        return False
    colon_heads = sum(1 for line in lines if 2 <= len(line) <= 48 and line.endswith(":"))
    if colon_heads >= 2 and bulletish >= 2:
        return False
    if colon_heads >= 3:
        return False
    # One long blob / few breaks → wall of text.
    if len(body) >= 500 and body.count("\n") < 5:
        return True
    # Long enough with almost no section cues.
    if len(body) >= 400 and colon_heads < 2 and bulletish < 2:
        return True
    return False


def _clean_items(values: Any, *, limit: int = 24) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for raw in values:
        item = " ".join(str(raw or "").split()).strip(" -\u2022\t")
        if len(item) < 2:
            continue
        out.append(item[:500])
        if len(out) >= limit:
            break
    return out


def _section_block(title: str, items: list[str] | None = None, paragraphs: list[str] | None = None) -> str:
    parts: list[str] = []
    if items:
        parts.append(f"{title}:")
        parts.extend(f"\u2022 {item}" for item in items)
    elif paragraphs:
        parts.append(f"{title}:")
        parts.extend(paragraphs)
    return "\n".join(parts)


def format_structured(data: dict[str, Any], *, lang: str = "en") -> str:
    """Turn structured tidy JSON into plain text the detail parser understands."""
    heads = _HEADINGS.get(lang) or _HEADINGS["en"]
    blocks: list[str] = []

    why = _clean_items(data.get("why_interesting"), limit=8)
    if why:
        blocks.append(_section_block(heads["why"], why))

    about = " ".join(str(data.get("about") or "").split()).strip()
    if about:
        blocks.append(_section_block(heads["about"], paragraphs=[about[:1200]]))

    do = _clean_items(data.get("what_youll_do"))
    if do:
        blocks.append(_section_block(heads["do"], do))

    need = _clean_items(data.get("requirements"))
    if need:
        blocks.append(_section_block(heads["need"], need))

    nice = _clean_items(data.get("nice_to_have"), limit=16)
    if nice:
        blocks.append(_section_block(heads["nice"], nice))

    offer = _clean_items(data.get("benefits"), limit=16)
    if offer:
        blocks.append(_section_block(heads["offer"], offer))

    extras = data.get("extra_sections")
    if isinstance(extras, list):
        for extra in extras[:8]:
            if not isinstance(extra, dict):
                continue
            title = " ".join(str(extra.get("title") or "").split()).strip(" :")
            if not title or len(title) > 70:
                continue
            items = _clean_items(extra.get("items"))
            paras = _clean_items(extra.get("paragraphs"), limit=6)
            block = _section_block(title, items=items or None, paragraphs=paras or None)
            if block:
                blocks.append(block)

    return "\n\n".join(blocks).strip()


def _untouched(original: str, cleaned: str) -> bool:
    """Reject empty / tiny rewrites that lost the ad."""
    if not cleaned or len(cleaned) < 80:
        return True
    if len(cleaned) < min(200, len(original) // 4):
        return True
    return False


def _tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tidy_batches (
            id INTEGER PRIMARY KEY,
            openai_id TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS tidy_batch_jobs (
            job_id INTEGER NOT NULL,
            batch_id INTEGER NOT NULL,
            PRIMARY KEY (job_id, batch_id)
        );
        """
    )


def _pending_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, text FROM jobs
        WHERE status = 'published'
          AND (cleaned_text IS NULL OR cleaned_text = '')
          AND id NOT IN (
              SELECT j.job_id FROM tidy_batch_jobs j
              JOIN tidy_batches b ON b.id = j.batch_id
              WHERE b.status IN ('validating', 'in_progress', 'finalizing', 'cancelling')
          )
        ORDER BY id DESC
        """
    ).fetchall()


def _sync_tidy(conn: sqlite3.Connection, limit: int = SYNC_PER_RUN) -> int:
    """Immediate structured tidy through the multi-provider gateway."""
    from worker.ai_flags import feature_on
    from worker.ai_gateway import any_provider_key, complete_json

    if not feature_on("gateway", conn) or not any_provider_key():
        return 0

    targets = [row for row in _pending_rows(conn) if messy(row["text"])][:limit]
    saved = 0
    for row in targets:
        snippet = (row["text"] or "")[:INPUT_CHARS]
        lang = _lang(snippet)
        heads = _HEADINGS[lang]
        user = (
            f"Language hint: {lang}\n"
            f"Prefer these section titles when filling fields: "
            f"{heads['why']}; {heads['about']}; {heads['do']}; "
            f"{heads['need']}; {heads['nice']}; {heads['offer']}.\n\n"
            f"Job ad:\n{snippet}"
        )
        result = complete_json(
            purpose=PURPOSE,
            prompt_version=PROMPT_VERSION,
            system=_SYSTEM,
            user=user,
            schema=_JSON_SCHEMA,
            schema_name="job_tidy",
            conn=conn,
            timeout=90.0,
        )
        if not result.ok or not isinstance(result.data, dict):
            log.info("job_tidy sync miss id=%s: %s", row["id"], result.error or "failed")
            continue
        cleaned = format_structured(result.data, lang=lang)
        if _untouched(snippet, cleaned):
            log.info("job_tidy sync rejected id=%s: thin output", row["id"])
            continue
        conn.execute("UPDATE jobs SET cleaned_text = ? WHERE id = ?", (cleaned, row["id"]))
        saved += 1
    if saved:
        conn.commit()
    return saved


def _api(key: str, method: str, path: str, body: bytes | None = None, content_type: str | None = None) -> dict | bytes:
    headers = {"Authorization": "Bearer " + key}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(
        "https://api.openai.com" + path,
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        raw = res.read()
    if content_type == "application/json" or path.endswith("/content") is False and raw[:1] in (b"{", b"["):
        return json.loads(raw)
    return raw


def _upload(jsonl: bytes, key: str) -> str:
    boundary = "ingressjobtidy"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="purpose"\r\n\r\n'
        "batch\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="tidy.jsonl"\r\n'
        "Content-Type: application/jsonl\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    raw = _api(
        key,
        "POST",
        "/v1/files",
        head + jsonl + tail,
        "multipart/form-data; boundary=" + boundary,
    )
    return raw["id"]


def _line(job_id: int, text: str) -> dict:
    snippet = text[:INPUT_CHARS]
    lang = _lang(snippet)
    heads = _HEADINGS[lang]
    cap = min(4500, max(700, len(snippet) // 2))
    prompt = (
        "Reformat the whole job ad for a structured detail page. Do not stop early. "
        "Same language. No new facts, salary, or links. Drop spam. "
        "Use these headings exactly (each on its own line, ending with ':'): "
        f"{heads['why']}: / {heads['about']}: / {heads['do']}: / "
        f"{heads['need']}: / {heads['nice']}: / {heads['offer']}:. "
        "Omit a heading when the ad has no matching content. "
        "Under list headings, each item starts with '\u2022 '. "
        "Keep meaning; only fix structure and readability."
    )
    return {
        "custom_id": f"job-{job_id}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": MODEL,
            "temperature": 0,
            "max_tokens": cap,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": snippet},
            ],
        },
    }


def _collect(conn: sqlite3.Connection, key: str) -> int:
    saved = 0
    rows = conn.execute(
        "SELECT id, openai_id FROM tidy_batches WHERE status IN ('validating', 'in_progress', 'finalizing', 'cancelling', '')"
    ).fetchall()
    for row in rows:
        try:
            batch = _api(key, "GET", "/v1/batches/" + row["openai_id"])
        except Exception:
            continue
        status = batch.get("status") or "failed"
        conn.execute("UPDATE tidy_batches SET status = ? WHERE id = ?", (status, row["id"]))
        conn.commit()
        if status != "completed" or not batch.get("output_file_id"):
            continue
        try:
            payload = _api(key, "GET", "/v1/files/" + batch["output_file_id"] + "/content")
        except Exception:
            continue
        text = payload.decode() if isinstance(payload, bytes) else json.dumps(payload)
        for line in text.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            custom = str(item.get("custom_id") or "")
            if not custom.startswith("job-"):
                continue
            job_id = int(custom.split("-", 1)[1])
            choice = ((item.get("response") or {}).get("body") or {}).get("choices") or []
            if not choice or choice[0].get("finish_reason") == "length":
                continue
            cleaned = ((choice[0].get("message") or {}).get("content") or "").strip()
            if not cleaned:
                continue
            conn.execute("UPDATE jobs SET cleaned_text = ? WHERE id = ?", (cleaned, job_id))
            saved += 1
        conn.commit()
    return saved


def _submit(conn: sqlite3.Connection, key: str, limit: int) -> int:
    targets = [row for row in _pending_rows(conn) if messy(row["text"])][:limit]
    if not targets:
        return 0
    jsonl = "\n".join(json.dumps(_line(row["id"], row["text"]), ensure_ascii=False) for row in targets).encode()
    file_id = _upload(jsonl, key)
    batch = _api(
        key,
        "POST",
        "/v1/batches",
        json.dumps({
            "input_file_id": file_id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        }).encode(),
        "application/json",
    )
    cur = conn.execute(
        "INSERT INTO tidy_batches (openai_id, status) VALUES (?, ?)",
        (batch["id"], batch.get("status") or "validating"),
    )
    batch_row = int(cur.lastrowid)
    conn.executemany(
        "INSERT INTO tidy_batch_jobs (job_id, batch_id) VALUES (?, ?)",
        [(row["id"], batch_row) for row in targets],
    )
    conn.commit()
    return len(targets)


def tidy_pending(conn: sqlite3.Connection, limit: int = PER_RUN) -> tuple[int, int]:
    """Returns (saved, queued). saved includes sync + completed batch results."""
    _tables(conn)
    from worker.ai_flags import feature_on

    if not feature_on("job_tidy", conn):
        return (0, 0)

    saved = 0
    try:
        saved += _sync_tidy(conn, limit=min(SYNC_PER_RUN, limit))
    except Exception:
        log.exception("job_tidy sync failed")

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return (saved, 0)
    saved += _collect(conn, key)
    try:
        queued = _submit(conn, key, limit)
    except Exception:
        queued = 0
    return (saved, queued)
