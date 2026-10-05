"""Regional and niche tech sources with official open APIs or RSS feeds.

- JobTech / Platsbanken (Sweden): Arbetsförmedlingen's open JobSearch API,
  filtered to the Data/IT occupation field. Open data.
- Get on Board (Latin America): documented public API, tech categories only.
- Hasjob (India): public Atom feed.
- WordPress Jobs (jobs.wordpress.net) and Remote Python: public RSS feeds.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from worker.connectors.feed import FeedConnector, first, read_rss, text_from_html
from worker.http import NotFound, SourceFailed
from worker.parsing import clean

_EN_WORDS = re.compile(r"\b(the|and|you|with|our|we|will|experience|team|for)\b", re.IGNORECASE)


def _english(text: str) -> bool:
    sample = text[:1500]
    return len(_EN_WORDS.findall(sample)) >= 12


# Platsbanken's Swedish occupation labels (SSYK) in the Data/IT field, as the
# English words the category rules understand. Order matters: first match wins.
_OCCUPATION_EN = (
    ("testare", "Software testing"), ("testledare", "Software testing"),
    ("support", "IT support"), ("säkerhet", "IT security"),
    ("databas", "Network and systems administration"),
    ("nätverk", "Network and systems administration"),
    ("systemadministrat", "Network and systems administration"),
    ("systemtekniker", "Network and systems administration"),
    ("drift", "IT operations"), ("arkitekt", "IT architecture"),
    ("systemanalytiker", "IT architecture"), ("spel", "Game development"),
    ("webb", "Web development"), ("analytiker", "Data analysis"),
    ("data scientist", "Data analysis"), ("ux", "UX design"), ("användbarhet", "UX design"),
    ("mjukvaru", "Software development"), ("systemutvecklare", "Software development"),
    ("programmerare", "Software development"), ("utvecklare", "Software development"),
    ("chef", "IT management"),
)


def _occupation_en(label: str) -> str:
    low = label.lower()
    for key, english in _OCCUPATION_EN:
        if key in low:
            return english
    return ""


class JobTechSwedenConnector(FeedConnector):
    """https://jobsearch.api.jobtechdev.se — Platsbanken ads, Data/IT field (apaJ_2ja_LuF)."""

    name = "JobTech Platsbanken (Sweden)"
    entry_url = "https://jobsearch.api.jobtechdev.se/search"
    field = "apaJ_2ja_LuF"
    credit_note = (
        "Arbetsförmedlingen JobTech JobSearch API (Platsbanken), open data. The link opens "
        "the ad on arbetsformedlingen.se."
    )

    def feed_items(self) -> list[dict]:
        payload = self.client.get_json(
            f"{self.entry_url}?occupation-field={self.field}&limit=100&sort=pubdate-desc")
        hits = payload.get("hits") if isinstance(payload, dict) else None
        if not isinstance(hits, list):
            raise SourceFailed("jobtech payload had no hits list")
        english: list[dict] = []
        other: list[dict] = []
        for hit in hits:
            if not isinstance(hit, dict) or hit.get("removed"):
                continue
            addr = hit.get("workplace_address") or {}
            town = clean(addr.get("municipality") or addr.get("city") or addr.get("region"))
            place = ", ".join(x for x in (town, clean(addr.get("country")) or "Sverige") if x)
            text = str((hit.get("description") or {}).get("text") or "").strip()
            swedish = [clean((hit.get(k) or {}).get("label")) for k in ("occupation", "occupation_group")]
            labels = [_occupation_en(x) for x in swedish if x]
            # The occupation field is Data/IT for every hit (the query filter);
            # "IT" keeps that verdict without reading "Data" as Data/ML.
            labels = list(dict.fromkeys(x for x in labels if x)) + ["IT"]
            model = clean((hit.get("workplace_model") or {}).get("label")).lower()
            item = {
                "title": hit.get("headline"),
                "company": clean((hit.get("employer") or {}).get("name") or (hit.get("employer") or {}).get("workplace")),
                "city": place,
                "text": text,
                "source_url": hit.get("webpage_url"),
                "external_id": f"jobtech-{hit.get('id')}",
                "category": labels,
                "remote": True if ("distans" in model or "remote" in model) else None,
            }
            (english if _english(text) else other).append(item)
        # English-language ads first: they are the ones open to people relocating.
        return english + other


class GetOnBoardConnector(FeedConnector):
    """https://www.getonbrd.com/api-doc — public API, tech categories, LatAm + remote."""

    name = "Get on Board (Latin America)"
    entry_url = "https://www.getonbrd.com/api/v0/categories/programming/jobs"
    categories = ("programming", "sysadmin-devops-qa", "data-science-analytics", "mobile-developer",
                  "cybersecurity")
    credit_note = "Get on Board public API. Link back to getonbrd.com and name Get on Board as the source."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        read = 0
        expand = quote('["company"]')
        for cat in self.categories:
            url = f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs?per_page=40&page=1&expand={expand}"
            try:
                payload = self.client.get_json(url)
            except NotFound:
                continue
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                continue
            read += 1
            for row in rows:
                attrs = (row or {}).get("attributes") or {}
                if not attrs.get("title"):
                    continue
                company = (((attrs.get("company") or {}).get("data") or {}).get("attributes") or {}).get("name")
                countries = [clean(c) for c in attrs.get("countries") or [] if clean(c)]
                modality = str(attrs.get("remote_modality") or "").lower()
                remote = bool(attrs.get("remote")) or modality in {"fully_remote", "remote_local", "remote"}
                place = ", ".join(countries[:3])
                if remote:
                    place = "Remote" + (f" ({place})" if place else "")
                parts = []
                for key in ("description", "functions", "desirable", "benefits", "projects"):
                    head = clean(attrs.get(f"{key}_headline"))
                    body = text_from_html(attrs.get(key))
                    if body:
                        parts.append(f"{head}\n{body}" if head else body)
                out.append({
                    "title": attrs.get("title"),
                    "company": company,
                    "city": place,
                    "text": "\n\n".join(parts),
                    "source_url": ((row or {}).get("links") or {}).get("public_url"),
                    "external_id": f"getonbrd-{row.get('id')}",
                    "category": attrs.get("category_name"),
                    "remote": True if remote else None,
                    "_ts": int(attrs.get("published_at") or 0),
                })
        if not read:
            raise SourceFailed("get on board categories unreadable")
        out.sort(key=lambda r: r.pop("_ts", 0), reverse=True)
        return out


class HasjobConnector(FeedConnector):
    """https://hasjob.co/feed — HasGeek's job board (India), Atom feed of recent posts."""

    name = "Hasjob (India)"
    entry_url = "https://hasjob.co/feed"
    credit_note = "Hasjob public Atom feed. The link opens the post on hasjob.co."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for item in read_rss(self.client, self.entry_url):
            html = first(item.get("content") or item.get("summary"))
            match = re.search(r"<strong>\s*(?:<a[^>]*>)?(.*?)(?:</a>)?\s*</strong>", html, re.S)
            company = clean(re.sub(r"<[^>]+>", " ", match.group(1))) if match else ""
            out.append({
                "title": first(item.get("title")),
                "company": company,
                "city": clean(first(item.get("location"))),
                "text": text_from_html(html),
                "source_url": first(item.get("link") or item.get("id")),
                "external_id": first(item.get("id")),
            })
        return out


class WordPressJobsConnector(FeedConnector):
    """https://jobs.wordpress.net/feed/ — the WordPress community job board (RSS)."""

    name = "WordPress Jobs"
    entry_url = "https://jobs.wordpress.net/feed/"
    detail = True
    credit_note = "jobs.wordpress.net public RSS feed. The link opens the post on jobs.wordpress.net."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for item in read_rss(self.client, self.entry_url):
            title = clean(first(item.get("title")))
            company = ""
            match = re.search(r"\s[—–-]\s([^—–-]{2,60})$", title)
            if match and not re.search(r"(?i)remote|time|contract", match.group(1)):
                company = clean(match.group(1))
            out.append({
                "title": title,
                "company": company,
                "city": "",
                "text": text_from_html(first(item.get("encoded") or item.get("description"))),
                "source_url": first(item.get("link")),
                "external_id": first(item.get("guid")),
                "tags": ["WordPress", "PHP"],
            })
        return out


class RemotePythonConnector(FeedConnector):
    """https://www.remotepython.com/latest/jobs/feed/ — remote Python roles (RSS)."""

    name = "Remote Python"
    entry_url = "https://www.remotepython.com/latest/jobs/feed/"
    remote_default = True
    credit_note = "Remote Python public RSS feed. The link opens the post on remotepython.com."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for item in read_rss(self.client, self.entry_url):
            title = clean(first(item.get("title")))
            company = ""
            if " at " in title:
                title, company = (clean(x) for x in title.rsplit(" at ", 1))
            out.append({
                "title": title,
                "company": company,
                "city": "Remote",
                "text": text_from_html(first(item.get("description"))),
                "source_url": first(item.get("link")),
                "external_id": first(item.get("guid")),
                "tags": ["Python"],
                "remote": True,
            })
        return out
