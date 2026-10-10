"""Shared LLM/embedding entry point (plan §11 ai_gateway).

All provider calls go through here: feature flag, PII redact, cache, daily
budget, cost log, OpenTelemetry spans. Soft-fails when disabled / over budget /
provider errors so the rest of the pipeline keeps working without AI.

Chat providers (default order): gemini → groq → nvidia → openrouter → openai.
Embed providers (default order): nvidia → openai.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from worker.ai_gateway.redact import mask_pii
from worker.observability import span

log = logging.getLogger("ingress-job.worker.ai_gateway")

PROMPT_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_cache (
    cache_key TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    output TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_usage_daily (
    day TEXT NOT NULL,
    purpose TEXT NOT NULL,
    calls INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (day, purpose)
);
"""

DEFAULT_MODEL = "gpt-4.1-nano"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_NVIDIA_CHAT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
DEFAULT_NVIDIA_EMBED_MODEL = "nvidia/nemotron-3-embed-1b"
# Auto-router across currently available :free models (single-model free tiers rate-limit hard).
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
CACHE_MODEL_TAG = "multi-v1"
# Rough small-model list prices (USD / 1M tokens); used only for budget logs.
_DEFAULT_INPUT_PER_M = 0.10
_DEFAULT_OUTPUT_PER_M = 0.40
_DEFAULT_EMBED_PER_M = 0.02

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass
class GatewayResult:
    ok: bool
    data: dict | None = None
    error: str = ""
    cached: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    prompt_version: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class EmbedResult:
    ok: bool
    vectors: list[list[float]] = field(default_factory=list)
    error: str = ""
    prompt_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _ChatProvider:
    name: str
    key: str
    base_url: str
    model: str
    json_mode: str  # schema | object | prompt
    extra_headers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class _EmbedProvider:
    name: str
    key: str
    base_url: str
    model: str


def enabled(conn: sqlite3.Connection | None = None) -> bool:
    from worker.ai_flags import feature_on

    return feature_on("gateway", conn)


def any_provider_key() -> bool:
    return bool(
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("GROQ_API_KEY", "").strip()
        or os.environ.get("NVIDIA_API_KEY", "").strip()
        or os.environ.get("OPENROUTER_API_KEY", "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
    )


def model_name() -> str:
    providers = _chat_providers()
    if providers:
        return providers[0].model
    return (os.environ.get("AI_GATEWAY_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def embedding_model_name() -> str:
    explicit = (os.environ.get("AI_EMBEDDING_MODEL") or "").strip()
    if explicit:
        return explicit
    if os.environ.get("NVIDIA_API_KEY", "").strip():
        return (
            os.environ.get("NVIDIA_EMBED_MODEL") or DEFAULT_NVIDIA_EMBED_MODEL
        ).strip() or DEFAULT_NVIDIA_EMBED_MODEL
    return DEFAULT_EMBEDDING_MODEL


def daily_call_limit() -> int:
    raw = os.environ.get("AI_GATEWAY_DAILY_CALL_LIMIT", "200").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 200


def ensure_ai_tables(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    conn.executescript(PROMPT_CACHE_SCHEMA)
    from worker.ai_flags import ensure_flag_table

    ensure_flag_table(conn)


def complete_json(
    *,
    purpose: str,
    prompt_version: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str = "result",
    known_pii: dict | None = None,
    conn: sqlite3.Connection | None = None,
    timeout: float = 60.0,
    allow_provider: bool = True,
) -> GatewayResult:
    """Redact → cache → budget → provider JSON call → cost log.

    When allow_provider=False, only a cache hit succeeds; a miss returns
    error ``ai_pending`` so HTTP handlers can respond without blocking on LLMs.
    """
    purpose = (purpose or "unknown")[:80]
    prompt_version = (prompt_version or "v0")[:40]
    result = GatewayResult(ok=False, prompt_version=prompt_version, model=model_name())

    if not enabled(conn):
        result.error = "ai_disabled"
        return result
    if not any_provider_key():
        result.error = "ai_no_key"
        return result

    redacted_user = mask_pii(user, known=known_pii)
    redacted_system = mask_pii(system, known=known_pii)
    cache_key = _cache_key(
        purpose, prompt_version, CACHE_MODEL_TAG, redacted_system, redacted_user
    )

    with span(f"ai_gateway.{purpose}"):
        ensure_ai_tables(conn)
        cached = _cache_get(conn, cache_key)
        if cached is not None:
            result.ok = True
            result.data = cached
            result.cached = True
            result.meta["cache"] = "hit"
            return result

        if not allow_provider:
            result.error = "ai_pending"
            result.meta["cache"] = "miss"
            return result

        if _over_budget(conn, purpose):
            result.error = "ai_budget_exceeded"
            return result

        started = time.monotonic()
        try:
            raw = _call_chat_json(
                system=redacted_system,
                user=redacted_user,
                schema=schema,
                schema_name=schema_name,
                timeout=timeout,
            )
        except Exception as exc:
            result.error = f"ai_provider_error:{type(exc).__name__}"
            log.warning("ai_gateway %s failed: %s", purpose, exc)
            return result

        data = raw.get("data")
        if not isinstance(data, dict):
            result.error = "ai_bad_json"
            return result

        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        cost = _estimate_cost(prompt_tokens, completion_tokens)

        _cache_put(conn, cache_key, purpose, prompt_version, data)
        _usage_add(conn, purpose, prompt_tokens, completion_tokens, cost)
        # Persist even when the caller is a read path that never commits.
        _commit(conn)

        result.ok = True
        result.data = data
        result.model = str(raw.get("model") or result.model)
        result.prompt_tokens = prompt_tokens
        result.completion_tokens = completion_tokens
        result.cost_usd = cost
        result.meta["latency_ms"] = int((time.monotonic() - started) * 1000)
        result.meta["cache"] = "miss"
        result.meta["provider"] = str(raw.get("provider") or "")
        return result


def _commit(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    commit = getattr(conn, "commit", None)
    if callable(commit):
        commit()


def _cache_key(purpose: str, prompt_version: str, model: str, system: str, user: str) -> str:
    blob = "\n".join([purpose, prompt_version, model, system, user]).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _cache_get(conn: sqlite3.Connection | None, cache_key: str) -> dict | None:
    if conn is None:
        return None
    row = conn.execute(
        "SELECT output FROM ai_cache WHERE cache_key = ?",
        (cache_key,),
    ).fetchone()
    if row is None:
        return None
    raw = row[0] if not hasattr(row, "keys") else row["output"]
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _cache_put(
    conn: sqlite3.Connection | None,
    cache_key: str,
    purpose: str,
    prompt_version: str,
    data: dict,
) -> None:
    if conn is None:
        return
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO ai_cache (cache_key, purpose, prompt_version, output, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(cache_key) DO UPDATE SET
            output = excluded.output,
            created_at = excluded.created_at
        """,
        (
            cache_key,
            purpose,
            prompt_version,
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
            now,
        ),
    )


def _over_budget(conn: sqlite3.Connection | None, purpose: str) -> bool:
    limit = daily_call_limit()
    if limit <= 0:
        return True
    if conn is None:
        return False
    day = date.today().isoformat()
    row = conn.execute(
        "SELECT COALESCE(SUM(calls), 0) FROM ai_usage_daily WHERE day = ?",
        (day,),
    ).fetchone()
    total = int(row[0] if row is not None else 0)
    return total >= limit


def _usage_add(
    conn: sqlite3.Connection | None,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float,
) -> None:
    if conn is None:
        return
    day = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO ai_usage_daily (day, purpose, calls, prompt_tokens, completion_tokens, cost_usd)
        VALUES (?, ?, 1, ?, ?, ?)
        ON CONFLICT(day, purpose) DO UPDATE SET
            calls = ai_usage_daily.calls + 1,
            prompt_tokens = ai_usage_daily.prompt_tokens + excluded.prompt_tokens,
            completion_tokens = ai_usage_daily.completion_tokens + excluded.completion_tokens,
            cost_usd = ai_usage_daily.cost_usd + excluded.cost_usd
        """,
        (day, purpose, prompt_tokens, completion_tokens, cost),
    )


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    try:
        inp = float(os.environ.get("AI_GATEWAY_INPUT_USD_PER_M", _DEFAULT_INPUT_PER_M))
        out = float(os.environ.get("AI_GATEWAY_OUTPUT_USD_PER_M", _DEFAULT_OUTPUT_PER_M))
    except ValueError:
        inp, out = _DEFAULT_INPUT_PER_M, _DEFAULT_OUTPUT_PER_M
    return round((prompt_tokens * inp + completion_tokens * out) / 1_000_000.0, 8)


def _estimate_embed_cost(prompt_tokens: int) -> float:
    try:
        rate = float(os.environ.get("AI_EMBEDDING_USD_PER_M", _DEFAULT_EMBED_PER_M))
    except ValueError:
        rate = _DEFAULT_EMBED_PER_M
    return round((prompt_tokens * rate) / 1_000_000.0, 8)


def embed(
    *,
    texts: list[str],
    purpose: str = "embed",
    conn: sqlite3.Connection | None = None,
    timeout: float = 60.0,
) -> EmbedResult:
    """Budget → embedding providers (fallback) → cost log. Soft-fails."""
    purpose = (purpose or "embed")[:80]
    model = embedding_model_name()
    result = EmbedResult(ok=False, model=model)
    cleaned = [str(t or "").strip() for t in texts]
    cleaned = [t for t in cleaned if t]
    if not cleaned:
        result.error = "ai_empty_input"
        return result
    if not enabled(conn):
        result.error = "ai_disabled"
        return result
    if not any_provider_key():
        result.error = "ai_no_key"
        return result

    with span(f"ai_gateway.{purpose}"):
        ensure_ai_tables(conn)
        if _over_budget(conn, purpose):
            result.error = "ai_budget_exceeded"
            return result
        started = time.monotonic()
        try:
            raw = _call_embed(texts=cleaned, timeout=timeout)
        except Exception as exc:
            result.error = f"ai_provider_error:{type(exc).__name__}"
            log.warning("ai_gateway embed %s failed: %s", purpose, exc)
            return result
        vectors = raw.get("vectors") if isinstance(raw.get("vectors"), list) else []
        if len(vectors) != len(cleaned):
            result.error = "ai_bad_embed"
            return result
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
        cost = _estimate_embed_cost(prompt_tokens)
        _usage_add(conn, purpose, prompt_tokens, 0, cost)
        _commit(conn)
        result.ok = True
        result.vectors = vectors
        result.model = str(raw.get("model") or model)
        result.prompt_tokens = prompt_tokens
        result.cost_usd = cost
        result.meta["latency_ms"] = int((time.monotonic() - started) * 1000)
        result.meta["provider"] = str(raw.get("provider") or "")
        return result


def _provider_order(env_name: str, default: str) -> list[str]:
    raw = (os.environ.get(env_name) or default).strip()
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _openai_last(order: list[str]) -> list[str]:
    """Paid OpenAI is always the last resort, whatever AI_CHAT_PROVIDERS says."""
    return [p for p in order if p != "openai"] + (["openai"] if "openai" in order else [])


def _chat_providers() -> list[_ChatProvider]:
    out: list[_ChatProvider] = []
    for name in _openai_last(
        _provider_order("AI_CHAT_PROVIDERS", "gemini,groq,nvidia,openrouter,openai")
    ):
        if name == "gemini":
            key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
            ).strip() or DEFAULT_GEMINI_MODEL
            out.append(
                _ChatProvider(
                    name="gemini",
                    key=key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                    model=model,
                    json_mode="schema",
                )
            )
        elif name == "groq":
            key = os.environ.get("GROQ_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("GROQ_MODEL") or DEFAULT_GROQ_MODEL
            ).strip() or DEFAULT_GROQ_MODEL
            out.append(
                _ChatProvider(
                    name="groq",
                    key=key,
                    base_url="https://api.groq.com/openai/v1",
                    model=model,
                    json_mode="object",
                )
            )
        elif name == "nvidia":
            key = os.environ.get("NVIDIA_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("NVIDIA_CHAT_MODEL") or DEFAULT_NVIDIA_CHAT_MODEL
            ).strip() or DEFAULT_NVIDIA_CHAT_MODEL
            out.append(
                _ChatProvider(
                    name="nvidia",
                    key=key,
                    base_url="https://integrate.api.nvidia.com/v1",
                    model=model,
                    json_mode="prompt",
                )
            )
        elif name == "openrouter":
            key = os.environ.get("OPENROUTER_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
            ).strip() or DEFAULT_OPENROUTER_MODEL
            referer = (
                os.environ.get("OPENROUTER_HTTP_REFERER")
                or os.environ.get("APP_URL")
                or "https://ingress.job"
            ).strip()
            title = (os.environ.get("OPENROUTER_APP_TITLE") or "Ingress Job").strip()
            out.append(
                _ChatProvider(
                    name="openrouter",
                    key=key,
                    base_url="https://openrouter.ai/api/v1",
                    model=model,
                    json_mode="object",
                    extra_headers=(
                        ("HTTP-Referer", referer),
                        ("X-Title", title),
                    ),
                )
            )
        elif name == "openai":
            key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("AI_GATEWAY_MODEL") or DEFAULT_MODEL
            ).strip() or DEFAULT_MODEL
            out.append(
                _ChatProvider(
                    name="openai",
                    key=key,
                    base_url="https://api.openai.com/v1",
                    model=model,
                    json_mode="schema",
                )
            )
    return out


def _embed_providers() -> list[_EmbedProvider]:
    out: list[_EmbedProvider] = []
    for name in _provider_order("AI_EMBED_PROVIDERS", "nvidia,openai"):
        if name == "nvidia":
            key = os.environ.get("NVIDIA_API_KEY", "").strip()
            if not key:
                continue
            model = embedding_model_name()
            if model.startswith("text-embedding"):
                model = (
                    os.environ.get("NVIDIA_EMBED_MODEL") or DEFAULT_NVIDIA_EMBED_MODEL
                ).strip() or DEFAULT_NVIDIA_EMBED_MODEL
            out.append(
                _EmbedProvider(
                    name="nvidia",
                    key=key,
                    base_url="https://integrate.api.nvidia.com/v1",
                    model=model,
                )
            )
        elif name == "openai":
            key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not key:
                continue
            model = (
                os.environ.get("AI_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
            ).strip() or DEFAULT_EMBEDDING_MODEL
            if model.startswith("nvidia/"):
                model = DEFAULT_EMBEDDING_MODEL
            out.append(
                _EmbedProvider(
                    name="openai",
                    key=key,
                    base_url="https://api.openai.com/v1",
                    model=model,
                )
            )
    return out


def _call_chat_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    timeout: float,
) -> dict[str, Any]:
    providers = _chat_providers()
    if not providers:
        raise RuntimeError("no_chat_provider")
    errors: list[str] = []
    failed_names: list[str] = []
    for provider in providers:
        try:
            raw = _chat_json(
                provider=provider,
                system=system,
                user=user,
                schema=schema,
                schema_name=schema_name,
                timeout=timeout,
            )
            raw["provider"] = provider.name
            raw["model"] = provider.model
            if failed_names:
                log.warning(
                    "ai_gateway chat provider ok: %s model=%s (after failed: %s)",
                    provider.name,
                    provider.model,
                    ",".join(failed_names),
                )
            else:
                log.warning(
                    "ai_gateway chat provider ok: %s model=%s",
                    provider.name,
                    provider.model,
                )
            return raw
        except Exception as exc:
            msg = f"{provider.name}:{type(exc).__name__}:{exc}"
            errors.append(msg[:180])
            failed_names.append(provider.name)
            log.warning("ai_gateway chat provider failed: %s", msg)
    raise RuntimeError("; ".join(errors[:4]) or "all_chat_providers_failed")


def _call_embed(*, texts: list[str], timeout: float) -> dict[str, Any]:
    providers = _embed_providers()
    if not providers:
        raise RuntimeError("no_embed_provider")
    errors: list[str] = []
    failed_names: list[str] = []
    for provider in providers:
        try:
            raw = _openai_compat_embed(
                key=provider.key,
                base_url=provider.base_url,
                model=provider.model,
                texts=texts,
                timeout=timeout,
            )
            raw["provider"] = provider.name
            raw["model"] = provider.model
            if failed_names:
                log.warning(
                    "ai_gateway embed provider ok: %s model=%s (after failed: %s)",
                    provider.name,
                    provider.model,
                    ",".join(failed_names),
                )
            else:
                log.warning(
                    "ai_gateway embed provider ok: %s model=%s",
                    provider.name,
                    provider.model,
                )
            return raw
        except Exception as exc:
            msg = f"{provider.name}:{type(exc).__name__}:{exc}"
            errors.append(msg[:180])
            failed_names.append(provider.name)
            log.warning("ai_gateway embed provider failed: %s", msg)
    raise RuntimeError("; ".join(errors[:4]) or "all_embed_providers_failed")


def _chat_json(
    *,
    provider: _ChatProvider,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    timeout: float,
) -> dict[str, Any]:
    schema_hint = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    system_with_schema = (
        system
        + "\n\nReturn ONLY a valid JSON object (no markdown) matching this schema:\n"
        + schema_hint
    )
    body: dict[str, Any] = {
        "model": provider.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_with_schema},
            {"role": "user", "content": user},
        ],
    }
    if provider.json_mode == "schema":
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name[:64] or "result",
                "strict": True,
                "schema": schema,
            },
        }
    elif provider.json_mode == "object":
        body["response_format"] = {"type": "json_object"}
    if provider.name == "nvidia":
        body["chat_template_kwargs"] = {"enable_thinking": False}

    url = provider.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": "Bearer " + provider.key,
        "Content-Type": "application/json",
    }
    for hk, hv in provider.extra_headers:
        headers[hk] = hv

    payload = _http_json(url, body=body, headers=headers, timeout=timeout)
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("empty_choices")
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                parts.append(part)
        content = "".join(parts)
    data = _loads_json_object(str(content))
    return {"data": data, "usage": payload.get("usage") or {}}


def _openai_compat_embed(
    *,
    key: str,
    base_url: str,
    model: str,
    texts: list[str],
    timeout: float,
) -> dict[str, Any]:
    body = {"model": model, "input": texts}
    url = base_url.rstrip("/") + "/embeddings"
    payload = _http_json(
        url,
        body=body,
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    data = payload.get("data") or []
    if not isinstance(data, list) or not data:
        raise RuntimeError("empty_embeddings")
    ordered = sorted(data, key=lambda row: int((row or {}).get("index") or 0))
    vectors: list[list[float]] = []
    for row in ordered:
        emb = (row or {}).get("embedding")
        if not isinstance(emb, list) or not emb:
            raise RuntimeError("bad_embedding_row")
        vectors.append([float(x) for x in emb])
    return {"vectors": vectors, "usage": payload.get("usage") or {}}


def _http_json(
    url: str,
    *,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _loads_json_object(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        raise RuntimeError("empty_content")
    candidates = [text]
    m = _FENCE_RE.search(text)
    if m:
        candidates.insert(0, m.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    last_err: Exception | None = None
    for cand in candidates:
        try:
            data = json.loads(cand)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            continue
        if isinstance(data, dict):
            return data
        last_err = RuntimeError("non_object_json")
    raise RuntimeError(f"bad_json:{type(last_err).__name__ if last_err else 'unknown'}")


def _openai_json(
    *,
    key: str,
    model: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    timeout: float,
) -> dict[str, Any]:
    provider = _ChatProvider(
        name="openai",
        key=key,
        base_url="https://api.openai.com/v1",
        model=model,
        json_mode="schema",
    )
    return _chat_json(
        provider=provider,
        system=system,
        user=user,
        schema=schema,
        schema_name=schema_name,
        timeout=timeout,
    )


def _openai_embed(
    *,
    key: str,
    model: str,
    texts: list[str],
    timeout: float,
) -> dict[str, Any]:
    return _openai_compat_embed(
        key=key,
        base_url="https://api.openai.com/v1",
        model=model,
        texts=texts,
        timeout=timeout,
    )
