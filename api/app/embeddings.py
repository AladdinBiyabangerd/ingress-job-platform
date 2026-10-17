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
# OpenAI text-embedding-3-small=1536; NVIDIA nemotron-3-embed-1b=2048.
DEFAULT_DIMS = 1536
_VECTOR_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_pgvector_ready: bool | None = None


def embedding_model() -> str:
    """Same key the gateway writes under (single active embedding provider)."""
    from app.ai_gateway.gateway import embedding_model_name

    return embedding_model_name()


def embedding_dims() -> int:
    raw = (os.environ.get("AI_EMBEDDING_DIMS") or "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    model = embedding_model().lower()
    if "nv-embed-v1" in model:
        return 4096
    if "nemotron-3-embed" in model or "nvidia/" in model:
        return 2048
    return DEFAULT_DIMS


def content_hash(model: str, text: str) -> str:
    if model.startswith("nvidia/"):
        blob = f"{model}\n{_NVIDIA_HASH_TAG}\n{text}".encode("utf-8")
    else:
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
    remote: bool | None = None,
    relocation: bool | None = None,
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
    flags: list[str] = []
    if remote:
        flags.append("Remote")
    if relocation:
        flags.append("Relocation")
    if flags:
        parts.append("Work: " + ", ".join(flags))
    snippet = re.sub(r"\s+", " ", (text or "").strip())[:800]
    if snippet:
        parts.append(snippet)
    return "\n".join(parts)


def profile_embed_text(profile: dict | None) -> str:
    """PII-free profile text for embeddings. Soft skills omitted (matching noise)."""
    data = profile if isinstance(profile, dict) else {}
    parts: list[str] = []
    headline = str(data.get("headline") or "").strip()
    if headline:
        parts.append(headline)
    summary = re.sub(r"\s+", " ", str(data.get("summary") or "").strip())[:600]
    if summary:
        parts.append(summary)
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
    # ≤2–3 recent roles × 120-char work summary (not soft-skill noise).
    work = data.get("work_history") if isinstance(data.get("work_history"), list) else []
    for item in work[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        w_sum = re.sub(r"\s+", " ", str(item.get("summary") or "").strip())[:120]
        if title and w_sum:
            parts.append(f"{title}: {w_sum}")
        elif title:
            w_skills = item.get("skills") if isinstance(item.get("skills"), list) else []
            w_names = [str(s).strip() for s in w_skills if str(s).strip()][:8]
            bit = f"{title}: {', '.join(w_names)}" if w_names else title
            parts.append(bit)
        elif w_sum:
            parts.append(w_sum)
    langs = data.get("languages") if isinstance(data.get("languages"), list) else []
    lang_bits: list[str] = []
    for item in langs[:8]:
        if isinstance(item, dict):
            code = str(item.get("code") or "").strip()
            level = str(item.get("level") or "").strip()
            if code:
                lang_bits.append(f"{code}:{level}" if level else code)
        elif isinstance(item, str) and item.strip():
            lang_bits.append(item.strip())
    if lang_bits:
        parts.append("Languages: " + ", ".join(lang_bits))
    prefs = data.get("preferences") if isinstance(data.get("preferences"), dict) else {}
    pref_bits: list[str] = []
    if prefs.get("remote") is True:
        pref_bits.append("remote")
    elif prefs.get("remote") is False:
        pref_bits.append("on-site")
    if prefs.get("relocation") is True:
        pref_bits.append("open to relocation")
    elif prefs.get("relocation") is False:
        pref_bits.append("no relocation")
    if pref_bits:
        parts.append("Preferences: " + ", ".join(pref_bits))
    return "\n".join(parts)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _is_postgres() -> bool:
    try:
        from app.jobs_db import postgres_enabled

        return bool(postgres_enabled())
    except Exception:
        return False


def _mark_pgvector_unavailable() -> None:
    global _pgvector_ready
    _pgvector_ready = False


# Bumped when the provider request changes while the text stays the same, so
# stale vectors are re-embedded. input_type-v1: NVIDIA query/passage modes.
_NVIDIA_HASH_TAG = "input_type-v1"
INPUT_QUERY = "query"
INPUT_PASSAGE = "passage"
_COLUMN_DIMS_RE = re.compile(r"\((\d+)\)")
_column_dims_cache: int | None = None


def column_dims(conn) -> int | None:
    """Declared size of embeddings.embedding (e.g. vector(2048) -> 2048)."""
    global _column_dims_cache
    if _column_dims_cache:
        return _column_dims_cache
    if conn is None or not _is_postgres():
        return None
    try:
        row = conn.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            WHERE a.attrelid = to_regclass('embeddings')
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        ).fetchone()
    except Exception as exc:
        log.warning("embeddings column size lookup failed: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    if row is None:
        return None
    match = _COLUMN_DIMS_RE.search(str(row[0] or ""))
    if not match:
        return None
    _column_dims_cache = int(match.group(1))
    return _column_dims_cache


def dims_match(conn, vector: list[float], *, entity: str = "") -> bool:
    """False (with a warning) when the vector does not fit the column size."""
    expected = column_dims(conn) or embedding_dims()
    if len(vector) == expected:
        return True
    log.warning(
        "embedding skipped for %s: %s dims from model %s, column expects %s "
        "(set AI_EMBEDDING_DIMS to the model size and recreate the embeddings table once)",
        entity or "?",
        len(vector),
        embedding_model(),
        expected,
    )
    return False


def ensure_embedding_tables(conn) -> bool:
    """Create pgvector extension + embeddings table. False on SQLite / failure.

    The HNSW index is created by the worker (``worker.embeddings.ensure_vector_index``)
    so an index build never blocks an API request.
    """
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
                embedding vector({embedding_dims()}) NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entity_type, entity_id, model)
            )
            """
        )
        conn.commit()
    except Exception as exc:
        log.warning("pgvector embeddings unavailable: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        _pgvector_ready = False
        return False
    _pgvector_ready = True
    return True


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
    try:
        row = conn.execute(
            """
            SELECT embedding::text, content_hash
            FROM embeddings
            WHERE entity_type = ? AND entity_id = ? AND model = ?
            """,
            (entity_type, str(entity_id), chosen),
        ).fetchone()
    except Exception as exc:
        log.warning("get_embedding failed: %s", exc)
        _mark_pgvector_unavailable()
        try:
            conn.rollback()
        except Exception:
            pass
        # One retry after ensure — covers stale ready cache / missing table.
        if not ensure_embedding_tables(conn):
            return None
        try:
            row = conn.execute(
                """
                SELECT embedding::text, content_hash
                FROM embeddings
                WHERE entity_type = ? AND entity_id = ? AND model = ?
                """,
                (entity_type, str(entity_id), chosen),
            ).fetchone()
        except Exception as retry_exc:
            log.warning("get_embedding retry failed: %s", retry_exc)
            _mark_pgvector_unavailable()
            try:
                conn.rollback()
            except Exception:
                pass
            return None
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
        try:
            rows = conn.execute(
                f"""
                SELECT entity_id, embedding::text
                FROM embeddings
                WHERE entity_type = ? AND model = ? AND entity_id IN ({placeholders})
                """,
                (entity_type, chosen, *part),
            ).fetchall()
        except Exception as exc:
            log.warning("load_embeddings failed: %s", exc)
            _mark_pgvector_unavailable()
            try:
                conn.rollback()
            except Exception:
                pass
            if not ensure_embedding_tables(conn):
                return out
            try:
                rows = conn.execute(
                    f"""
                    SELECT entity_id, embedding::text
                    FROM embeddings
                    WHERE entity_type = ? AND model = ? AND entity_id IN ({placeholders})
                    """,
                    (entity_type, chosen, *part),
                ).fetchall()
            except Exception as retry_exc:
                log.warning("load_embeddings retry failed: %s", retry_exc)
                _mark_pgvector_unavailable()
                try:
                    conn.rollback()
                except Exception:
                    pass
                return out
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
    if not dims_match(conn, vector, entity=f"{entity_type}/{entity_id}"):
        return False
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

    input_type = INPUT_QUERY if entity_type == ENTITY_PROFILE else INPUT_PASSAGE
    result = embed(
        texts=[text_s],
        purpose=f"embed_{entity_type}",
        conn=conn,
        input_type=input_type,
    )
    if not result.ok or not result.vectors:
        log.info("embed skip %s/%s: %s", entity_type, entity_id, result.error)
        return False
    if result.model and result.model != model:
        log.warning(
            "embed skip %s/%s: provider model %s != stored model key %s",
            entity_type,
            entity_id,
            result.model,
            model,
        )
        return False
    ok = upsert_embedding(
        conn,
        entity_type=entity_type,
        entity_id=str(entity_id),
        text=text_s,
        vector=result.vectors[0],
        model=model,
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
