"""Shared LLM/embedding entry point (plan §11 ai_gateway).

All provider calls go through here: feature flag, PII redact, cache, daily
budget, cost log, OpenTelemetry spans. Soft-fails when disabled / over budget /
provider errors so the rest of the pipeline keeps working without AI.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
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
# Rough small-model list prices (USD / 1M tokens); used only for budget logs.
_DEFAULT_INPUT_PER_M = 0.10
_DEFAULT_OUTPUT_PER_M = 0.40


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


def enabled() -> bool:
    raw = os.environ.get("AI_GATEWAY_ENABLED", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in {"1", "true", "yes", "on"}:
        return True
    # Default: on when a provider key exists.
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def model_name() -> str:
    return (os.environ.get("AI_GATEWAY_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


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
) -> GatewayResult:
    """Redact → cache → budget → provider JSON call → cost log."""
    purpose = (purpose or "unknown")[:80]
    prompt_version = (prompt_version or "v0")[:40]
    result = GatewayResult(ok=False, prompt_version=prompt_version, model=model_name())

    if not enabled():
        result.error = "ai_disabled"
        return result
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        result.error = "ai_no_key"
        return result

    redacted_user = mask_pii(user, known=known_pii)
    redacted_system = mask_pii(system, known=known_pii)
    cache_key = _cache_key(purpose, prompt_version, model_name(), redacted_system, redacted_user)

    with span(f"ai_gateway.{purpose}"):
        ensure_ai_tables(conn)
        cached = _cache_get(conn, cache_key)
        if cached is not None:
            result.ok = True
            result.data = cached
            result.cached = True
            result.meta["cache"] = "hit"
            return result

        if _over_budget(conn, purpose):
            result.error = "ai_budget_exceeded"
            return result

        started = time.monotonic()
        try:
            raw = _openai_json(
                key=key,
                model=model_name(),
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

        result.ok = True
        result.data = data
        result.prompt_tokens = prompt_tokens
        result.completion_tokens = completion_tokens
        result.cost_usd = cost
        result.meta["latency_ms"] = int((time.monotonic() - started) * 1000)
        result.meta["cache"] = "miss"
        return result


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
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name[:64] or "result",
                "strict": True,
                "schema": schema,
            },
        },
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("empty_choices")
    content = (((choices[0] or {}).get("message") or {}).get("content")) or ""
    data = json.loads(content)
    if not isinstance(data, dict):
        raise RuntimeError("non_object_json")
    return {"data": data, "usage": payload.get("usage") or {}}
