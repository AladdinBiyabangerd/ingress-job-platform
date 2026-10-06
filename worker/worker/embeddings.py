"""Job embedding backfill (plan §6.2 / §13.3 embed_new_jobs).

Postgres + pgvector only. Soft-fails on SQLite / missing extension / AI off.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("ingress-job.worker.embeddings")

ENTITY_JOB = "job"
ENTITY_PROFILE = "profile"
DEFAULT_DIMS = 1536
_VECTOR_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_pgvector_ready: bool | None = None


def embedding_model() -> str:
    return (os.environ.get("AI_EMBEDDING_MODEL") or "text-embedding-3-small").strip() or "text-embedding-3-small"


def content_hash(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8g}" for v in values) + "]"


def job_embed_text(
    *,
    title: str = "",
    category: str = "",
    skills: list[str] | None = None,
    text: str = "",
) -> str:
    parts: list[str] = []
    title_s = (title or "").strip()
    if title_s:
        parts.append(title_s)
    cat = (category or "").strip()
    if cat:
        parts.append(f"Category: {cat}")
    names = [str(s).strip() for s in (skills or []) if str(s).strip()]
    if names:
        parts.append("Skills: " + ", ".join(names[:40]))
    snippet = re.sub(r"\s+", " ", (text or "").strip())[:500]
    if snippet:
        parts.append(snippet)
    return "\n".join(parts)


def profile_embed_text(profile: dict | None) -> str:
    data = profile if isinstance(profile, dict) else {}
    parts: list[str] = []
    headline = str(data.get("headline") or "").strip()
    if headline:
        parts.append(headline)
    seniority = str(data.get("seniority") or "").strip()
    if seniority:
        parts.append(f"Seniority: {seniority}")
    years = data.get("total_years")
    if isinstance(years, (int, float)):
        parts.append(f"Years: {years}")
    skill_names: list[str] = []
    raw_skills = data.get("skills") if isinstance(data.get("skills"), list) else []
    for item in raw_skills:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("canonical_name") or "").strip()
        else:
            continue
        if name and name not in skill_names:
            skill_names.append(name)
        if len(skill_names) >= 40:
            break
    if skill_names:
        parts.append("Skills: " + ", ".join(skill_names))
    work = data.get("work_history") if isinstance(data.get("work_history"), list) else []
    for item in work[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        w_skills = item.get("skills") if isinstance(item.get("skills"), list) else []
        w_names = [str(s).strip() for s in w_skills if str(s).strip()][:12]
        bit = title
        if w_names:
            bit = f"{title}: {', '.join(w_names)}" if title else ", ".join(w_names)
        if bit:
            parts.append(bit)
    return "\n".join(parts)


def embed_profile(conn, *, user_id: str, profile: dict) -> bool:
    """Embed a candidate profile (PII-free text). Soft-fails."""
    subject = (user_id or "").strip()
    if not subject or not ensure_embedding_tables(conn):
        return False
    text = profile_embed_text(profile)
    if not text.strip():
        return False
    from worker.ai_flags import feature_on

    if not feature_on("embeddings", conn):
        return False
    model = embedding_model()
    from worker.ai_gateway import embed

    result = embed(texts=[text], purpose="embed_profile", conn=conn)
    if not result.ok or not result.vectors:
        return False
    chosen = result.model or model
    lit = vector_literal(result.vectors[0])
    ch = content_hash(chosen, text)
    conn.execute(
        """
        INSERT INTO embeddings (
            entity_type, entity_id, model, content_hash, dims, embedding, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?::vector, ?)
        ON CONFLICT(entity_type, entity_id, model) DO UPDATE SET
            content_hash = excluded.content_hash,
            dims = excluded.dims,
            embedding = excluded.embedding,
            updated_at = excluded.updated_at
        """,
        (ENTITY_PROFILE, subject, chosen, ch, len(result.vectors[0]), lit, _now()),
    )
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_postgres() -> bool:
    try:
        from worker.jobs_db import postgres_enabled

        return bool(postgres_enabled())
    except Exception:
        url = (os.environ.get("DATABASE_URL") or "").strip().lower()
        return url.startswith(("postgresql://", "postgres://", "postgresql+", "postgres+"))


def ensure_embedding_tables(conn) -> bool:
    global _pgvector_ready
    if conn is None or not _is_postgres():
        _pgvector_ready = False
        return False
    if _pgvector_ready is True:
        return True
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS embeddings (
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                model TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                dims INTEGER NOT NULL,
                embedding vector({DEFAULT_DIMS}) NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entity_type, entity_id, model)
            )
            """
        )
        try:
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS embeddings_hnsw
                ON embeddings USING hnsw (embedding vector_cosine_ops)
                """
            )
        except Exception as idx_exc:
            log.info("embeddings HNSW index skipped: %s", idx_exc)
        conn.commit()
        _pgvector_ready = True
        return True
    except Exception as exc:
        log.warning("pgvector embeddings unavailable: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        _pgvector_ready = False
        return False


def _skill_names_for_job(conn, job_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT d.canonical_name
        FROM job_skill js
        JOIN skill_dictionary d ON d.id = js.skill_id
        WHERE js.job_id = ?
        ORDER BY d.canonical_name
        """,
        (int(job_id),),
    ).fetchall()
    names: list[str] = []
    for row in rows:
        name = str(row[0] if not hasattr(row, "keys") else row["canonical_name"] or "").strip()
        if name:
            names.append(name)
    if names:
        return names
    # Fallback: tech_stack JSON on the job row.
    row = conn.execute("SELECT tech_stack FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
    if row is None:
        return []
    raw = row[0] if not hasattr(row, "keys") else row["tech_stack"]
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()][:40]


def _stored_hash(conn, *, entity_id: str, model: str) -> str | None:
    row = conn.execute(
        """
        SELECT content_hash FROM embeddings
        WHERE entity_type = ? AND entity_id = ? AND model = ?
        """,
        (ENTITY_JOB, entity_id, model),
    ).fetchone()
    if row is None:
        return None
    return str(row[0] if not hasattr(row, "keys") else row["content_hash"] or "")


def upsert_job_embedding(
    conn,
    *,
    job_id: int,
    text: str,
    vector: list[float],
    model: str | None = None,
) -> bool:
    if not ensure_embedding_tables(conn):
        return False
    chosen = model or embedding_model()
    ch = content_hash(chosen, text)
    lit = vector_literal(vector)
    conn.execute(
        """
        INSERT INTO embeddings (
            entity_type, entity_id, model, content_hash, dims, embedding, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?::vector, ?)
        ON CONFLICT(entity_type, entity_id, model) DO UPDATE SET
            content_hash = excluded.content_hash,
            dims = excluded.dims,
            embedding = excluded.embedding,
            updated_at = excluded.updated_at
        """,
        (ENTITY_JOB, str(job_id), chosen, ch, len(vector), lit, _now()),
    )
    return True


def embed_job(conn, job_id: int) -> bool:
    """Embed one published job if missing/stale. Soft-fails."""
    if not ensure_embedding_tables(conn):
        return False
    row = conn.execute(
        """
        SELECT id, title, category, text, status, COALESCE(hidden, 0) AS hidden, merged_into
        FROM jobs WHERE id = ?
        """,
        (int(job_id),),
    ).fetchone()
    if row is None:
        return False
    status = str(row["status"] if hasattr(row, "keys") else row[4] or "")
    hidden = int(row["hidden"] if hasattr(row, "keys") else row[5] or 0)
    merged = row["merged_into"] if hasattr(row, "keys") else row[6]
    if status != "published" or hidden or merged:
        return False
    title = str(row["title"] if hasattr(row, "keys") else row[1] or "")
    category = str(row["category"] if hasattr(row, "keys") else row[2] or "")
    text = str(row["text"] if hasattr(row, "keys") else row[3] or "")
    skills = _skill_names_for_job(conn, int(job_id))
    embed_text = job_embed_text(title=title, category=category, skills=skills, text=text)
    if not embed_text.strip():
        return False
    model = embedding_model()
    ch = content_hash(model, embed_text)
    if _stored_hash(conn, entity_id=str(job_id), model=model) == ch:
        return True

    from worker.ai_flags import feature_on
    from worker.ai_gateway import embed

    if not feature_on("embeddings", conn):
        return False

    result = embed(texts=[embed_text], purpose="embed_job", conn=conn)
    if not result.ok or not result.vectors:
        return False
    ok = upsert_job_embedding(
        conn,
        job_id=int(job_id),
        text=embed_text,
        vector=result.vectors[0],
        model=result.model or model,
    )
    if ok:
        try:
            conn.commit()
        except Exception:
            pass
    return ok


def embed_stale_jobs(conn, *, limit: int = 40) -> dict[str, Any]:
    """Hourly batch: embed published jobs missing or with stale content_hash."""
    stats = {"attempted": 0, "embedded": 0, "skipped": 0, "ready": False}
    if not ensure_embedding_tables(conn):
        return stats
    stats["ready"] = True
    model = embedding_model()
    # Candidates: published, not hidden, not merged. Prefer newest first.
    rows = conn.execute(
        """
        SELECT id, title, category, text, tech_stack
        FROM jobs
        WHERE status = 'published'
          AND COALESCE(hidden, 0) = 0
          AND (merged_into IS NULL OR merged_into = 0)
        ORDER BY id DESC
        LIMIT ?
        """,
        (max(1, min(int(limit) * 5, 500)),),
    ).fetchall()

    from worker.ai_gateway import embed, enabled
    from worker.ai_flags import feature_on

    if not feature_on("embeddings", conn) or not enabled(conn):
        return stats

    batch_texts: list[str] = []
    batch_ids: list[int] = []
    for row in rows:
        if len(batch_ids) >= limit:
            break
        job_id = int(row["id"] if hasattr(row, "keys") else row[0])
        title = str(row["title"] if hasattr(row, "keys") else row[1] or "")
        category = str(row["category"] if hasattr(row, "keys") else row[2] or "")
        text = str(row["text"] if hasattr(row, "keys") else row[3] or "")
        skills = _skill_names_for_job(conn, job_id)
        embed_text = job_embed_text(title=title, category=category, skills=skills, text=text)
        if not embed_text.strip():
            stats["skipped"] += 1
            continue
        ch = content_hash(model, embed_text)
        if _stored_hash(conn, entity_id=str(job_id), model=model) == ch:
            stats["skipped"] += 1
            continue
        batch_ids.append(job_id)
        batch_texts.append(embed_text)

    stats["attempted"] = len(batch_ids)
    if not batch_ids:
        return stats

    # Small chunks to stay under provider limits.
    chunk = 16
    for i in range(0, len(batch_ids), chunk):
        ids = batch_ids[i : i + chunk]
        texts = batch_texts[i : i + chunk]
        result = embed(texts=texts, purpose="embed_job", conn=conn)
        if not result.ok or len(result.vectors) != len(texts):
            log.info("embed_stale_jobs batch failed: %s", result.error)
            break
        for job_id, text, vector in zip(ids, texts, result.vectors):
            if upsert_job_embedding(
                conn,
                job_id=job_id,
                text=text,
                vector=vector,
                model=result.model or model,
            ):
                stats["embedded"] += 1
        try:
            conn.commit()
        except Exception:
            pass
    return stats
