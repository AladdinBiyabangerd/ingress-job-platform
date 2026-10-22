"""Azerbaijan-market fit for scraped ads.

When keyword detection finds no remote / relocation / visa signal, ask the
shared AI gateway (free providers first, OpenAI last). Unsuitable URLs are
stored in ``crawl_rejects`` so the next crawl skips them without another call.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from worker.ai_flags import feature_on
from worker.ai_gateway import complete_json
from worker.az_context import NEGATION, NEGATION_OK, classify_unit, quote_az_context
from worker.fit_mapping import (
    AI_FLAGS,
    FLAGS,
    POSITIVE_FLAGS,
    CONFLICTS_AZ,
    TRUNCATION_HINT,
    VISA_NOTES_AZ,
    conflicts,
    visa_note,
    visa_strength,
    is_suitable,
    staff_percent,
    upgrade_legacy,
)
from worker.techstack import (
    international_reloc_offer,
    open_market_tier,
    relocation_flag,
    remote_flag,
)

log = logging.getLogger("ingress-job.worker.market_fit")

PURPOSE = "market_fit"
PROMPT_VERSION = "market-fit-v10"
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

_FLAG_DEFINITIONS = {
    "remote_worldwide": "the role can be done remotely from any country / worldwide / anywhere in the world.",
    "remote_region_includes_az": (
        'the role can be done remotely within a named geographic region that clearly includes Azerbaijan '
        '(e.g. "EMEA", "CIS", "Caucasus"). A time-zone range or UTC offset alone does not count.'
    ),
    "remote_az_explicit": (
        "the ad explicitly allows working from Azerbaijan or Baku: remote from Azerbaijan, Azerbaijan or Baku "
        'named in a list of places where the role is open (title "Engineer (Europe, Georgia, Azerbaijan)", '
        'location field "Armenia, Azerbaijan, Georgia", "Remote (Azerbaijan, Georgia)", "We hire in Azerbaijan"), '
        'or hybrid / on-site work in Baku or elsewhere in Azerbaijan ("Baku office, on-site"). Not when the ad '
        'excludes Azerbaijan ("excluding Azerbaijan", "not available in Azerbaijan"), and not for a statement '
        'that the company, its client or its team is based in or works with Azerbaijan ("Our client is based in '
        'Baku", "the team is international (Ukraine, Azerbaijan)").'
    ),
    "relocation": "genuine relocation support for this role (quote the target country or city when the ad states it).",
    "visa_support": (
        'the ad says it sponsors visas or work permits (a general "We do sponsor visas!" counts). '
        "Relocation alone is not visa support."
    ),
    "visa_support_conditional": (
        "the sponsorship is qualified: not guaranteed, not possible for every role or every candidate, case by case, "
        '"where possible", "may sponsor", subject to eligibility, or only a general company-wide statement that does '
        "not commit for this role. Quote the qualifying sentence. Always false when visa_support is false."
    ),
    "remote_country_restricted": (
        "the remote work is limited to named countries or regions that do not clearly include Azerbaijan "
        '(e.g. "Remote within Germany", "Remote — US residents only", "Must be based in the EU"), or the ad '
        "explicitly uses a time-zone range as an eligibility rule that excludes UTC+4 (e.g. \"must be located "
        "between UTC-5 and UTC-8\", \"only candidates in UTC-5..UTC-8\"). Not for a working-hours overlap "
        '("overlap with CET"), not for a statement about the company itself ("US-based company", '
        '"headquartered in London"), and not when the remote work is worldwide and only names other countries '
        'as exceptions ("worldwide (except Russia)"). An exclusion list that names only other countries '
        '("candidates from Russia and Belarus are not considered") is not a restriction against Azerbaijan. '
        "A time-zone rule that includes UTC+4 is neither a restriction nor confirmation."
    ),
    "candidate_location_restricted": (
        "the ad explicitly requires applicants to already reside in, be citizens or residents of, or have a "
        "specified history of residence in a named country or region that excludes Azerbaijan. Do not set this "
        "flag solely because the job is based in that country, or when the ad explicitly accepts applicants "
        "willing to relocate there as an alternative."
    ),
    "work_authorization_required": (
        "applicants must already hold the right to work in a named country, without employer sponsorship. "
        'Not for "authorized to work from your home location".'
    ),
    "temporary_abroad_only": 'working from abroad is allowed only temporarily (e.g. "up to 30 days per year").',
    "no_sponsorship_stated": "the ad explicitly says it does not sponsor visas or work permits.",
    "text_truncated": (
        "a hint only. True when you can see the text is cut (\"[… omitted …]\", it stops mid-sentence or ends "
        'with "...") or the message says it is truncated. Our code decides the final value from how the text '
        "was obtained; your false never overrides a cut the code knows about. Separate from "
        "work_location_unspecified."
    ),
    "work_location_unspecified": (
        "neither the title, the location field nor the ad text says where the work is done or from where remote "
        "work is allowed (a country list in the title or location field does say it)."
    ),
}
_EXAMPLE_ON = {
    "relocation": ["We offer relocation support to Berlin."],
    "visa_support": ["We do sponsor visas!"],
    "visa_support_conditional": ["Sponsorship is decided case by case and is not possible for every candidate."],
}
_EXAMPLE_REASON = (
    "Berlinə relocation təklif olunur; viza sponsorluğu var, amma hər namizəd üçün zəmanət verilmir."
)


def _example_json() -> str:
    lines = [
        f'  "{name}": {{"value": {"true" if name in _EXAMPLE_ON else "false"}, '
        f'"quotes": {json.dumps(_EXAMPLE_ON.get(name, []), ensure_ascii=False)}}},'
        for name in FLAGS
    ]
    lines.append(f'  "reason": {json.dumps(_EXAMPLE_REASON, ensure_ascii=False)}')
    return "{\n" + "\n".join(lines) + "\n}"


_SYSTEM_TEMPLATE = """You check international tech job ads for a job board whose candidates live in Azerbaijan (AZ).
Extract evidence, not conclusions: answer yes/no questions about the ad and copy the text that supports each answer. Do NOT score the ad or decide whether it is suitable; our code computes the result from your answers.

A person living in Azerbaijan can take a job only through one of these routes:
A. Remote from Azerbaijan: the ad explicitly allows Azerbaijan or Baku, allows work from anywhere in the world, or names a geographic region that clearly includes Azerbaijan. A time-zone overlap or UTC offset alone is not evidence of geographic eligibility.
B. Relocation: genuine relocation support for this role.
C. Visa / work permit: explicit visa or work-permit sponsorship for this role.
If the evidence is ambiguous, answer false. Never invent facts.

Not enough on their own for route A: "remote", "fully remote", "remote-first", "remote-friendly", "flexible work location", "work from home or the office", "distributed team", "WFH", "hybrid", "almost any country", "most countries", a time-zone overlap or UTC range ("UTC+2 to UTC+6", "overlap with CET"), a statement about the company itself ("US-based company", "headquartered in London"). "Up to N days or weeks per year working from abroad" is temporary_abroad_only, not remote.
"Relocation benefits may vary", "where applicable" and other generic relocation phrases are weak: relocation=true only for a clear offer for this role. Relocation does not imply visa support, and visa support does not imply relocation.
The source metadata is a clue, not proof. The title and the location field are part of the ad: a country or city list there (e.g. a title ending "(Europe, Georgia, Turkey, Azerbaijan, Ukraine)" or a location field "Armenia, Azerbaijan, Georgia") names the places the role is open to; quote that list verbatim when you use it. If the ad text gives a different allowed-country list that leaves Azerbaijan out, set both flags and quote both.

Evidence extraction and conflict handling
1. Extract evidence, not conclusions. Evaluate each flag independently. Several flags may be true at once when the ad contains evidence for each one, even when they contradict each other.
2. A quote must directly support that specific flag. Do not use a general sentence about remote work as evidence for worldwide eligibility, or a relocation statement as evidence of visa sponsorship.
3. For restrictions, preserve the exact scope. A requirement to have work authorization in a specific country is not automatically a restriction on every remote-work option; decide from the context whether it limits the remote work, the candidates, or only an on-site / relocation location.
4. When the ad contains conflicting statements (for example "remote worldwide" and "US and Canada residents only"), set every applicable flag and quote each statement. Do not silently resolve the conflict or invent an explanation. Mention the conflict in reason.
5. Treat missing or omitted text as unknown, not as positive or negative evidence. If the text contains [… omitted …], do not assume that the omitted paragraphs support eligibility.
6. A missing work location is not the same as truncated text; they are separate questions.
7. Region-based eligibility is positive only when the geographic region named in the ad, in its ordinary and clear geographic meaning, includes Azerbaijan for the stated remote arrangement. A time-zone overlap or UTC offset alone is not a region. If it is debatable whether it includes Azerbaijan, answer false. Do not infer a company's internal geographic, payroll or legal-entity policy.
8. no_sponsorship_stated=true means the ad explicitly says that visa or work-permit sponsorship is unavailable. It does not, by itself, disqualify a role that independently qualifies for remote work from Azerbaijan. If the ad both offers and refuses sponsorship, set visa_support and no_sponsorship_stated both to true, quote both, and mention the conflict in reason; do the same for visa_support and work_authorization_required. A general "We do sponsor visas!" can make visa_support true, but whenever the ad qualifies it ("not for every role and every candidate", "case by case", "where possible", "may sponsor") also set visa_support_conditional and quote that qualification.
9. Quotes must be copied verbatim from the supplied ad (title, location field or ad text), must be no longer than 160 characters, must be one continuous passage and must not be assembled from separate passages or paraphrased. If no exact supporting quote exists, return value=false and quotes=[] for that flag.
10. Do not treat a statement that the company is an equal-opportunity employer, hires internationally, has a global team, or has customers or offices worldwide as evidence of remote eligibility, relocation or visa sponsorship.

Explicit country eligibility and exclusion lists
1. Interpret allowed-country and excluded-country lists independently, based on their actual meaning. An exclusion list naming other countries does not restrict Azerbaijan unless Azerbaijan, Baku, or a geographic category that includes Azerbaijan is explicitly covered by that exclusion.
2. If Azerbaijan is explicitly included in an allowed-country list for the role, treat this as positive evidence for remote eligibility, even if a separate exclusion list names other countries. Do not infer that Azerbaijan is excluded merely because it is absent from the exclusion list.
3. If Azerbaijan appears in an allowed-country list and is also explicitly excluded elsewhere in the ad, preserve both pieces of evidence, flag the conflict, and send the case for moderator review.
4. Apply these rules regardless of the language of the ad. Copy the relevant evidence verbatim; do not infer restrictions from the language, ordering, or mere presence of an exclusion list.

For each flag return {"value": true/false, "quotes": ["..."]}: up to 3 verbatim quotes that make the flag true, each one sentence or phrase of at most 160 characters; [] when false.
{flag_definitions}
reason: one or two short sentences in Azerbaijani for the moderator naming the route or the blocker, any conflict and any condition on visa sponsorship (e.g. "Yalnız Bolqarıstan daxilində remote; Azərbaycandan iş təsdiqlənmir; relocation/viza yoxdur.").

Return one JSON object with exactly these keys in this order: {key_order}.
Example of the shape only (an imaginary ad; your values and quotes must come from the ad you are given):
{example}

Reply with JSON only, matching the schema."""
_SYSTEM = (
    _SYSTEM_TEMPLATE.replace("{flag_definitions}", "\n".join(f"- {n}: {_FLAG_DEFINITIONS[n]}" for n in FLAGS))
    .replace("{key_order}", ", ".join([*FLAGS, "reason"]))
    .replace("{example}", _example_json())
)

_FLAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["value", "quotes"],
    "properties": {
        "value": {"type": "boolean"},
        "quotes": {"type": "array", "items": {"type": "string"}},
    },
}

_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [*AI_FLAGS, "reason"],
    "properties": {**{name: _FLAG_SCHEMA for name in AI_FLAGS}, "reason": {"type": "string"}},
}

# Ad text budget for the user prompt (~10k tokens). Longer ads keep the head, every
# paragraph with an exclusion / negation term (a lost "excluding Azerbaijan" must not
# turn into a yes), every paragraph about location / eligibility / benefits /
# relocation / visa, then the footer. Omitted runs are marked "[… omitted …]".
PROMPT_TEXT_MAX = 40000
OMITTED = "[… omitted …]"
_KEY_PARAGRAPH = re.compile(
    r"(?i)location|remote|hybrid|on[\s-]?site|office|relocat|visa|sponsor|work\s+permit|"
    r"right\s+to\s+work|authori[sz]|eligib|resid|based\s+in|citizen|countr|abroad|"
    r"time\s?zone|requirement|qualif|benefit|perk|we\s+offer|apply|application|"
    r"contract|\*|footnote|vary"
)
_MUST_KEEP_PARAGRAPH = re.compile(
    r"(?i)exclud|except|not\s+eligible|ineligible|unable\s+to|cannot|can['’]t|\bonly\b|\bmust\b|"
    r"not\s+(?:able|available|offer|provide|sponsor)|\bno\s+(?:visa|sponsor|relocation)|"
    r"without\s+(?:employer\s+)?sponsor"
)


# A stored description that the source itself cut ("…platform-focused...", Jooble-style
# snippets). "And much more..." at the end of a perks list is not a cut.
_SOURCE_CUT_END = re.compile(r"[\w,;:)\-]\s*(?:\.\.\.|…)\s*$")
_MORE_ELLIPSIS = re.compile(r"(?i)\b(?:and\s+)?(?:much\s+)?more\s*(?:\.\.\.|…)\s*$")


def source_text_truncated(text: str) -> bool:
    """Reliable signs that the source gave us a cut description (not our prompt limit)."""
    from worker.parsing import is_aggregator_snippet

    raw = (text or "").strip()
    if not raw:
        return False
    if is_aggregator_snippet(raw):
        return True
    return bool(_SOURCE_CUT_END.search(raw)) and not _MORE_ELLIPSIS.search(raw)


def truncation_source(text: str, limit: int = PROMPT_TEXT_MAX) -> str:
    """'prompt_limit' | 'source_snippet' | '' — why the AI does not see the whole ad."""
    raw = (text or "").strip()
    if len(raw) > limit:
        return "prompt_limit"
    if source_text_truncated(raw):
        return "source_snippet"
    return ""


def prompt_ad_text(text: str, limit: int = PROMPT_TEXT_MAX) -> tuple[str, bool]:
    """Full ad text when it fits; otherwise head + exclusion + eligibility paragraphs.

    Returns ``(text, truncated)``; ``truncated`` is passed on to the verdict so the
    code (not the AI) sets the ``text_truncated`` flag. It is also true when the source
    itself only gave a cut description (:func:`source_text_truncated`).
    """
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw, source_text_truncated(raw)
    paras = [p for p in re.split(r"\n\s*\n|\n(?=\s*[-•*]\s)", raw) if p.strip()]
    keep: set[int] = set()
    used = 0
    head_budget = limit // 4
    for i, para in enumerate(paras):  # head (role summary)
        if used + len(para) > head_budget:
            break
        keep.add(i)
        used += len(para) + 2
    for pattern in (_MUST_KEEP_PARAGRAPH, _KEY_PARAGRAPH):  # exclusions first, then eligibility
        for i, para in enumerate(paras):
            if i in keep or not pattern.search(para):
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
            out.append(OMITTED)
        out.append(paras[i])
        last = i
    if last != len(paras) - 1:
        out.append(OMITTED)
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


def is_current_ai_reason(reason: str) -> bool:
    """True for a reason written by the current prompt ("AI: 90% (market-fit-v8) ...")."""
    text = str(reason or "")
    return text.startswith(AI_REASON_PREFIX) and f"({PROMPT_VERSION})" in text[:40]


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
    source: str | None = None,
) -> dict[str, Any]:
    """Cap rule/AI % of pending scraped ads by Azerbaijan eligibility (no AI calls).

    Never changes status. ``reset_ai`` clears AI % scored by older prompts (reason
    without the current ``PROMPT_VERSION`` tag, e.g. market-fit-v6 rows) so the next
    pass re-asks the AI with the current prompt. ``limit`` (oldest id first) and
    ``source`` (exact job_sources.source_name) narrow the run for a staged rollout.
    """
    from worker.eligibility import CAP_LOCKED, RULE_MAX, summary

    sql = _PENDING_SCRAPED
    params: tuple = ()
    if source:
        sql += " AND EXISTS (SELECT 1 FROM job_sources s2 WHERE s2.job_id = jobs.id AND s2.source_name = ?)"
        params += (str(source),)
    sql += " ORDER BY id ASC"
    if limit:
        sql += " LIMIT ?"
        params += (int(limit),)
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
        if reset_ai and ai is not None and not is_current_ai_reason(reason):
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
        verdict.setdefault("eligibility_cap", int(elig["cap"]))
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
        store_fit_detail(conn, job_id, {**verdict, "confidence": confidence})
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
    prompt_limit: int = PROMPT_TEXT_MAX,
    fresh: bool = False,
) -> dict[str, Any] | None:
    """Ask AI. Returns verdict dict, or None when AI is off / fails.

    ``fresh=True`` bypasses the AI answer cache (staff re-check).

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
        title=title, company=company, place=place, text=text, source_meta=source_meta,
        prompt_limit=prompt_limit,
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
        **({"bypass_cache": True} if fresh else {}),
    )
    if not result.ok or not isinstance(result.data, dict):
        last_miss_error = (result.error or "failed")[:180]
        log.warning("market_fit ai miss: %s", last_miss_error)
        return None
    last_miss_error = ""
    _, truncated = prompt_ad_text(text, prompt_limit)
    return verdict_from_ai(
        result.data,
        ad_text=f"{title}\n{place}\n{text}",
        cached=bool(result.cached),
        truncated=truncated,
        truncation_source=truncation_source(text, prompt_limit),
    )


def build_user_prompt(
    *,
    title: str,
    company: str,
    place: str,
    text: str,
    source_meta: str = "",
    prompt_limit: int = PROMPT_TEXT_MAX,
) -> str:
    meta = " ".join(str(source_meta or "").split())[:400] or "(none)"
    body, truncated = prompt_ad_text(text, prompt_limit)
    why = truncation_source(text, prompt_limit)
    if why == "prompt_limit":
        note = (
            "Ad text: TRUNCATED — some paragraphs were omitted ([… omitted …]). Do not assume "
            "anything favourable about the missing parts."
        )
    elif truncated:
        note = (
            "Ad text: TRUNCATED — the source only provided a shortened description. Do not assume "
            "anything favourable about the missing parts."
        )
    else:
        note = "Ad text: complete as provided by the source."
    return (
        f"Title: {title}\n"
        f"Company: {company}\n"
        f"Location field (as listed by the source): {place or '(empty)'}\n"
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
    "visa_support_conditional": "viza şərtlidir: hər rol/namizəd üçün zəmanət yoxdur (zəif yol)",
    "remote_country_restricted": "remote yalnız müəyyən ölkə/regionlarda",
    "candidate_location_restricted": "namizəd müəyyən ölkədə yaşamalı/vətəndaş olmalı",
    "work_authorization_required": "konkret ölkədə hazır iş icazəsi tələb olunur",
    "temporary_abroad_only": "yalnız müvəqqəti xaricdən iş",
    "no_sponsorship_stated": "viza sponsorluğu yoxdur",
    "text_truncated": "mətn natamamdır (kəsilib və ya mənbə qısa snippet verib)",
    "work_location_unspecified": "iş yeri / remote əhatəsi yazılmayıb",
    # market-fit-v6 names, still in stored reasons and old cached answers.
    "country_restricted": "ölkə/rezidentlik məhdudiyyəti",
    "text_truncated_or_missing_location": "mətn kəsilib və ya iş yeri yazılmayıb",
}

QUOTE_MAX = 160
QUOTES_PER_FLAG = 3

# Negation / exclusion words that turn a positive-looking quote into the opposite
# ("We do not offer visa sponsorship" is not visa_support evidence).
# Shared with the eligibility pre-check (worker.az_context) so both layers agree.
_NEGATION = NEGATION
_NEGATION_OK = NEGATION_OK
_KEY_TERMS = {
    "visa_support": r"visa|sponsor|work[\s-]?permit|immigration|blue\s+card",
    "relocation": r"relocat|move|moving",
    "remote": r"remote|anywhere|worldwide|world|countr|region|location|time\s?zone|utc|gmt|"
    r"azerbaijan|azərbaycan|азербайджан|baku|bakı|баку|based|work\s+from|hire|hiring|eligible|open\s+to",
}
_NEAR = 60  # characters around a key term that a negation must fall within
# What an "except / excluding" clause may name without killing the quote: specific
# other countries. Azerbaijan, its regions, or a vague list keep the rejection.
_EXCLUSION_HITS_AZ = re.compile(
    r"(?i)azerbaijan|azərbaycan|азербайджан|baku|bakı|баку|caucasus|\bcis\b|post[\s-]soviet|central\s+asia|sanction|embargo|"
    r"certain|some|few|several|other|restricted|specific|list|where\s+we|unable|cannot"
)


# "almost anywhere", "most countries": a hedged worldwide claim (some countries are out).
_HEDGED_WORLDWIDE = re.compile(
    r"(?i)\b(?:almost|nearly|virtually|most|many|several|select(?:ed)?|certain|some)\s+"
    r"(?:anywhere|any\s+(?:country|location)|everywhere|(?:of\s+the\s+)?(?:countries|locations|world))\b"
)
# Regions whose ordinary geographic meaning clearly includes Azerbaijan. A region
# quote must name one of these (a UTC/GMT range alone never counts); "Eastern Europe",
# "Central Asia", "Europe" alone are debatable and do not count.
_REGION_INCLUDES_AZ = re.compile(
    r"(?i)azerbaijan|azərbaycan|azerbaycan|азербайджан|\bbaku\b|\bbakı\b|\bбаку\b|caucasus|\bcis\b|commonwealth\s+of\s+independent\s+states|"
    r"\bemea\b|eurasia"
)
# "based in Munich or open to relocate", "candidates worldwide may relocate": relocation
# is accepted as the alternative, so not a candidate-location restriction.
_RELOCATE_ALTERNATIVE = re.compile(
    r"(?i)\bor\s+(?:be\s+|are\s+)?(?:willing|open|able|ready|happy)\s+to\s+(?:re)?locat|"
    r"\b(?:candidates?|applicants?|you|people|talent)\b[^.;]{0,40}?\b(?:may|can|could|are\s+welcome\s+to)\s+relocat|"
    r"\b(?:willing|open|ready|happy)\s+to\s+relocate\b[^.;]{0,30}?\b(?:welcome|considered|accepted|also)\b"
)
# What each flag's quote must talk about (a quote that does not mention its subject
# cannot "directly support" the flag).
_RELEVANT = {
    "remote_az_explicit": re.compile(r"(?i)azerbaijan|azərbaycan|azerbaycan|азербайджан|\bbaku\b|\bbakı\b|\bбаку\b"),
    # bare "remote" / "100% remote" / "distributed team" is not worldwide (prompt says so too)
    "remote_worldwide": re.compile(
        r"(?i)anywhere|worldwide|world[\s-]?wide|\bworld\b|\bglobal(?:ly)?\b|any\s+(?:country|location|place)|"
        r"all\s+countries|every\s+country|location[\s-]?independent|regardless\s+of\s+(?:location|country|where)|"
        r"no\s+(?:location|geographic(?:al)?|country)\s+(?:restrictions?|limits?|requirements?)|wherever\s+you"
    ),
    "remote_region_includes_az": re.compile(
        r"(?i)remote|anywhere|work\s+from|based|location|region|countr|hir|azerbaijan|\bbaku\b|caucasus|\bcis\b|"
        r"commonwealth|\bemea\b|eurasia|europe|asia"
    ),
    # "relocat…", or a real ad's "We support you with your move to Germany"
    "relocation": re.compile(r"(?i)relocat|\b(?:your|the)\s+move\s+to\b|\bmoving\s+(?:to|from)\b"),
    "visa_support": re.compile(r"(?i)visa|sponsor|work[\s-]?permit|immigration|blue\s+card"),
    "no_sponsorship_stated": re.compile(r"(?i)visa|sponsor|work[\s-]?permit|immigration"),
    "visa_support_conditional": re.compile(
        r"(?i)visa|sponsor|work[\s-]?permit|immigration|case[\s-]by[\s-]case|every|guarantee|possible|eligib"
    ),
    "work_authorization_required": re.compile(
        r"(?i)authori[sz]|right\s+to\s+work|eligib\w*\s+to\s+work|legally|work[\s-]?permit|green\s+card|"
        r"citizen|permanent\s+resident|visa|sponsor"
    ),
    "remote_country_restricted": re.compile(
        r"(?i)remote|based|located|location|within|only|resid|countr|region|time\s?zone|utc|gmt|\bin\s+[A-Z]|"
        r"anywhere|from\s+(?:the\s+)?[A-Z]"
    ),
    "candidate_location_restricted": re.compile(
        r"(?i)resid|citizen|nationals?\b|passport|\blive[sd]?\s+in|living\s+in|lived|"
        r"currently\s+(?:located|based|living|in)|"
        r"\bopen\s+(?:for|to)\s+(?:candidates?|applicants?)\s+(?:from|in)\b|"
        r"\b(?:candidates?|applicants?)\s+from\b|"
        r"\b(?:candidates?|applicants?|talent|people|professionals|engineers|those|individuals)\s+(?:who\s+are\s+|that\s+are\s+)?"
        r"(?:based|located|living|residing)\s+(?:in|within)\b|"
        r"(?:candidates?|applicants?|you)\s+(?:must|should|need\s+to|are\s+required\s+to|will\s+need\s+to)\s+"
        r"(?:already\s+)?(?:be\s+)?(?:based|located|living|in)\b|must\s+be\s+(?:based|located)\b"
    ),
    "temporary_abroad_only": re.compile(
        r"(?i)abroad|outside|temporar|\d+\s+(?:days?|weeks?|months?)|per\s+year|a\s+year|travel|anywhere"
    ),
}
_NOT_RELEVANT = "sitat bu bayrağa aid deyil (mövzu sözü yoxdur)"
# Restrictive flags an off-topic quote may switch off. Others stay true (conservative):
# a country list in a title is hard to recognise by keywords.
_DROP_WHEN_OFF_TOPIC = ("candidate_location_restricted",)


# "Remote, worldwide (except Russia)": worldwide minus named other countries is not a
# country restriction for an Azerbaijani candidate.
_WORLDWIDE_EXCEPT = re.compile(
    r"(?i)\b(?:worldwide|anywhere|any\s+country|globally|global)\b[^.;]{0,40}?\b(?:except|excluding|exclude[sd]?)\b"
)


def _exclusion_only(quote: str) -> bool:
    m = _WORLDWIDE_EXCEPT.search(quote)
    if not m:
        return False
    tail = quote[m.end(): m.end() + _NEAR]
    return not _EXCLUSION_HITS_AZ.search(tail) and bool(re.search(r"[A-Z][a-z]", tail))


def _norm(value: str) -> str:
    return " ".join(re.sub(r"[“”\"'’‘`*_]", " ", value or "").lower().split())


def _quote_in_ad(quote: str, ad: str) -> bool:
    """Verbatim (whitespace / quote-mark insensitive) and continuous: no prefix match."""
    q = _norm(quote)
    if len(q) < 4:
        return False
    return q in _norm(ad)


def _negated(flag: str, quote: str) -> str:
    """Return the negation word when it sits near the flag's key term, else ''."""
    key = _KEY_TERMS["remote" if flag.startswith("remote_") else flag]
    text = _NEGATION_OK.sub(" ", quote)
    keys = [m.start() for m in re.finditer(f"(?i){key}", text)]
    if not keys:
        keys = [0]
    for neg in _NEGATION.finditer(text):
        word = neg.group(0).lower()
        if not any(abs(neg.start() - k) <= _NEAR for k in keys):
            continue
        if word.startswith(("exclud", "except")):
            tail = text[neg.end(): neg.end() + _NEAR]
            if not _EXCLUSION_HITS_AZ.search(tail) and re.search(r"[A-Z][a-z]", tail):
                continue  # "worldwide (except Russia)": a named other country only
        return word
    return ""


# remote_country_restricted: statements about the company, or a working-hours overlap,
# are not a restriction on where the candidate may work from.
_COMPANY_HQ = re.compile(
    r"(?i)\b(?:headquartered|headquarters|\bHQ\b)|"
    r"\b[A-Z][\w.&]*(?:\s[A-Z][\w.&]*)?[\s-]based\s+(?:company|startup|start-up|firm|business|scale-?up|team|employer)\b|"
    r"\b(?:company|startup|firm|we)\s+(?:is|are)\s+(?:headquartered|based)\s+in\b"
)
_TZ_MENTION = re.compile(r"(?i)\b(?:UTC|GMT|CET|CEST|EST|EDT|PST|PDT|ET|PT)\b|time\s?zones?|working\s+hours|overlap")
_RESTRICTION_WORDING = re.compile(
    r"(?i)\bonly\b|\bmust\b|\brequire[ds]?\b|\bresid|\bwithin\b|\beligib|\blimited\s+to\b|"
    r"\b(?:candidates?|applicants?|people|engineers|you)\s+(?:in|from|located|based|living)\b|"
    r"\b(?:located|based|living)\s+(?:in|between|within)\b|\bremote\s*(?:\(|[-–—:,]|in\b|from\b|within\b)"
)
_TZ_RANGE = re.compile(
    r"(?i)\b(?:GMT|UTC)\s*([+\-−–]\s*\d{1,2})(?::\d{2})?\s*(?:-|–|—|\.\.|to|and|through)\s*"
    r"(?:(?:GMT|UTC)\s*)?([+\-−–]\s*\d{1,2})(?::\d{2})?"
)
# visa_support_conditional: sponsorship qualified for some roles / candidates only.
_VISA_CONDITIONAL = re.compile(
    r"(?i)(?:visa|sponsor|work[\s-]?permit)[^.!?\n]{0,160}?(?:(?:\bnot\b|n['’]t\b)[^.!?\n]{0,60}\bevery\b|\bnot\s+(?:all|always|guaranteed)\b|"
    r"case[\s-]by[\s-]case|where\s+possible|\bmay\b|\bmight\b|\bsubject\s+to\b|depending\s+on|\bcertain\s+roles\b|"
    r"\bsome\s+roles\b|\beligible\s+roles\b|cannot\s+guarantee|can['’]t\s+guarantee|on\s+a\s+case)|"
    r"(?:(?:\bnot\b|n['’]t\b)[^.!?\n]{0,60}\bevery\b|case[\s-]by[\s-]case|where\s+possible|\bmay\b|cannot\s+guarantee|can['’]t\s+guarantee)"
    r"[^.!?\n]{0,80}?(?:visa|sponsor|work[\s-]?permit)|"
    r"(?:\bnot\b|n['’]t\b)[^.!?\n]{0,60}(?:visa|sponsor)[^.!?\n]{0,40}\b(?:every|all)\b"
)


# Prompt rule 10: "a globally dispersed, 100% remote company" describes the company, not
# where this role may be done from.
_COMPANY_SUBJECT = re.compile(r"(?i)\b(?:company|team|teams|employees|workforce|offices?|customers|clients|organi[sz]ation)\b")
_ROLE_SUBJECT = re.compile(
    r"(?i)\b(?:you|your|candidates?|applicants?|hire|hiring|role|position|job|work\s+from|work\s+(?:from\s+)?anywhere|opportunity\s+to\s+work|open\s+to|join\s+from)\b"
)


# remote_az_explicit: "Our client is based in Baku", "the team is international (Ukraine,
# Azerbaijan)", "the largest operator in Azerbaijan" describe the company, not where this
# role may be done from. Work wording ("remote", "on-site", "hire", "open to") keeps the quote.
def _az_company_statement(q: str) -> bool:
    return quote_az_context(q) == "company"


def _company_statement_only(q: str) -> bool:
    return bool(_COMPANY_SUBJECT.search(q)) and not _ROLE_SUBJECT.search(q)


def _tz_range_includes_az(quote: str) -> bool:
    for m in _TZ_RANGE.finditer(quote or ""):
        try:
            lo, hi = (int(re.sub(r"[−–]", "-", g).replace(" ", "")) for g in m.groups())
        except ValueError:
            continue
        if min(lo, hi) <= 4 <= max(lo, hi):
            return True
    return False


def _country_restriction_problem(q: str) -> str:
    """'' when the quote can show a remote-location restriction; else an 'alternativ' note."""
    if _COMPANY_HQ.search(q) and not _RESTRICTION_WORDING.search(_COMPANY_HQ.sub(" ", q)):
        return "alternativ: şirkətin özü haqqında (HQ), remote məhdudiyyəti deyil"
    if _TZ_MENTION.search(q):
        if _tz_range_includes_az(q):
            return "alternativ: saat qurşağı aralığı UTC+4-ü əhatə edir, məhdudiyyət deyil"
        if not _RESTRICTION_WORDING.search(q):
            return "alternativ: iş saatlarının üst-üstə düşməsi, yer məhdudiyyəti deyil"
    return ""


def conditional_visa_sentence(ad_text: str) -> str:
    """The ad's own sentence that qualifies visa sponsorship (≤160 chars), or ''."""
    for part in re.split(r"(?<=[.!?])\s+|\n+", ad_text or ""):
        part = " ".join(part.split())
        if part and _VISA_CONDITIONAL.search(part) and not _NO_SPONSOR_ONLY.search(part):
            if len(part) <= QUOTE_MAX:
                return part
            for piece in re.split(r"\s*;\s*", part):
                if len(piece) <= QUOTE_MAX and _VISA_CONDITIONAL.search(piece):
                    return piece
            return part[:QUOTE_MAX].rsplit(" ", 1)[0]
    return ""


_NO_SPONSOR_ONLY = re.compile(
    r"(?i)^(?=.*\b(?:not|no|unable|cannot|can['’]t)\b)(?!.*\b(?:every|all|case|possible|guarantee)\b).*$"
)


def _names_az_as_allowed(q: str) -> bool:
    """Azerbaijan / Baku / CIS / Caucasus named outside any negation in the quote itself
    ("Central Asia" alone is debatable and does not count)."""
    if quote_az_context(q) != "positive":
        return False
    return any(kind == "positive" and not re.match(r"(?i)central", name) for kind, name in classify_unit(q))


def check_quote(flag: str, quote: str, ad_text: str = "") -> str:
    """'' when the quote may back ``flag``; otherwise a short Azerbaijani rejection note."""
    q = " ".join(str(quote or "").split())
    if not q:
        return "sitat yoxdur"
    if len(q) > QUOTE_MAX:
        return f"sitat {QUOTE_MAX} simvoldan uzundur"
    if re.search(r"\.\.\.|…|\[\s*omitted", q):
        return "sitat ayrı hissələrdən yığılıb"
    if ad_text and not _quote_in_ad(q, ad_text):
        return "sitat elanda tapılmadı"
    if flag == "remote_worldwide" and _HEDGED_WORLDWIDE.search(q):
        return "qeyd-şərtli ifadə (almost/most …), hamı üçün deyil"
    if flag in ("remote_worldwide", "remote_region_includes_az") and _company_statement_only(q):
        return "şirkət haqqında ifadədir, bu rol üçün remote icazəsi deyil"
    if flag == "remote_az_explicit":
        context = quote_az_context(q)
        if context == "company":
            return "şirkət/müştəri/komanda haqqında ifadədir, Azərbaycandan iş icazəsi deyil"
        if context == "negative":
            return "sitatda Azərbaycan inkar/istisna kontekstindədir"
    if flag == "remote_country_restricted":
        problem = _country_restriction_problem(q)
        if problem:
            return problem
    if flag in ("remote_country_restricted", "candidate_location_restricted") and _names_az_as_allowed(q):
        # the quote itself names Azerbaijan / Baku / an AZ region as allowed ("Allowed countries:
        # Azerbaijan, Georgia"): it cannot back "limited to places that exclude Azerbaijan"
        return "alternativ: sitatda Azərbaycan icazəli yerlər arasındadır, məhdudiyyət deyil"
    relevant = _RELEVANT.get(flag)
    if relevant and not relevant.search(q):
        return _NOT_RELEVANT
    if flag in POSITIVE_FLAGS:
        word = _negated(flag, q)
        if word:
            return f"sitatda inkar/istisna var ('{word}')"
    if flag == "remote_region_includes_az" and not _REGION_INCLUDES_AZ.search(q):
        return "region Azərbaycanı aydın əhatə etmir (saat qurşağı region sayılmır)"
    if flag in ("remote_country_restricted", "candidate_location_restricted") and _exclusion_only(q):
        return "alternativ: dünya üzrə remote, yalnız başqa ölkələr istisnadır"
    if flag == "candidate_location_restricted" and _RELOCATE_ALTERNATIVE.search(q):
        return "alternativ olaraq relocation təklif olunur, məhdudiyyət deyil"
    return ""


def _sentences(quote: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\s+[•·|]\s+|\s+[-–—]\s+", quote)
    return [p.strip() for p in parts if len(p.strip()) >= 4]


def _best_quote(flag: str, quote: str, ad_text: str) -> tuple[str, str]:
    """(usable quote, problem). A too-long quote may still hold one valid sentence."""
    problem = check_quote(flag, quote, ad_text)
    if not problem.startswith("sitat 160"):
        return ("" if problem else quote), problem
    for part in _sentences(quote):
        if len(part) <= QUOTE_MAX and not check_quote(flag, part, ad_text):
            return part, ""
    clause = ""  # one long sentence: its leading clauses up to 160 characters
    for piece in quote.split(", "):
        longer = f"{clause}, {piece}" if clause else piece
        if len(longer) > QUOTE_MAX:
            break
        clause = longer
    if clause and not check_quote(flag, clause, ad_text):
        return clause, ""
    return "", problem


# The model sometimes copies the user-prompt field label with the value
# ("Location field (as listed by the source): Armenia, Azerbaijan"); the label is ours,
# not the ad's, so it is stripped before the verbatim check.
_PROMPT_LABEL = re.compile(
    r"^\s*(?:Title|Company|Location field \(as listed by the source\)|Board location field(?: \([^)]*\))?|"
    r"Source metadata \([^)]*\))\s*:\s*",
    re.I,
)


def _strip_prompt_label(quote: str) -> str:
    return _PROMPT_LABEL.sub("", quote, count=1)


def _raw_quotes(raw: dict[str, Any]) -> list[str]:
    quotes = raw.get("quotes")
    if isinstance(quotes, str):
        quotes = [quotes]
    if not isinstance(quotes, list):
        quotes = []
    legacy = raw.get("quote")  # market-fit-v6 answers
    if isinstance(legacy, str) and legacy.strip():
        quotes = [*quotes, legacy]
    out = [_strip_prompt_label(" ".join(str(q or "").split())) for q in quotes if str(q or "").strip()]
    return [q for q in out if q][:QUOTES_PER_FLAG]


_WORK_PLACE_WORDING = re.compile(
    r"(?i)\b(?:remote(?:ly)?|hybrid|on[\s-]?site|office|work(?:ing)?|hire|hiring|candidates?|applicants?|"
    r"based|located|location|anywhere|worldwide|open\s+(?:to|for)|allowed|eligible|resid\w*)\b|"
    r"дозвол|віддален|удал[её]н"
)


def _states_work_place(quote: str) -> bool:
    return bool(_WORK_PLACE_WORDING.search(quote)) or quote.count(",") >= 1


def verdict_from_ai(
    data: dict[str, Any],
    *,
    ad_text: str = "",
    cached: bool = False,
    truncated: bool | None = None,
    truncation_source: str = "",
) -> dict[str, Any]:
    """Turn the AI's yes/no flags into a verdict; the % comes from :func:`staff_percent`.

    A positive flag counts only with at least one quote that is verbatim in the ad,
    at most 160 characters, one passage, and not negated near its key term
    ("We do not offer visa sponsorship" never backs visa_support). Restrictive flags
    count even without a quote (conservative). ``truncated`` (from
    :func:`prompt_ad_text`) decides ``text_truncated``; the code value wins over the
    AI. Rejected quotes are listed for the moderator.
    """
    data = upgrade_legacy(data if isinstance(data, dict) else {})
    flags: dict[str, bool] = {}
    quotes: dict[str, list[str]] = {}
    notes: list[str] = []
    for name in FLAGS:
        raw = data.get(name) if isinstance(data.get(name), dict) else {}
        value = bool(raw.get("value")) if raw else bool(data.get(name) is True)
        candidates = _raw_quotes(raw) if raw else []
        good: list[str] = []
        problems: list[str] = []
        for quote in candidates:
            usable, problem = _best_quote(name, quote, ad_text)
            if problem:
                problems.append(problem)
                if value and (name in POSITIVE_FLAGS or problem.startswith("alternativ") or problem == _NOT_RELEVANT):
                    # off-topic quote on a kept restrictive flag: noted for the moderator
                    notes.append(f"{name}: {problem} “{quote[:120]}”")
                elif value and name not in POSITIVE_FLAGS and problem.startswith("sitat 160"):
                    good.append(quote[:QUOTE_MAX])  # restriction counts anyway; shown trimmed
            elif usable:
                good.append(usable)
        hedged = name == "remote_worldwide" and any(p.startswith("qeyd-şərtli") for p in problems)
        if name in POSITIVE_FLAGS and value and (not good or hedged):
            value = False
            good = []
            if not candidates:
                notes.append(f"{name}: sitat yoxdur")
        if name not in POSITIVE_FLAGS and value and candidates and not good and all(
            p.startswith("alternativ") or (p == _NOT_RELEVANT and name in _DROP_WHEN_OFF_TOPIC) for p in problems
        ):
            # every quote is off-topic or offers the alternative ("or willing to relocate"):
            # the quotes themselves show the restriction is not there
            value = False
        flags[name] = value
        quotes[name] = good if value else []
    # visa qualifier: only meaningful with visa_support; code adds it when the ad itself
    # qualifies sponsorship and the model missed it (conservative, never the reverse).
    if not flags["visa_support"]:
        flags["visa_support_conditional"] = False
        quotes["visa_support_conditional"] = []
    elif not flags["visa_support_conditional"]:
        found = conditional_visa_sentence(ad_text)
        if found:
            flags["visa_support_conditional"] = True
            quotes["visa_support_conditional"] = [found]
            notes.append("visa_support_conditional: kod elanda şərtli viza ifadəsi tapdı")
    # A quoted work geography (remote from AZ / worldwide / region, or a quoted country
    # restriction) means the work location IS stated: "unspecified" contradicts it.
    # A bare place token ("EMEA") is not a statement of where the work is done; a quote
    # with work wording or a list of two or more places is.
    located = [
        n for n in ("remote_az_explicit", "remote_worldwide", "remote_region_includes_az", "remote_country_restricted")
        if flags[n] and any(_states_work_place(q) for q in quotes[n])
    ]
    if flags["work_location_unspecified"] and located:
        flags["work_location_unspecified"] = False
        quotes["work_location_unspecified"] = []
        notes.append(f"work_location_unspecified: kod ləğv etdi, iş yeri sitatla göstərilib ({located[0]})")
    # text_truncated: the code value (prompt cut / source snippet) is authoritative;
    # the AI answer is only a hint, kept separately.
    ai_hint = flags["text_truncated"]
    code_cut = None if truncated is None else bool(truncated)
    flags["text_truncated"] = ai_hint if code_cut is None else code_cut
    quotes["text_truncated"] = []
    soft_hint = bool(ai_hint and code_cut is False)
    score, route = staff_percent({**flags, TRUNCATION_HINT: soft_hint})
    if soft_hint:
        notes.append("text_truncated: AI mətnin natamam olduğundan şübhələnir, kod təsdiqləmir (84-ə qədər)")
    conflict_keys = conflicts(flags)
    conflict = bool(conflict_keys)
    # market-fit-v10 decision: list semantics are the AI's job (prompt section "Explicit
    # country eligibility and exclusion lists"). The code never drops a quoted restriction
    # on its own; when Azerbaijan is allowed and the restriction quotes do not even mention
    # Azerbaijan / Baku / a region that includes it, it only tells the moderator so.
    if "remote_vs_restriction" in conflict_keys and flags["remote_az_explicit"]:
        # verbatim restriction quotes, also ones kept only conservatively (e.g. non-English
        # wording the relevance check cannot read)
        r_quotes = [
            q
            for name in ("remote_country_restricted", "candidate_location_restricted")
            if flags[name] and isinstance(data.get(name), dict)
            for q in _raw_quotes(data[name])
            if not ad_text or _quote_in_ad(q, ad_text)
        ]
        if r_quotes and not any(_REGION_INCLUDES_AZ.search(q) for q in r_quotes):
            notes.append(
                "remote_country_restricted: məhdudiyyət sitatlarında Azərbaycan çəkilmir — siyahı başqa ölkələri "
                "istisna edə bilər; moderator yoxlasın (84)"
            )
    true_parts = [
        f"{name} ({_FLAG_AZ[name]})" + "".join(f" “{q}”" for q in quotes[name])
        for name in FLAGS
        if flags[name]
    ]
    vnote = visa_note(flags, route)
    reason_az = " ".join(str(data.get("reason") or "").split())[:240]
    reason = (
        f"{AI_REASON_PREFIX}{score}% ({PROMPT_VERSION}) AI-nın bəli/xeyr yoxlamalarından hesablanıb · "
        + (
            "ziddiyyətli sübut (moderator baxsın): " + "; ".join(CONFLICTS_AZ[k] for k in conflict_keys) + " · "
            if conflict
            else ""
        )
        + ("; ".join(true_parts) if true_parts else "heç bir bayraq doğru deyil")
        + (f" · {VISA_NOTES_AZ[vnote]}" if vnote else "")
        + (f" · yoxlamada rədd edilən sitatlar: {'; '.join(notes)}" if notes else "")
        + (f" · {reason_az}" if reason_az else "")
    )
    suitable = is_suitable(route)
    visa_ok = bool(visa_strength(flags))
    return {
        "suitable": suitable,
        "unclear": route == "no_evidence",
        "remote": route in ("remote_az_explicit", "remote_worldwide", "remote_region_includes_az"),
        "relocation": flags["relocation"],
        "visa_support": visa_ok,
        "flags": flags,
        "quotes": quotes,
        "validation_notes": notes,
        "conflict": conflict,
        "conflicts": conflict_keys,
        "visa_strength": visa_strength(flags),
        "visa_note": vnote,
        "text_truncated_code": code_cut,
        "text_truncated_ai_hint": bool(ai_hint),
        "text_truncated_source": truncation_source,
        "reason_az": reason_az,
        "ai_score": score,
        "route": route,
        "reason": reason[:800],
        "confidence": score,
        "cached": cached,
    }


def fit_detail(verdict: dict[str, Any]) -> dict[str, Any]:
    """Structured AI result for the Moderasiya popover (stored as JSON in market_fit_detail)."""
    flags = verdict.get("flags") or {}
    quotes = verdict.get("quotes") or {}
    return {
        "prompt_version": PROMPT_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "score": int(verdict.get("confidence") or 0),
        "ai_score": int(verdict.get("ai_score", verdict.get("confidence")) or 0),
        "route": str(verdict.get("route") or ""),
        "cap": verdict.get("eligibility_cap"),
        "eligibility": str(verdict.get("eligibility") or ""),
        "hard_reject": bool(verdict.get("hard_reject")),
        "conflict": bool(verdict.get("conflict")),
        "conflicts": [
            {"key": k, "label": CONFLICTS_AZ.get(k, k)} for k in (verdict.get("conflicts") or []) if isinstance(k, str)
        ],
        "visa_strength": str(verdict.get("visa_strength") or ""),
        "visa_note": {
            "key": str(verdict.get("visa_note") or ""),
            "label": VISA_NOTES_AZ.get(str(verdict.get("visa_note") or ""), ""),
        },
        "text_truncated": {
            "code": verdict.get("text_truncated_code"),
            "ai_hint": bool(verdict.get("text_truncated_ai_hint")),
            "source": str(verdict.get("text_truncated_source") or ""),
        },
        "flags": [
            {"name": name, "label": _FLAG_AZ.get(name, name), "quotes": list(quotes.get(name) or [])[:QUOTES_PER_FLAG]}
            for name in FLAGS
            if flags.get(name)
        ],
        "notes": [str(n)[:240] for n in (verdict.get("validation_notes") or [])][:8],
        "reason_az": str(verdict.get("reason_az") or "")[:300],
    }


def store_fit_detail(conn, job_id: int, verdict: dict[str, Any] | None) -> None:
    """Write the popover JSON next to ai_confidence (no-op when the column is missing)."""
    if conn is None or not verdict:
        return
    import json

    try:
        conn.execute(
            "UPDATE jobs SET market_fit_detail = ? WHERE id = ?",
            (json.dumps(fit_detail(verdict), ensure_ascii=False)[:6000], int(job_id)),
        )
    except Exception as exc:  # older DB without the column: keep the AI write
        log.warning("market_fit_detail not stored for job %s: %s", job_id, exc)


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
    prompt_limit: int = PROMPT_TEXT_MAX,
    fresh: bool = False,
) -> dict[str, Any] | None:
    """Eligibility gate + AI flags + cap: the one path for staff rechecks / fills.

    ``fresh=True`` asks the AI again instead of reusing a cached answer.

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
            "route": "eligibility_reject",
            "eligibility_cap": int(elig["cap"]),
            "eligibility": summary(elig),
            "ai_score": None,
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
        prompt_limit=prompt_limit,
        **({"fresh": True} if fresh else {}),
    )
    if verdict is None:
        return None
    cap = int(elig["cap"])
    verdict["eligibility_cap"] = cap
    verdict["confidence"] = min(int(verdict.get("confidence") or 0), cap)
    if cap < 100:
        verdict["eligibility"] = summary(elig)
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
