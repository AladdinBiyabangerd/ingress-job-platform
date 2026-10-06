"""pgvector embeddings store + text builders (plan §6.2 AI #2).

Postgres + pgvector only. SQLite / missing extension → no-op; matching stays
structured-only.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("ingress-job.api.embeddings")

ENTITY_JOB = "job"
ENTITY_PROFILE = "profile"
DEFAULT_DIMS = 1536
_VECTOR_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_pgvector_ready: bool | None = None


def embedding_model() -> str:
    return (os.environ.get("AI_EMBEDDING_MODEL") or "text-embedding-3-small").strip() or "text-embedding-3-small"


def content_hash(model: str, text: str) -> str:
    blob = f"{model}\n{text}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (math.sqrt(na) * math.sqrt(nb))))


def parse_vector(raw: Any) -> list[float] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        try:
            return [float(x) for x in raw]
        except (TypeError, ValueError):
            return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return [float(m.group(0)) for m in _VECTOR_RE.finditer(text)]
    except (TypeError, ValueError):
        return None


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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_postgres() -> bool:
    try:
        from app.jobs_db import postgres_enabled

        return bool(postgres_enabled())
    except Exception:
        return False


def ensure_embedding_tables(conn) -> bool:
    """Create pgvector extension + embeddings table. False on SQLite / failure."""
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
            # Index is optional for MVP (top-N cosine is computed in Python).
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


def pgvector_available(conn) -> bool:
    global _pgvector_ready
    if _pgvector_ready is True:
        return True
    return ensure_embedding_tables(conn)


def get_embedding(
    conn,
    *,
    entity_type: str,
    entity_id: str,
    model: str | None = None,
) -> tuple[list[float], str] | None:
    """Return (vector, content_hash) or None."""
    if not pgvector_available(conn):
        return None
    chosen = model or embedding_model()
    row = conn.execute(
        """
        SELECT embedding::text, content_hash
        FROM embeddings
        WHERE entity_type = ? AND entity_id = ? AND model = ?
        """,
        (entity_type, str(entity_id), chosen),
    ).fetchone()
    if row is None:
        return None
    vec = parse_vector(row[0] if not hasattr(row, "keys") else row["embedding"])
    if not vec:
        return None
    ch = str(row[1] if not hasattr(row, "keys") else row["content_hash"] or "")
    return vec, ch


def load_embeddings(
    conn,
    *,
    entity_type: str,
    entity_ids: list[str],
    model: str | None = None,
) -> dict[str, list[float]]:
    if not entity_ids or not pgvector_available(conn):
        return {}
    chosen = model or embedding_model()
    out: dict[str, list[float]] = {}
    # Chunk IN lists for safety.
    chunk = 100
    for i in range(0, len(entity_ids), chunk):
        part = [str(x) for x in entity_ids[i : i + chunk]]
        placeholders = ",".join("?" for _ in part)
        rows = conn.execute(
            f"""
            SELECT entity_id, embedding::text
            FROM embeddings
            WHERE entity_type = ? AND model = ? AND entity_id IN ({placeholders})
            """,
            (entity_type, chosen, *part),
        ).fetchall()
        for row in rows:
            eid = str(row[0] if not hasattr(row, "keys") else row["entity_id"])
            vec = parse_vector(row[1] if not hasattr(row, "keys") else row["embedding"])
            if vec:
                out[eid] = vec
    return out


def upsert_embedding(
    conn,
    *,
    entity_type: str,
    entity_id: str,
    text: str,
    vector: list[float],
    model: str | None = None,
) -> bool:
    if not pgvector_available(conn):
        return False
    if not text.strip() or not vector:
        return False
    chosen = model or embedding_model()
    dims = len(vector)
    if dims != DEFAULT_DIMS:
        log.warning("embedding dims %s != %s for %s/%s", dims, DEFAULT_DIMS, entity_type, entity_id)
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
        (entity_type, str(entity_id), chosen, ch, dims, lit, _now()),
    )
    return True


def delete_entity_embeddings(conn, *, entity_type: str, entity_id: str) -> None:
    if conn is None or not _is_postgres():
        return
    try:
        if not ensure_embedding_tables(conn):
            return
        conn.execute(
            "DELETE FROM embeddings WHERE entity_type = ? AND entity_id = ?",
            (entity_type, str(entity_id)),
        )
    except Exception as exc:
        log.warning("delete embeddings failed: %s", exc)


def embed_and_store(
    conn,
    *,
    entity_type: str,
    entity_id: str,
    text: str,
) -> bool:
    """Call gateway.embed and upsert. Soft-fails."""
    text_s = (text or "").strip()
    if not text_s:
        return False
    from app.ai_flags import feature_on

    if not feature_on("embeddings", conn):
        return False
    if not pgvector_available(conn):
        return False
    model = embedding_model()
    ch = content_hash(model, text_s)
    existing = get_embedding(conn, entity_type=entity_type, entity_id=str(entity_id), model=model)
    if existing is not None and existing[1] == ch:
        return True

    from app.ai_gateway import embed

    result = embed(texts=[text_s], purpose=f"embed_{entity_type}", conn=conn)
    if not result.ok or not result.vectors:
        log.info("embed skip %s/%s: %s", entity_type, entity_id, result.error)
        return False
    ok = upsert_embedding(
        conn,
        entity_type=entity_type,
        entity_id=str(entity_id),
        text=text_s,
        vector=result.vectors[0],
        model=result.model or model,
    )
    if ok:
        try:
            conn.commit()
        except Exception:
            pass
    return ok


def embed_profile_for_user(*, user_id: str) -> bool:
    """Load profile, build PII-free text, embed. Soft-fails."""
    subject = (user_id or "").strip()
    if not subject or not _is_postgres():
        return False
    from app.cabinet_store import _LOCK, _connect
    from app.cv_profile import _profile_payload, ensure_profile_tables

    with _LOCK:
        conn = _connect()
        try:
            ensure_profile_tables(conn)
            if not ensure_embedding_tables(conn):
                return False
            payload = _profile_payload(conn, user_id=subject)
            profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
            text = profile_embed_text(profile)
            return embed_and_store(
                conn,
                entity_type=ENTITY_PROFILE,
                entity_id=subject,
                text=text,
            )
        except Exception as exc:
            log.warning("profile embed failed for %s: %s", subject, exc)
            return False
        finally:
            conn.close()
