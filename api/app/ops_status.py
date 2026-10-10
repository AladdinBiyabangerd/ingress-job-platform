"""Live AI + crawl funnel status for staff / Academy ops pages.

Derived at runtime from env keys, feature flags, budget, crawl_sources, and
crawl_runs — not a hardcoded “everything is fine” list.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.ai_flags import FEATURE_ENV, FEATURES, _env_state, feature_on, key_configured, stored_flags

_CRAWL_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    found_count INTEGER NOT NULL DEFAULT 0,
    created_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
"""

# Human labels for AI flows (same product language as Job admin UI).
_FEATURE_LABELS = {
    "gateway": "Ümumi AI gateway (LLM və embed)",
    "cv_fallback": "CV parse ehtiyatı",
    "job_tidy": "Elan mətnini təmizləmə",
    "market_fit": "Crawl bazar uyğunluğu",
    "embeddings": "Vakansiya və profil embed-ləri",
    "rerank": "Uyğunluq rerank",
    "llm_rerank": "LLM uyğunluq re-rank",
    "match_why": "Uyğunluq «niyə» cümləsi",
    "role_coach": "Rol bacarıq koçu",
    "learning_roadmap": "Öyrənmə roadmap",
    "job_analyze": "Elan «Analiz et» hesabatı",
    "job_apply_draft": "Elan «Müraciət mətni» qaralama",
    "digest_intro": "Digest giriş mətni",
    "engagement_copy": "Engagement bildiriş mətni",
}

_PROVIDER_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}

_PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "groq": "Groq",
    "nvidia": "NVIDIA",
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
}


def _cell(row: Any, key: str, index: int):
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            pass
    return row[index]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _since_iso(days: int) -> str:
    days = max(1, min(90, int(days)))
    return (_utc_now() - timedelta(days=days)).isoformat(timespec="seconds")


def _feature_detail(feature: str, conn: sqlite3.Connection | None, *, budget_hit: bool) -> dict:
    label = _FEATURE_LABELS.get(feature, feature)
    env = _env_state(feature)
    stored = stored_flags(conn)
    on = feature_on(feature, conn)

    if env is False:
        env_name = FEATURE_ENV.get(feature) or ""
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": f"Server ayarı ({env_name}) bu axını söndürüb.",
        }
    if feature in stored and not stored[feature]:
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Staff panelindən söndürülüb.",
        }
    if not key_configured() and feature in {
        "gateway",
        "job_tidy",
        "engagement_copy",
        "market_fit",
    }:
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Heç bir AI açarı qoyulmayıb (Gemini / Groq / NVIDIA / OpenRouter / OpenAI).",
        }
    if not on and feature not in {
        "gateway",
        "job_tidy",
        "engagement_copy",
        "market_fit",
    }:
        if not feature_on("gateway", conn):
            return {
                "id": feature,
                "label": label,
                "status": "stopped",
                "reason": "Ümumi AI gateway sönülüdür; bu axın da işləmir.",
            }
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Axın hazırda sönülüdür.",
        }
    if not on:
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Axın hazırda sönülüdür.",
        }
    if budget_hit and feature != "gateway":
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Gündəlik AI çağırış limiti dolub; yeni model çağırışları dayandırılıb.",
        }
    if budget_hit and feature == "gateway":
        return {
            "id": feature,
            "label": label,
            "status": "stopped",
            "reason": "Gündəlik AI çağırış limiti dolub.",
        }
    return {
        "id": feature,
        "label": label,
        "status": "running",
        "reason": "İşləyir.",
    }


def _provider_slots(kind: str) -> list[dict]:
    from app.ai_gateway import gateway as gw

    if kind == "chat":
        order = gw._provider_order("AI_CHAT_PROVIDERS", "gemini,groq,nvidia,openrouter,openai")
        live = {p.name: p for p in gw._chat_providers()}
    else:
        order = gw._provider_order("AI_EMBED_PROVIDERS", "nvidia,openai")
        live = {p.name: p for p in gw._embed_providers()}

    gateway_on = gw.enabled()
    out: list[dict] = []
    for index, name in enumerate(order):
        key_env = _PROVIDER_KEY_ENV.get(name, "")
        label = _PROVIDER_LABELS.get(name, name)
        configured = name in live
        model = live[name].model if configured else ""
        if not configured:
            out.append(
                {
                    "id": name,
                    "label": label,
                    "kind": kind,
                    "model": "",
                    "order": index + 1,
                    "status": "stopped",
                    "reason": (
                        f"{key_env or name} açarı yoxdur — bu provayder failover sırasına daxil deyil."
                        if key_env
                        else "Provayder konfiqurasiya olunmayıb."
                    ),
                }
            )
            continue
        if not gateway_on:
            out.append(
                {
                    "id": name,
                    "label": label,
                    "kind": kind,
                    "model": model,
                    "order": index + 1,
                    "status": "stopped",
                    "reason": "AI gateway sönülüdür; provayder çağırılmır.",
                }
            )
            continue
        out.append(
            {
                "id": name,
                "label": label,
                "kind": kind,
                "model": model,
                "order": index + 1,
                "status": "running",
                "reason": "Açar var; failover sırasındadır.",
            }
        )
    return out


def _apply_budget_to_providers(providers: list[dict], *, budget_hit: bool) -> list[dict]:
    if not budget_hit:
        return providers
    updated = []
    for row in providers:
        if row["status"] == "running":
            updated.append(
                {
                    **row,
                    "status": "stopped",
                    "reason": "Gündəlik AI çağırış limiti dolub; provayder çağırılmır.",
                }
            )
        else:
            updated.append(row)
    return updated


def _usage_today(conn: sqlite3.Connection | None) -> tuple[int, list[dict]]:
    if conn is None:
        return 0, []
    from app.ai_gateway.gateway import ensure_ai_tables

    ensure_ai_tables(conn)
    day = date.today().isoformat()
    rows = conn.execute(
        """
        SELECT purpose, calls, prompt_tokens, completion_tokens, cost_usd
        FROM ai_usage_daily
        WHERE day = ?
        ORDER BY calls DESC
        """,
        (day,),
    ).fetchall()
    usage = []
    total = 0
    for row in rows:
        calls = int(_cell(row, "calls", 1) or 0)
        total += calls
        usage.append(
            {
                "purpose": str(_cell(row, "purpose", 0) or ""),
                "calls": calls,
                "prompt_tokens": int(_cell(row, "prompt_tokens", 2) or 0),
                "completion_tokens": int(_cell(row, "completion_tokens", 3) or 0),
                "cost_usd": float(_cell(row, "cost_usd", 4) or 0),
            }
        )
    return total, usage


def _source_run_ok(source: dict, *, key_ok: bool) -> tuple[str, str]:
    if not source["enabled"]:
        return "stopped", "Mənbə staff kataloqunda söndürülüb."
    if source["go_decision"] != "go":
        decision = source["go_decision"] or "pending"
        if decision == "retired":
            return "stopped", "Mənbə retired edilib; artıq crawl olunmur."
        return "stopped", f"Mənbə hələ «go» deyil (status: {decision})."
    if source["api_key_env"] and not key_ok:
        return "stopped", f"{source['api_key_env']} açarı yoxdur; crawl keçilir."
    last_status = source.get("last_run_status") or ""
    last_error = (source.get("last_error") or "").strip()
    if last_status == "error":
        detail = last_error or "Naməlum xəta"
        return "stopped", f"Son crawl uğursuz olub: {detail}"
    if last_status == "running":
        return "running", "Crawl indi işləyir."
    if last_status == "ok":
        return "running", "Son crawl uğurlu olub."
    return "running", "Mənbə aktivdir; hələ bu dövrdə run yoxdur."


LINKEDIN_EXTENSION_SOURCE = "linkedin-extension"


def _empty_linkedin_extension() -> dict:
    return {
        "source_name": LINKEDIN_EXTENSION_SOURCE,
        "created": 0,
        "published_live": 0,
        "rejected": 0,
    }


def _linkedin_extension_stats(conn: sqlite3.Connection, *, since: str) -> dict:
    """Separate funnel for Chrome LinkedIn extension imports (not in crawl_runs)."""
    out = _empty_linkedin_extension()
    try:
        created_row = conn.execute(
            """
            SELECT COUNT(DISTINCT j.id) AS n
            FROM jobs j
            JOIN job_sources js ON js.job_id = j.id
            WHERE js.source_name = ?
              AND j.created_at >= ?
            """,
            (LINKEDIN_EXTENSION_SOURCE, since),
        ).fetchone()
        out["created"] = int(_cell(created_row, "n", 0) or 0)

        live_row = conn.execute(
            """
            SELECT COUNT(DISTINCT j.id) AS n
            FROM jobs j
            JOIN job_sources js ON js.job_id = j.id
            WHERE js.source_name = ?
              AND j.status = 'published'
              AND COALESCE(j.hidden, 0) = 0
              AND (j.merged_into IS NULL OR j.merged_into = 0)
            """,
            (LINKEDIN_EXTENSION_SOURCE,),
        ).fetchone()
        out["published_live"] = int(_cell(live_row, "n", 0) or 0)

        # Import always has a LinkedIn view URL; finish_item may also reject apply URLs.
        # Count LinkedIn job URLs remembered in the period (extension-attributable).
        reject_row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM crawl_rejects
            WHERE decided_at >= ?
              AND (
                LOWER(source_url) LIKE '%linkedin.com/jobs/view/%'
                OR LOWER(source_url) LIKE '%linkedin.com/jobs/search%'
              )
            """,
            (since,),
        ).fetchone()
        out["rejected"] = int(_cell(reject_row, "n", 0) or 0)
    except Exception:
        pass
    return out


def _crawl_funnel(conn: sqlite3.Connection | None, *, days: int) -> dict:
    if conn is None:
        return {
            "days": days,
            "since": _since_iso(days),
            "sources": [],
            "totals": {
                "fetched": 0,
                "selected": 0,
                "selected_new": 0,
                "published_live": 0,
            },
            "rejects_by_reason": [],
            "linkedin_extension": _empty_linkedin_extension(),
        }

    conn.executescript(_CRAWL_RUNS_DDL)
    since = _since_iso(days)

    sources = conn.execute(
        """
        SELECT id, name, homepage, enabled, go_decision, api_key_env, note
        FROM crawl_sources
        ORDER BY LOWER(name)
        """
    ).fetchall()

    run_rows = conn.execute(
        """
        SELECT source_id,
               COALESCE(SUM(found_count), 0) AS fetched,
               COALESCE(SUM(created_count), 0) AS selected_new,
               COALESCE(SUM(updated_count), 0) AS selected_seen,
               SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_runs
        FROM crawl_runs
        WHERE started_at >= ?
        GROUP BY source_id
        """,
        (since,),
    ).fetchall()
    runs_by_id = {
        int(_cell(r, "source_id", 0)): {
            "fetched": int(_cell(r, "fetched", 1) or 0),
            "selected_new": int(_cell(r, "selected_new", 2) or 0),
            "selected_seen": int(_cell(r, "selected_seen", 3) or 0),
            "error_runs": int(_cell(r, "error_runs", 4) or 0),
        }
        for r in run_rows
    }

    last_rows = conn.execute(
        """
        SELECT cr.source_id, cr.status, cr.error, cr.finished_at, cr.started_at
        FROM crawl_runs cr
        INNER JOIN (
            SELECT source_id, MAX(id) AS max_id
            FROM crawl_runs
            GROUP BY source_id
        ) latest ON latest.max_id = cr.id
        """
    ).fetchall()
    last_by_id = {
        int(_cell(r, "source_id", 0)): {
            "status": str(_cell(r, "status", 1) or ""),
            "error": str(_cell(r, "error", 2) or ""),
            "finished_at": str(_cell(r, "finished_at", 3) or ""),
            "started_at": str(_cell(r, "started_at", 4) or ""),
        }
        for r in last_rows
    }

    # Same visibility rules as the public board (sqlite_jobs._PUBLISHED_WHERE /
    # query_jobs total) — unique open ads, including employer-posted ones.
    board_live_row = conn.execute(
        """
        SELECT COUNT(*) AS published_live
        FROM jobs j
        WHERE j.status = 'published'
          AND COALESCE(j.hidden, 0) = 0
          AND (j.merged_into IS NULL OR j.merged_into = 0)
        """
    ).fetchone()
    board_live = int(_cell(board_live_row, "published_live", 0) or 0)

    # Per-source live count for the funnel table only (may overlap across sources).
    live_rows = conn.execute(
        """
        SELECT js.source_name, COUNT(DISTINCT j.id) AS published_live
        FROM jobs j
        JOIN job_sources js ON js.job_id = j.id
        WHERE j.status = 'published'
          AND COALESCE(j.hidden, 0) = 0
          AND (j.merged_into IS NULL OR j.merged_into = 0)
        GROUP BY js.source_name
        """
    ).fetchall()
    live_by_name = {
        str(_cell(r, "source_name", 0) or ""): int(_cell(r, "published_live", 1) or 0)
        for r in live_rows
    }

    out_sources: list[dict] = []
    totals = {
        "fetched": 0,
        "selected": 0,
        "selected_new": 0,
        "published_live": board_live,
    }

    for row in sources:
        sid = int(_cell(row, "id", 0))
        name = str(_cell(row, "name", 1) or "")
        api_key_env = str(_cell(row, "api_key_env", 5) or "").strip()
        key_ok = (not api_key_env) or bool(os.environ.get(api_key_env, "").strip())
        metrics = runs_by_id.get(
            sid,
            {"fetched": 0, "selected_new": 0, "selected_seen": 0, "error_runs": 0},
        )
        selected = metrics["selected_new"] + metrics["selected_seen"]
        published_live = live_by_name.get(name, 0)
        last = last_by_id.get(sid, {})
        source = {
            "name": name,
            "homepage": str(_cell(row, "homepage", 2) or ""),
            "enabled": bool(int(_cell(row, "enabled", 3) or 0)),
            "go_decision": str(_cell(row, "go_decision", 4) or ""),
            "api_key_env": api_key_env,
            "note": str(_cell(row, "note", 6) or ""),
            "key_ok": key_ok,
            "last_run_status": last.get("status") or "",
            "last_error": last.get("error") or "",
            "last_run_at": last.get("finished_at") or last.get("started_at") or "",
            "fetched": metrics["fetched"],
            "selected": selected,
            "selected_new": metrics["selected_new"],
            "selected_seen": metrics["selected_seen"],
            "published_live": published_live,
            "error_runs": metrics["error_runs"],
        }
        status, reason = _source_run_ok(source, key_ok=key_ok)
        source["status"] = status
        source["reason"] = reason
        out_sources.append(source)
        totals["fetched"] += metrics["fetched"]
        totals["selected"] += selected
        totals["selected_new"] += metrics["selected_new"]

    # Prefer sources with activity first, then name.
    out_sources.sort(
        key=lambda s: (-(s["fetched"] + s["selected"] + s["published_live"]), s["name"].lower())
    )

    reject_rows = []
    try:
        reject_rows = conn.execute(
            """
            SELECT reason, COUNT(*) AS n
            FROM crawl_rejects
            WHERE decided_at >= ?
            GROUP BY reason
            ORDER BY n DESC
            """,
            (since,),
        ).fetchall()
    except Exception:
        reject_rows = []

    rejects = [
        {"reason": str(_cell(r, "reason", 0) or ""), "count": int(_cell(r, "n", 1) or 0)}
        for r in reject_rows
    ]

    # Extension source is not a crawl_sources row — keep it out of the hourly table.
    out_sources = [s for s in out_sources if s["name"] != LINKEDIN_EXTENSION_SOURCE]

    return {
        "days": days,
        "since": since,
        "sources": out_sources,
        "totals": totals,
        "rejects_by_reason": rejects,
        "linkedin_extension": _linkedin_extension_stats(conn, since=since),
    }


def build_ops_status(conn: sqlite3.Connection | None, *, days: int = 7) -> dict:
    from app.ai_gateway import gateway as gw

    days = max(1, min(90, int(days or 7)))
    daily_calls, usage = _usage_today(conn)
    limit = gw.daily_call_limit()
    budget_hit = bool(limit > 0 and daily_calls >= limit)

    features = [_feature_detail(name, conn, budget_hit=budget_hit) for name in FEATURES]
    chat = _apply_budget_to_providers(_provider_slots("chat"), budget_hit=budget_hit)
    embed = _apply_budget_to_providers(_provider_slots("embed"), budget_hit=budget_hit)

    # Re-check feature stopped reasons after budget (gateway detail already covers it).
    if budget_hit:
        features = [_feature_detail(name, conn, budget_hit=True) for name in FEATURES]

    return {
        "generated_at": _utc_now().isoformat(timespec="seconds"),
        "ai": {
            "gateway_enabled": gw.enabled(conn),
            "key_configured": key_configured(),
            "daily_calls": daily_calls,
            "daily_limit": limit,
            "budget_ok": not budget_hit,
            "features": features,
            "chat_providers": chat,
            "embed_providers": embed,
            "usage_today": usage,
        },
        "crawl": _crawl_funnel(conn, days=days),
    }
