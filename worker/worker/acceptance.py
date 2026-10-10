"""Acceptance rules for a normalized ad. Shared by the hourly crawler (runner)
and the LinkedIn extension import (API), so both apply the same checks."""

from __future__ import annotations

from worker.market_fit import (
    clarify_market_fit,
    has_clear_market_signal,
    is_rejected,
    mark_rejected,
)
from worker.techstack import (
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

    title = str(item.get("title") or "")
    place = str(item.get("city") or "")
    text = str(item.get("text") or "")
    company = str(item.get("company") or "")
    url = str(item.get("source_url") or "").strip()
    conn = getattr(getattr(connector, "store", None), "conn", None)

    if url and is_rejected(conn, url):
        return None

    pre_remote = item.get("remote")
    pre_relocation = item.get("relocation")
    remote_default = bool(getattr(connector, "remote_default", False))
    relocation_default = bool(getattr(connector, "relocation_default", False))
    clear = has_clear_market_signal(
        title,
        place,
        text,
        pre_remote=pre_remote if isinstance(pre_remote, bool) else None,
        pre_relocation=pre_relocation if isinstance(pre_relocation, bool) else None,
        remote_default=remote_default,
        relocation_default=relocation_default,
    )

    enrich(item, remote_default=remote_default, relocation_default=relocation_default)

    # Tel Aviv / hybrid office etc.: drop before AI (no remote/reloc keywords).
    if foreign_office_without_offer(title, place, text):
        if url:
            mark_rejected(conn, url, "foreign_office", via_ai=False)
        return None

    if not clear:
        verdict = clarify_market_fit(
            title=title, company=company, place=place, text=text, conn=conn
        )
        if not verdict or not verdict.get("suitable"):
            if url and verdict is not None and not verdict.get("suitable"):
                mark_rejected(
                    conn,
                    url,
                    str(verdict.get("reason") or "unsuitable"),
                    via_ai=True,
                )
            return None
        item["remote"] = bool(verdict.get("remote"))
        item["relocation"] = bool(verdict.get("relocation"))

    if getattr(connector, "require_remote_or_relocation", False):
        if not (item.get("remote") or item.get("relocation")):
            return None

    if not az_market_relevant(
        title,
        place,
        text,
        remote=bool(item.get("remote")),
        relocation=bool(item.get("relocation")),
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
