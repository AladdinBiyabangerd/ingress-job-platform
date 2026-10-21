"""Acceptance rules for a normalized ad. Shared by the hourly crawler (runner)
and the LinkedIn extension import (API), so both apply the same checks."""

from __future__ import annotations

from worker.eligibility import assess as assess_eligibility
from worker.eligibility import cap_score, is_hard_reject
from worker.eligibility import summary as eligibility_summary
from worker.market_fit import (
    AI_REASON_PREFIX,
    RULE_REASON_PREFIX,
    clarify_market_fit,
    is_rejected,
    mark_rejected,
    rule_fit_confidence,
    source_meta_line,
)
from worker.parsing import is_aggregator_snippet
from worker.techstack import (
    apply_relocation_override,
    az_market_relevant,
    enrich,
    foreign_office_without_offer,
    is_tech_job,
)


def finish_item(connector, item: dict | None) -> dict | None:
    """Tech roles only. Adds tech_stack / remote / relocation. Keeps AZ-market
    remote or relocation; unclear ads go through AI; rejects are remembered."""
    if not item:
        return None
    if not is_tech_job(str(item.get("title") or ""), item.get("category"), item.get("tags")):
        return None
    # Reject-only guard: a listing without an employer name is never published.
    if not str(item.get("company") or "").strip():
        return None

    title = str(item.get("title") or "")
    place = str(item.get("city") or "")
    text = str(item.get("text") or "")
    company = str(item.get("company") or "")
    url = str(item.get("source_url") or "").strip()
    conn = getattr(getattr(connector, "store", None), "conn", None)

    if url and is_rejected(conn, url):
        return None

    # Jooble (and similar) only ship search snippets — never a full JD.
    if is_aggregator_snippet(text):
        if url:
            mark_rejected(conn, url, "thin_description", via_ai=False)
        return None

    pre_remote = item.get("remote")
    pre_relocation = item.get("relocation")
    remote_default = bool(getattr(connector, "remote_default", False))
    relocation_default = bool(getattr(connector, "relocation_default", False))
    rule_fit = rule_fit_confidence(
        title,
        place,
        text,
        pre_remote=pre_remote if isinstance(pre_remote, bool) else None,
        pre_relocation=pre_relocation if isinstance(pre_relocation, bool) else None,
        remote_default=remote_default,
        relocation_default=relocation_default,
    )

    # Azerbaijan eligibility from the ad text + source location (before any AI).
    countries = [str(c) for c in (item.get("geo_countries") or []) if str(c or "").strip()]
    elig = assess_eligibility(
        title,
        place,
        text,
        countries=countries or None,
        source_remote=pre_remote if isinstance(pre_remote, bool) else None,
        source_url=url,
        source=str(getattr(connector, "name", "") or ""),
    )
    if is_hard_reject(elig):
        if url:
            mark_rejected(conn, url, ("eligibility: " + eligibility_summary(elig))[:300], via_ai=False)
        return None

    enrich(item, remote_default=remote_default, relocation_default=relocation_default)

    # Tel Aviv / hybrid office etc.: drop before AI (no remote/reloc keywords).
    if foreign_office_without_offer(title, place, text):
        if url:
            mark_rejected(conn, url, "foreign_office", via_ai=False)
        return None

    if rule_fit:
        item["rule_confidence"] = cap_score(int(rule_fit["confidence"]), elig, rule=True)
        item["ai_confidence"] = None
        item["market_fit_reason"] = (
            RULE_REASON_PREFIX
            + eligibility_summary(elig)
            + f" · qayda siqnalı: {rule_fit.get('reason') or 'market signal'}"
        )[:800]
    else:
        verdict = clarify_market_fit(
            title=title,
            company=company,
            place=place,
            text=text,
            conn=conn,
            source_meta=source_meta_line(
                remote=pre_remote,
                relocation=pre_relocation,
                place=place,
                countries=countries,
                source=str(getattr(connector, "name", "") or ""),
            ),
        )
        keep = bool(verdict) and bool(verdict.get("suitable") or verdict.get("unclear"))
        if not keep:
            if url and verdict is not None:
                mark_rejected(
                    conn,
                    url,
                    str(verdict.get("reason") or "unsuitable"),
                    via_ai=True,
                )
            return None
        if verdict.get("suitable"):
            item["remote"] = bool(verdict.get("remote"))
            item["relocation"] = bool(verdict.get("relocation"))
        # unclear (no evidence, 40%): keep source flags, stay pending for staff.
        item["rule_confidence"] = None
        item["ai_confidence"] = cap_score(int(verdict.get("confidence") or 0), elig, rule=False)
        reason = str(verdict.get("reason") or "")
        if not reason.startswith(AI_REASON_PREFIX):
            reason = AI_REASON_PREFIX + reason
        item["market_fit_reason"] = reason[:800]

    if getattr(connector, "require_remote_or_relocation", False):
        if not (item.get("remote") or item.get("relocation")):
            return None

    # Region/country-locked remote + relocation/visa offer (text or structured
    # flag) is accepted as remote=0, relocation=1.
    source_name = str(getattr(connector, "name", "") or "")
    structured_reloc = pre_relocation is True or relocation_default
    apply_relocation_override(item, source_name, structured_relocation=structured_reloc)

    if not az_market_relevant(
        title,
        place,
        text,
        remote=bool(item.get("remote")),
        relocation=bool(item.get("relocation")),
        source=source_name,
        structured_relocation=structured_reloc,
    ):
        if url:
            mark_rejected(conn, url, "foreign_locked_remote", via_ai=False)
        return None

    if not (item.get("remote") or item.get("relocation")):
        return None

    credit = getattr(connector, "credit_note", "")
    if credit and not item.get("credit_note"):
        item["credit_note"] = credit
    return item
