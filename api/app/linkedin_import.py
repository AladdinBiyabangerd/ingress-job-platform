"""Batch import of ads the user viewed on LinkedIn (Chrome extension).

The extension captures pages as-is. Nothing is judged here: every ad goes
through the same acceptance rules and the same store upsert as the hourly
crawler (worker.acceptance.finish_item, worker.db.Store.upsert), so status,
tech/market/geo checks and rejected-URL memory behave exactly like crawled ads.
Only a title and a URL/LinkedIn id are required to try.
"""

from __future__ import annotations

import sys
from pathlib import Path

SOURCE_NAME = "linkedin-extension"


class WorkerUnavailable(RuntimeError):
    pass


def _worker():
    try:
        import worker.acceptance  # noqa: F401
    except ImportError:
        repo_worker = Path(__file__).resolve().parents[2] / "worker"
        if repo_worker.is_dir() and str(repo_worker) not in sys.path:
            sys.path.insert(0, str(repo_worker))
        try:
            import worker.acceptance  # noqa: F401
        except ImportError as exc:
            raise WorkerUnavailable(str(exc)) from exc
    from worker.acceptance import finish_item
    from worker.db import Store
    from worker.market_fit import is_rejected, mark_rejected

    return finish_item, Store, is_rejected, mark_rejected


class _Connector:
    """Stand-in for a crawler connector: same attributes finish_item reads."""

    name = SOURCE_NAME
    remote_default = False
    relocation_default = False
    require_remote_or_relocation = False
    credit_note = ""

    def __init__(self, store) -> None:
        self.store = store


def import_jobs(items: list[dict]) -> dict:
    finish_item, Store, is_rejected, mark_rejected = _worker()
    from app.sqlite_jobs import DB_PATH

    created: list[dict] = []
    duplicates: list[dict] = []
    rejected: list[dict] = []
    errors: list[dict] = []
    store = Store(Path(DB_PATH))
    try:
        connector = _Connector(store)
        for raw in items:
            lid = str(raw.get("linkedin_id") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not lid or not title:
                errors.append({"linkedin_id": lid, "error": "title/id missing"})
                continue
            try:
                li_url = f"https://www.linkedin.com/jobs/view/{lid}/"
                apply_url = str(raw.get("apply_url") or "").strip()
                source_url = apply_url if apply_url.startswith(("http://", "https://")) else li_url
                dup = store.conn.execute(
                    "SELECT job_id FROM job_sources WHERE source_url IN (?, ?) "
                    "OR (source_name = ? AND external_id = ?)",
                    (li_url, source_url, SOURCE_NAME, lid),
                ).fetchone()
                if dup is not None:
                    duplicates.append({"linkedin_id": lid, "job_id": int(dup[0])})
                    continue
                if is_rejected(store.conn, li_url):
                    rejected.append({"linkedin_id": lid, "reason": "previously_rejected"})
                    continue
                note = " | ".join(
                    p for p in (f"LinkedIn {li_url}", str(raw.get("posted") or "").strip(),
                                str(raw.get("employment_type") or "").strip()) if p
                )
                item = {
                    "title": title,
                    "company": str(raw.get("company") or "").strip(),
                    "city": str(raw.get("location") or "").strip(),
                    "text": str(raw.get("description") or "").strip(),
                    "source_url": source_url,
                    "external_id": lid,
                    "credit_note": note[:300],
                }
                if raw.get("remote"):
                    item["remote"] = True
                accepted = finish_item(connector, item)
                store.conn.commit()
                if not accepted:
                    # Always remember the LinkedIn view URL so ops can attribute rejects.
                    mark_rejected(store.conn, li_url, "rules")
                    rejected.append({"linkedin_id": lid, "reason": "rules"})
                    continue
                accepted["source_name"] = SOURCE_NAME
                kind = store.upsert(accepted)
                if kind == "created":
                    created.append({"linkedin_id": lid})
                else:
                    duplicates.append({"linkedin_id": lid, "job_id": None})
            except Exception as exc:  # one bad row must not stop the batch
                try:
                    store.conn.rollback()
                except Exception:
                    pass
                errors.append({"linkedin_id": lid, "error": str(exc)[:120]})
    finally:
        store.close()
    return {
        "created": len(created),
        "duplicates": len(duplicates),
        "rejected": len(rejected),
        "errors": len(errors),
        "created_items": created,
        "duplicate_items": duplicates,
        "rejected_items": rejected,
        "error_items": errors,
    }
