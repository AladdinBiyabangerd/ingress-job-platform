"""Niche tech job boards that publish an open RSS feed (robots.txt allows it).

CryptocurrencyJobs.co (web3), JsJobbs (JavaScript) and AI Dev Board (AI/ML). Only the
feed and, where the feed text is short, the public posting page (schema.org
JobPosting) are read. Region locks and relocation are decided by the shared rules.
"""

from __future__ import annotations

import re
from html import unescape

from worker.connectors.feed import FeedConnector, first, read_rss, text_from_html
from worker.parsing import clean, norm_key

_OPEN_PLACE = re.compile(r"(?i)\b(?:worldwide|anywhere|global|remote)\b")


def _split_at(full: str) -> tuple[str, str]:
    """"Role at Company" -> (role, company); the company follows the LAST " at "."""
    head, sep, tail = full.rpartition(" at ")
    if sep and head.strip() and tail.strip():
        return head.strip(), tail.strip()
    return full, ""


def known_company_title(store: object, title: str, company: str) -> bool:
    """True when a job with the same title and company is already stored (any place).
    Used by aggregator boards so an ad that an employer's own ATS board already gave us
    is not read again."""
    conn = getattr(store, "conn", None)
    if conn is None or not title or not company:
        return False
    prefix = norm_key(title, company, "")
    try:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE norm_key >= ? AND norm_key < ? LIMIT 1",
            (prefix, prefix + "\uffff"),
        ).fetchone()
    except Exception:
        return False
    return row is not None


class CryptocurrencyJobsConnector(FeedConnector):
    """https://cryptocurrencyjobs.co/index.xml — web3 jobs; the posting page has JSON-LD."""

    name = "CryptocurrencyJobs"
    entry_url = "https://cryptocurrencyjobs.co/index.xml"
    require_remote_or_relocation = True
    min_interval_hours = 6
    detail = True
    candidates = 30
    credit_note = "CryptocurrencyJobs.co public RSS feed and job pages."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = unescape(clean(first(it.get("title"))))
            link = first(it.get("link"))
            if not full or not link:
                continue
            title, company = _split_at(full)
            out.append({
                "title": title,
                "company": company,
                "city": "",
                "text": text_from_html(first(it.get("description"))),
                "source_url": link,
                "posted_at": first(it.get("pubdate") or it.get("published") or it.get("updated")),
                "external_id": link.rstrip("/").rsplit("/", 1)[-1],
                "_stamp": first(it.get("pubdate")),
            })
        return out


class JsJobbsConnector(FeedConnector):
    """https://jsjobbs.com/rss — JavaScript/TypeScript jobs, full text in the feed."""

    name = "JsJobbs"
    entry_url = "https://jsjobbs.com/rss"
    require_remote_or_relocation = True
    min_interval_hours = 6
    candidates = 40
    credit_note = "JsJobbs public RSS feed. The link opens the listing on jsjobbs.com."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            title = clean(first(it.get("title")))
            link = first(it.get("link"))
            if not title or not link:
                continue
            place = clean(first(it.get("category")))
            remote = bool(re.search(r"(?i)\bremote\b", place))
            out.append({
                "title": title,
                "company": clean(first(it.get("author"))),
                "city": place,
                "text": text_from_html(first(it.get("description"))),
                "source_url": link,
                "posted_at": first(it.get("pubdate") or it.get("published") or it.get("updated")),
                "external_id": clean(first(it.get("guid"))),
                "remote": True if remote else None,
            })
        return out


class AiDevBoardConnector(FeedConnector):
    """https://aidevboard.com/feed.xml — AI/ML jobs. The board re-lists employers' ATS postings,
    so a title + company we already hold from another source is skipped. Only rows marked
    Remote are read (the feed gives "Title — Place · type · Workplace · pay")."""

    name = "AI Dev Board"
    entry_url = "https://aidevboard.com/feed.xml"
    require_remote_or_relocation = True
    min_interval_hours = 6
    detail = True
    candidates = 30
    credit_note = "AI Dev Board public RSS feed and job pages."

    _SALARY = re.compile(r"\s*\((?:[^()]*\d[^()]*)\)\s*$")

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = self._SALARY.sub("", unescape(clean(first(it.get("title")))))
            link = first(it.get("link"))
            if not full or not link:
                continue
            title, company = _split_at(full)
            desc = clean(first(it.get("description")))
            parts = [p.strip() for p in desc.split("·")]
            if not any(p.lower() == "remote" for p in parts):
                continue
            if known_company_title(self.store, title, company):
                continue
            head = parts[0].rpartition(" — ")[2].strip() if parts else ""
            city = "Remote" if not head or _OPEN_PLACE.search(head) else f"Remote ({head})"
            tags = [t.strip() for t in first(it.get("category")).split(",") if t.strip()]
            out.append({
                "title": title,
                "company": company,
                "city": city,
                "text": "",
                "source_url": link,
                "posted_at": first(it.get("pubdate") or it.get("published") or it.get("updated")),
                "external_id": link.rstrip("/").rsplit("-", 1)[-1],
                "tags": tags,
                "remote": True,
                "_stamp": first(it.get("pubdate")),
            })
        return out
