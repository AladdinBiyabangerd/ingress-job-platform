"""Queue messy ads on the OpenAI Batch API after a collection pass.

Half the live price. Results can take up to 24 hours.
Nothing is sent when OPENAI_API_KEY is missing, the ad is already tidy,
or a batch for it is still open. A cut-off reply is not saved.
"""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.request

MODEL = "gpt-4.1-nano"
PER_RUN = 20
INPUT_CHARS = 14000
OPEN = ("validating", "in_progress", "finalizing", "cancelling")


def messy(text: str) -> bool:
    if len(text) < 400:
        return False
    if text.count("\u2022") >= 3 or text.count("\n- ") >= 3:
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if sum(1 for line in lines if line.endswith(";")) >= 4:
        return False
    headings = sum(1 for line in lines if len(line) < 48 and line.endswith(":"))
    return headings < 2


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
    cap = min(4000, max(500, len(snippet) // 3))
    prompt = (
        'Rewrite the whole ad, from start to end. Do not stop early. '
        'Same language. No new facts, salary, or links. Drop spam. '
        'Headings end with ":". Items start with "\u2022 ".'
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
    rows = conn.execute(
        """
        SELECT id, text FROM jobs
        WHERE status = 'published'
          AND (cleaned_text IS NULL OR cleaned_text = '')
          AND id NOT IN (
              SELECT j.job_id FROM tidy_batch_jobs j
              JOIN tidy_batches b ON b.id = j.batch_id
              WHERE b.status IN ('validating', 'in_progress', 'finalizing', 'cancelling')
          )
        """
    ).fetchall()
    targets = [row for row in rows if messy(row["text"])][:limit]
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
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    _tables(conn)
    if not key:
        return (0, 0)
    saved = _collect(conn, key)
    try:
        queued = _submit(conn, key, limit)
    except Exception:
        queued = 0
    return (saved, queued)
