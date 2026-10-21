"""Azerbaijan-market fit for scraped ads.

When keyword detection finds no remote / relocation / visa signal, ask the
shared AI gateway (free providers first, OpenAI last). Unsuitable URLs are
stored in ``crawl_rejects`` so the next crawl skips them without another call.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from worker.ai_flags import feature_on
from worker.ai_gateway import complete_json
from worker.fit_mapping import FLAGS, POSITIVE_FLAGS, is_suitable, staff_percent
from worker.techstack import (
    international_reloc_offer,
    open_market_tier,
    relocation_flag,
    remote_flag,
)

log = logging.getLogger("ingress-job.worker.market_fit")

PURPOSE = "market_fit"
PROMPT_VERSION = "market-fit-v6"
ENV_FLAG = "AI_MARKET_FIT_ENABLED"

# Graded rule confidence (how sure deterministic rules are the ad is OK to publish).
# Stronger AZ-open signals → higher %; bare board default / weak keyword → lower.
_RULE_SCORE_AZ = 96
_RULE_SCORE_OPEN_PLACE = 90
_RULE_SCORE_OPEN_BODY = 84
_RULE_SCORE_INTL_RELOC = 86
_RULE_SCORE_SCHEMA = 78
_RULE_SCORE_REMOTE_PLACE = 76
_RULE_SCORE_REMOTE_TITLE = 72
_RULE_SCORE_REMOTE_TEXT = 70
_RULE_SCORE_RELOC_KW = 68
_RULE_SCORE_BOARD_DEFAULT = 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_rejects (
    source_url TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL DEFAULT '',
    via_ai INTEGER NOT NULL DEFAULT 0
);
"""

_SYSTEM = """You check international tech job ads for a job board whose candidates live in Azerbaijan (AZ).
Answer yes/no questions about the ad. Do NOT score or rate the ad; our code computes the score from your answers.

A person living in Azerbaijan can take a job only through one of these routes:
A. Remote from Azerbaijan: the ad names Azerbaijan, says worldwide / anywhere in the world / any country, or names a region that clearly includes Azerbaijan (EMEA, Europe + Caucasus, CIS, Central Asia, ...) with nothing excluding Azerbaijan.
B. Relocation: genuine relocation support for this role to a work location an Azerbaijan resident can realistically reach.
C. Visa / work permit: explicit visa or work-permit sponsorship for this role.
If the evidence is ambiguous, answer false. Never invent facts.

Not enough on their own (answer false for A): "remote", "fully remote", "remote-friendly", "flexible work location", "work from home or the office", "distributed team", "WFH", "hybrid". "Up to N days per year working from abroad" is temporary_abroad_only, not remote.
"Relocation benefits may vary" and other generic relocation phrases are weak: relocation=true only for a clear offer for this role. Relocation does not imply visa support.
A board/source location tag is a clue, not proof. The company's global presence or customers do not mean it hires in Azerbaijan.
Check the title, location, requirements, benefits, footnotes and application instructions for contradictions; restrictions ("must reside in", "right to work in", "no sponsorship", "EU only", one named country) win over vague positives.

For each flag return {"value": true/false, "quote": "..."}. quote = the exact sentence or phrase copied from the ad (max 160 characters) that makes the flag true; empty string when false. Never paraphrase a quote.
- remote_worldwide: remote from any country / worldwide / anywhere in the world.
- remote_region_includes_az: remote within a named region that clearly includes Azerbaijan.
- remote_az_explicit: the ad explicitly allows working from Azerbaijan or Baku.
- relocation: genuine relocation support for this role (put the target country/city in the quote if the ad states it).
- visa_support: explicit visa or work-permit sponsorship.
- country_restricted: the remote work or the role is limited to specific countries, residency or citizenship, or needs the right to work there without sponsorship.
- temporary_abroad_only: working abroad only temporarily (e.g. "up to 30 days per year abroad").
- no_sponsorship_stated: the ad says it does not sponsor visas / work permits.
- text_truncated_or_missing_location: the ad text is truncated or does not say where the work is done.
reason: one or two short sentences in Azerbaijani for the moderator naming the route or the blocker (e.g. "Yalnız Bolqarıstan daxilində remote; Azərbaycandan iş təsdiqlənmir; relocation/viza yoxdur.").

Reply with JSON only, matching the schema."""

_FLAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["value", "quote"],
    "properties": {"value": {"type": "boolean"}, "quote": {"type": "string"}},
}

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*FLAGS, "reason"],
    "properties": {**{name: _FLAG_SCHEMA for name in FLAGS}, "reason": {"type": "string"}},
}

# Ad text budget for the user prompt (~8k tokens). Longer ads keep the head plus
# every paragraph about location / eligibility / benefits / relocation / visa.
PROMPT_TEXT_MAX = 30000
_KEY_PARAGRAPH = re.compile(
    r"(?i)location|remote|hybrid|on[\s-]?site|office|relocat|visa|sponsor|work\s+permit|"
    r"right\s+to\s+work|authori[sz]|eligib|resid|based\s+in|citizen|countr|abroad|"
    r"time\s?zone|requirement|qualif|benefit|perk|we\s+offer|apply|application|"
    r"contract|\*|footnote|vary"
)


def prompt_ad_text(text: str, limit: int = PROMPT_TEXT_MAX) -> tuple[str, bool]:
    """Full ad text when it fits; otherwise head + all eligibility-relevant paragraphs."""
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw, False
    paras = [p for p in re.split(r"\n\s*\n|\n(?=\s*[-•*]\s)", raw) if p.strip()]
    keep: set[int] = set()
    used = 0
    head_budget = limit // 4
    for i, para in enumerate(paras):  # head (role summary)
        if used + len(para) > head_budget:
            break
        keep.add(i)
        used += len(para) + 2
    for i, para in enumerate(paras):  # eligibility-relevant paragraphs anywhere
        if i in keep or not _KEY_PARAGRAPH.search(para):
            continue
        if used + len(para) > limit:
            continue
        keep.add(i)
        used += len(para) + 2
    for i in range(len(paras) - 1, -1, -1):  # footer
        if i in keep:
            continue
        if used + len(paras[i]) > limit:
            break
        keep.add(i)
        used += len(paras[i]) + 2
    out: list[str] = []
    last = -1
    for i in sorted(keep):
        if i != last + 1:
            out.append("[… omitted …]")
        out.append(paras[i])
        last = i
    if last != len(paras) - 1:
        out.append("[… omitted …]")
    return "\n\n".join(out), True


def clamp_confidence(raw: Any) -> int:
    """Normalize AI confidence to 0–100."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


def fit_score(*, suitable: bool, confidence: int) -> int:
    """Staff-facing % = how sure AI is the ad is OK to publish under our rules.

    Example: 30 ≈ unsure; 90 ≈ sure it qualifies; rejected/unsuitable must
    never show as 100. Older models sometimes returned suitable=false + 100
    ("sure of the reject") — invert that into a low publish-confidence.
    """
    raw = clamp_confidence(confidence)
    if suitable:
        return raw
    return min(raw, 100 - raw, 35)


def ensure_rejects_table(conn: sqlite3.Connection | None) -> None:
    if conn is None:
        return
    conn.executescript(_SCHEMA)


def is_rejected(conn: sqlite3.Connection | None, source_url: str) -> bool:
    url = (source_url or "").strip()
    if not url or conn is None:
        return False
    ensure_rejects_table(conn)
    row = conn.execute(
        "SELECT 1 FROM crawl_rejects WHERE source_url = ?",
        (url,),
    ).fetchone()
    return row is not None


def mark_rejected(
    conn: sqlite3.Connection | None,
    source_url: str,
    reason: str = "",
    *,
    via_ai: bool = False,
) -> None:
    url = (source_url or "").strip()
    if not url or conn is None:
        return
    ensure_rejects_table(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO crawl_rejects (source_url, reason, decided_at, via_ai)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_url) DO UPDATE SET
            reason = excluded.reason,
            decided_at = excluded.decided_at,
            via_ai = excluded.via_ai
        """,
        (url, (reason or "")[:300], now, 1 if via_ai else 0),
    )
    try:
        conn.commit()
    except Exception:
        pass


def has_clear_market_signal(
    title: str,
    place: str,
    text: str,
    *,
    pre_remote: bool | None,
    pre_relocation: bool | None,
    remote_default: bool,
    relocation_default: bool,
) -> bool:
    """True when keywords, source schema, or board default already decides."""
    return rule_fit_confidence(
        title,
        place,
        text,
        pre_remote=pre_remote,
        pre_relocation=pre_relocation,
        remote_default=remote_default,
        relocation_default=relocation_default,
    ) is not None


def rule_fit_confidence(
    title: str,
    place: str,
    text: str,
    *,
    pre_remote: bool | None,
    pre_relocation: bool | None,
    remote_default: bool,
    relocation_default: bool,
) -> dict[str, Any] | None:
    """Graded rule %: how sure deterministic rules are the ad is OK to publish.

    Returns ``{"confidence": 0-100, "reason": str}`` when keywords / schema /
    board default give a market signal; None when AI should decide instead.
    Never returns a flat 100 for every clear hit — stronger open-market and
    visa/reloc evidence scores higher than a bare board default.
    """
    kw_remote = remote_flag(title, place, text)
    kw_reloc = relocation_flag(title, place, text)
    schema_remote = pre_remote is True
    schema_reloc = pre_relocation is True
    board_remote = bool(remote_default)
    board_reloc = bool(relocation_default)

    if not (
        kw_remote
        or kw_reloc
        or schema_remote
        or schema_reloc
        or board_remote
        or board_reloc
    ):
        return None

    open_tier = open_market_tier(title, place, text)
    intl_reloc = international_reloc_offer(title, place, text)
    title_remote = bool(
        re.search(r"(?i)\bremote\b", title or "")
        and not re.search(r"(?i)\bhybrid\b|on[\s-]?site", title or "")
    )
    place_remote = bool(
        re.search(r"(?i)\bremote\b|worldwide|anywhere|telecommute|\bwfh\b", place or "")
        and not re.search(r"(?i)\bhybrid\b", place or "")
    )

    # Strongest matching evidence wins; small bonus when several agree.
    candidates: list[tuple[int, str]] = []
    if open_tier == "az":
        candidates.append((_RULE_SCORE_AZ, "azerbaijan / CIS open market"))
    elif open_tier == "place":
        candidates.append((_RULE_SCORE_OPEN_PLACE, "open remote place (worldwide/EMEA)"))
    elif open_tier == "body":
        candidates.append((_RULE_SCORE_OPEN_BODY, "open-market wording in description"))
    if intl_reloc:
        candidates.append((_RULE_SCORE_INTL_RELOC, "international visa / relocation"))
    elif kw_reloc:
        candidates.append((_RULE_SCORE_RELOC_KW, "relocation keywords"))
    if schema_remote or schema_reloc:
        candidates.append((_RULE_SCORE_SCHEMA, "source schema remote/relocation"))
    if place_remote:
        candidates.append((_RULE_SCORE_REMOTE_PLACE, "remote location field"))
    if title_remote:
        candidates.append((_RULE_SCORE_REMOTE_TITLE, "remote in title"))
    if kw_remote and not (place_remote or title_remote or open_tier):
        candidates.append((_RULE_SCORE_REMOTE_TEXT, "remote keywords in description"))
    if (board_remote or board_reloc) and not (
        kw_remote or kw_reloc or schema_remote or schema_reloc or open_tier
    ):
        candidates.append((_RULE_SCORE_BOARD_DEFAULT, "board remote/relocation default"))

    if not candidates:
        # Schema/board + weak overlap already covered; fall back sanely.
        if schema_remote or schema_reloc:
            candidates.append((_RULE_SCORE_SCHEMA, "source schema remote/relocation"))
        elif board_remote or board_reloc:
            candidates.append((_RULE_SCORE_BOARD_DEFAULT, "board remote/relocation default"))
        elif kw_remote:
            candidates.append((_RULE_SCORE_REMOTE_TEXT, "remote keywords"))
        else:
            candidates.append((_RULE_SCORE_RELOC_KW, "relocation keywords"))

    score, reason = max(candidates, key=lambda row: row[0])

    bonus = 0
    evidence = sum(
        (
            1 if open_tier else 0,
            1 if intl_reloc or kw_reloc else 0,
            1 if kw_remote or place_remote or title_remote else 0,
            1 if schema_remote or schema_reloc else 0,
        )
    )
    if evidence >= 3:
        bonus += 6
    elif evidence >= 2:
        bonus += 3
    if (schema_remote or schema_reloc) and (kw_remote or kw_reloc or open_tier):
        bonus += 2

    # Cap below absolute 100 unless AZ/CIS is named — leaves room for staff doubt.
    capped = clamp_confidence(score + bonus)
    # Rules alone never reach the 85 approve band (eligibility is checked separately).
    from worker.eligibility import RULE_MAX

    capped = min(capped, RULE_MAX)
    return {
        "confidence": capped,
        "reason": reason,
    }


# Last clarify miss reason (for recheck job / ops; not a public API).
last_miss_error: str = ""

# After each crawl pass: AI-score pending scraped ads that still lack ai_confidence
# (rule-passed rows show AI% empty until staff used to click recheck). Leftover
# rows wait for the next hourly pass. Override with AI_MARKET_FIT_AUTO_SCORE_LIMIT.
AUTO_SCORE_PER_RUN = 40


def auto_score_limit() -> int:
    raw = (os.environ.get("AI_MARKET_FIT_AUTO_SCORE_LIMIT") or "").strip()
    if not raw:
        return AUTO_SCORE_PER_RUN
    try:
        return max(0, min(200, int(raw)))
    except ValueError:
        return AUTO_SCORE_PER_RUN


_PENDING_SCRAPED = """
    SELECT id, title, company, city, text, remote, relocation,
           rule_confidence, ai_confidence, COALESCE(market_fit_reason, '') AS market_fit_reason,
           (SELECT source_url FROM job_sources s WHERE s.job_id = jobs.id
            ORDER BY s.id LIMIT 1) AS source_url
    FROM jobs
    WHERE status = 'pending'
      AND COALESCE(owner_subject, '') = ''
      AND COALESCE(merged_into, 0) = 0
"""

RULE_REASON_PREFIX = "Qayda: "
AI_REASON_PREFIX = "AI: "


def _row_eligibility(row) -> dict[str, Any]:
    from worker.eligibility import assess

    return assess(
        row["title"] or "",
        row["city"] or "",
        row["text"] or "",
        source_remote=bool(int(row["remote"] or 0)) or None,
        source_url=str(row["source_url"] or ""),
    )


def apply_eligibility_to_pending(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    reset_ai: bool = False,
) -> dict[str, Any]:
    """Cap rule/AI % of pending scraped ads by Azerbaijan eligibility (no AI calls).

    Never changes status. ``reset_ai`` clears AI % scored by older prompts (reason
    not from market-fit-v5) so the next pass re-asks the AI with the v5 rubric.
    """
    from worker.eligibility import CAP_LOCKED, RULE_MAX, summary

    sql = _PENDING_SCRAPED + " ORDER BY id ASC"
    params: tuple = ()
    if limit:
        sql += " LIMIT ?"
        params = (int(limit),)
    rows = conn.execute(sql, params).fetchall()
    stats: dict[str, Any] = {"scanned": len(rows), "changed": 0, "ai_reset": 0, "locked": 0, "changes": []}
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for row in rows:
        elig = _row_eligibility(row)
        cap = int(elig["cap"])
        rule = row["rule_confidence"]
        ai = row["ai_confidence"]
        reason = str(row["market_fit_reason"] or "")
        new_rule = None if rule is None else min(int(rule), cap, RULE_MAX)
        if cap <= CAP_LOCKED:
            new_rule = min(new_rule if new_rule is not None else cap, cap)
            stats["locked"] += 1
        new_ai = None if ai is None else min(int(ai), cap)
        if reset_ai and ai is not None and not reason.startswith(AI_REASON_PREFIX):
            new_ai = None
            stats["ai_reset"] += 1
        new_reason = reason
        if cap < 100 and not reason.startswith(AI_REASON_PREFIX):
            new_reason = (RULE_REASON_PREFIX + summary(elig))[:800]
        if (new_rule, new_ai, new_reason) == (rule, ai, reason):
            continue
        stats["changed"] += 1
        if len(stats["changes"]) < 200:
            stats["changes"].append(
                {"id": int(row["id"]), "rule": [rule, new_rule], "ai": [ai, new_ai], "reason": new_reason[:160]}
            )
        if dry_run:
            continue
        conn.execute(
            """
            UPDATE jobs SET rule_confidence = ?, ai_confidence = ?, market_fit_reason = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (new_rule, new_ai, new_reason, now, int(row["id"])),
        )
    if not dry_run:
        conn.commit()
    return stats


def score_pending_without_ai(
    conn: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Fill AI % on pending scraped ads missing ``ai_confidence`` (market-fit-v5).

    AI % is capped by the deterministic Azerbaijan eligibility check. Outcomes:
    works from AZ / relocation → write capped ``ai_confidence``; unclear → stays
    pending with a low capped score; clear "no" → ``status=rejected``.
    Hard-locked rows (rule_confidence <= 10) are not sent to the AI.
    Company/manual ads (owner_subject) skipped. Oldest id first. Soft-no-op when
    market_fit / gateway is off.
    """
    from worker.eligibility import CAP_LOCKED

    cap = AUTO_SCORE_PER_RUN if limit is None else max(0, int(limit))
    stats = {"planned": 0, "checked": 0, "rejected": 0, "failed": 0, "skipped": 0}
    if cap <= 0:
        return stats
    if not feature_on("market_fit", conn) or not feature_on("gateway", conn):
        return stats

    rows = conn.execute(
        _PENDING_SCRAPED
        + " AND ai_confidence IS NULL AND COALESCE(rule_confidence, 100) > ? ORDER BY id ASC LIMIT ?",
        (CAP_LOCKED, cap),
    ).fetchall()
    stats["planned"] = len(rows)
    if not rows:
        return stats

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for row in rows:
        job_id = int(row["id"])
        live = conn.execute(
            """
            SELECT status, ai_confidence, COALESCE(owner_subject, '') AS owner_subject
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        if (
            live is None
            or (live["status"] or "") != "pending"
            or live["ai_confidence"] is not None
            or (live["owner_subject"] or "") != ""
        ):
            stats["skipped"] += 1
            continue

        elig = _row_eligibility(row)
        verdict = clarify_market_fit(
            title=row["title"] or "",
            company=row["company"] or "",
            place=row["city"] or "",
            text=row["text"] or "",
            conn=conn,
            source_meta=source_meta_line(
                remote=bool(int(row["remote"] or 0)),
                relocation=bool(int(row["relocation"] or 0)),
                place=row["city"] or "",
                countries=[elig_place] if (elig_place := _slug_place(row)) else None,
            ),
        )
        if verdict is None:
            stats["failed"] += 1
            # Feature flipped off mid-batch — stop burning attempts.
            if last_miss_error in {"market_fit_off", "ai_disabled"}:
                break
            continue

        reason = str(verdict.get("reason") or "")[:800]
        confidence = min(int(verdict.get("confidence") or 0), int(elig["cap"]))
        if not verdict.get("suitable") and not verdict.get("unclear"):
            conn.execute(
                """
                UPDATE jobs
                SET status = 'rejected',
                    reject_reason = ?,
                    rule_confidence = NULL,
                    ai_confidence = ?,
                    market_fit_reason = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending' AND ai_confidence IS NULL
                """,
                (reason[:300] or "unsuitable", confidence, reason, now, job_id),
            )
            stats["checked"] += 1
            stats["rejected"] += 1
        elif verdict.get("unclear"):
            # Unconfirmed: keep flags as they are, stay pending with a low score.
            conn.execute(
                """
                UPDATE jobs
                SET ai_confidence = ?, market_fit_reason = ?, updated_at = ?
                WHERE id = ? AND status = 'pending' AND ai_confidence IS NULL
                """,
                (confidence, reason, now, job_id),
            )
            stats["checked"] += 1
        else:
            remote = 1 if verdict.get("remote") else 0
            relocation = 1 if verdict.get("relocation") else 0
            conn.execute(
                """
                UPDATE jobs
                SET remote = ?,
                    relocation = ?,
                    ai_confidence = ?,
                    market_fit_reason = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'pending' AND ai_confidence IS NULL
                """,
                (remote, relocation, confidence, reason, now, job_id),
            )
            stats["checked"] += 1
        conn.commit()
    return stats


def _slug_place(row) -> str:
    from worker.eligibility import place_from_source_url

    return place_from_source_url(str(row["source_url"] or ""))


def clarify_market_fit(
    *,
    title: str,
    company: str,
    place: str,
    text: str,
    conn: sqlite3.Connection | None,
    source_meta: str = "",
) -> dict[str, Any] | None:
    """Ask AI. Returns verdict dict, or None when AI is off / fails.

    ``source_meta`` (connector remote flag / location / countries) is sent labelled
    as possibly wrong; the AI must decide from the ad text.
    """
    global last_miss_error
    if not feature_on("market_fit", conn):
        last_miss_error = "market_fit_off"
        log.warning("market_fit skipped: feature off")
        return None
    if not feature_on("gateway", conn):
        last_miss_error = "ai_disabled"
        log.warning("market_fit skipped: gateway off")
        return None
    user = build_user_prompt(
        title=title, company=company, place=place, text=text, source_meta=source_meta
    )
    result = complete_json(
        purpose=PURPOSE,
        prompt_version=PROMPT_VERSION,
        system=_SYSTEM,
        user=user,
        schema=_JSON_SCHEMA,
        schema_name="market_fit",
        conn=conn,
        timeout=45.0,
    )
    if not result.ok or not isinstance(result.data, dict):
        last_miss_error = (result.error or "failed")[:180]
        log.warning("market_fit ai miss: %s", last_miss_error)
        return None
    last_miss_error = ""
    return verdict_from_ai(result.data, ad_text=f"{title}\n{place}\n{text}", cached=bool(result.cached))


def build_user_prompt(
    *, title: str, company: str, place: str, text: str, source_meta: str = ""
) -> str:
    meta = " ".join(str(source_meta or "").split())[:400] or "(none)"
    body, truncated = prompt_ad_text(text)
    note = (
        "Ad text: TRUNCATED — some paragraphs were omitted ([… omitted …]). Do not assume "
        "anything favourable about the missing parts."
        if truncated
        else "Ad text: complete."
    )
    return (
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Board location field (clue, may be wrong): {place or '(empty)'}\n"
        f"Source metadata (clue, may be wrong): {meta}\n"
        f"{note}\n\n"
        f"<ad>\n{body}\n</ad>"
    )


_FLAG_AZ = {
    "remote_az_explicit": "Azərbaycandan remote açıq yazılıb",
    "remote_worldwide": "istənilən ölkədən remote",
    "remote_region_includes_az": "Azərbaycanı əhatə edən regiondan remote",
    "relocation": "relocation dəstəyi",
    "visa_support": "viza/iş icazəsi dəstəyi",
    "country_restricted": "ölkə/rezidentlik məhdudiyyəti",
    "temporary_abroad_only": "yalnız müvəqqəti xaricdən iş",
    "no_sponsorship_stated": "viza sponsorluğu yoxdur",
    "text_truncated_or_missing_location": "mətn kəsilib və ya iş yeri yazılmayıb",
}


def _norm(value: str) -> str:
    return " ".join(re.sub(r"[“”\"'’‘`*_]", " ", value or "").lower().split())


def _quote_in_ad(quote: str, ad: str) -> bool:
    q = _norm(quote)
    if len(q) < 4:
        return False
    a = _norm(ad)
    return q in a or (len(q) > 40 and q[:40] in a)


def verdict_from_ai(data: dict[str, Any], *, ad_text: str = "", cached: bool = False) -> dict[str, Any]:
    """Turn the AI's yes/no flags into a verdict; the % comes from :func:`staff_percent`.

    A positive flag counts only with a quote that really appears in the ad text
    (when ``ad_text`` is given). Restrictive flags count even without a quote.
    """
    flags: dict[str, bool] = {}
    quotes: dict[str, str] = {}
    dropped: list[str] = []
    for name in FLAGS:
        raw = data.get(name) if isinstance(data.get(name), dict) else {}
        value = bool(raw.get("value"))
        quote = " ".join(str(raw.get("quote") or "").split())[:160]
        if value and name in POSITIVE_FLAGS:
            if not quote or (ad_text and not _quote_in_ad(quote, ad_text)):
                value = False
                dropped.append(name)
        flags[name] = value
        quotes[name] = quote if value else ""
    score, route = staff_percent(flags)
    true_parts = [
        f"{name} ({_FLAG_AZ[name]})" + (f" “{quotes[name]}”" if quotes[name] else "")
        for name in FLAGS
        if flags[name]
    ]
    reason_az = " ".join(str(data.get("reason") or "").split())[:240]
    reason = (
        f"{AI_REASON_PREFIX}{score}% AI-nın bəli/xeyr yoxlamalarından hesablanıb · "
        + ("; ".join(true_parts) if true_parts else "heç bir bayraq doğru deyil")
        + (f" · sitatsız/tapılmayan rədd edildi: {', '.join(dropped)}" if dropped else "")
        + (f" · {reason_az}" if reason_az else "")
    )
    suitable = is_suitable(route)
    return {
        "suitable": suitable,
        "unclear": route == "no_evidence",
        "remote": flags["remote_az_explicit"] or flags["remote_worldwide"] or flags["remote_region_includes_az"],
        "relocation": flags["relocation"],
        "visa_support": flags["visa_support"] and not flags["no_sponsorship_stated"],
        "flags": flags,
        "quotes": quotes,
        "route": route,
        "reason": reason[:800],
        "confidence": score,
        "cached": cached,
    }


def source_meta_line(
    *, remote: object = None, relocation: object = None, place: str = "", countries=None, source: str = ""
) -> str:
    bits = []
    if source:
        bits.append(f"source={source}")
    if remote is not None:
        bits.append(f"remote_flag={bool(remote)}")
    if relocation is not None:
        bits.append(f"relocation_flag={bool(relocation)}")
    if place:
        bits.append(f"location={place}")
    if countries:
        bits.append("countries=" + ", ".join(str(c) for c in countries[:8]))
    return "; ".join(bits)


def checked_verdict(
    *,
    title: str,
    company: str,
    place: str,
    text: str,
    conn: sqlite3.Connection | None,
    source_url: str = "",
    source_remote: bool | None = None,
    source_relocation: bool | None = None,
    countries: list[str] | None = None,
    source: str = "",
) -> dict[str, Any] | None:
    """Eligibility gate + AI flags + cap: the one path for staff rechecks / fills.

    Hard-locked ads (country-only remote etc.) are answered without an AI call.
    Otherwise the AI % (from fit_mapping) is capped by the eligibility cap and
    the eligibility summary is appended to the reason. None = AI off / failed.
    """
    from worker.eligibility import assess, is_hard_reject, summary

    elig = assess(
        title,
        place,
        text,
        countries=countries or None,
        source_remote=source_remote,
        source_url=source_url,
        source=source,
    )
    if is_hard_reject(elig):
        return {
            "suitable": False,
            "unclear": False,
            "remote": False,
            "relocation": False,
            "confidence": int(elig["cap"]),
            "reason": (RULE_REASON_PREFIX + summary(elig))[:800],
            "hard_reject": True,
            "cached": False,
        }
    verdict = clarify_market_fit(
        title=title,
        company=company,
        place=place,
        text=text,
        conn=conn,
        source_meta=source_meta_line(
            remote=source_remote,
            relocation=source_relocation,
            place=place,
            countries=countries,
            source=source,
        ),
    )
    if verdict is None:
        return None
    cap = int(elig["cap"])
    verdict["confidence"] = min(int(verdict.get("confidence") or 0), cap)
    if cap < 100:
        verdict["reason"] = (str(verdict.get("reason") or "") + " · Qayda: " + summary(elig))[:800]
    return verdict


def checked_rule_fit(
    title: str,
    place: str,
    text: str,
    *,
    pre_remote: bool | None,
    pre_relocation: bool | None,
    source_url: str = "",
) -> dict[str, Any] | None:
    """rule_fit_confidence capped by eligibility (never ≥ 85), reason with eligibility line."""
    from worker.eligibility import assess, cap_score, summary

    rule_fit = rule_fit_confidence(
        title,
        place,
        text,
        pre_remote=pre_remote,
        pre_relocation=pre_relocation,
        remote_default=False,
        relocation_default=False,
    )
    if not rule_fit:
        return None
    elig = assess(title, place, text, source_remote=pre_remote, source_url=source_url)
    return {
        "confidence": cap_score(int(rule_fit["confidence"]), elig, rule=True),
        "reason": (
            RULE_REASON_PREFIX
            + summary(elig)
            + f" · qayda siqnalı: {rule_fit.get('reason') or 'market signal'}"
        )[:800],
    }
