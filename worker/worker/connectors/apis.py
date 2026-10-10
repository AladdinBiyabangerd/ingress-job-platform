"""Official public JSON APIs. No key, no HTML scraping of the list pages.

Each class reads only the documented endpoint, keeps the source's own listing
URL, and honours the polling advice the source publishes.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from worker.connectors.feed import FeedConnector, text_from_html
from worker.http import SourceFailed
from worker.parsing import clean


class ArbeitnowConnector(FeedConnector):
    """https://www.arbeitnow.com/blog/job-board-api — visa_sponsorship=true and remote."""

    name = "Arbeitnow"
    entry_url = "https://www.arbeitnow.com/api/job-board-api"
    require_remote_or_relocation = True
    credit_note = "Arbeitnow free Job Board API. Link back to arbeitnow.com and name Arbeitnow as the source."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for url, visa in ((self.entry_url + "?visa_sponsorship=true", True), (self.entry_url, False)):
            payload = self.client.get_json(url)
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise SourceFailed("arbeitnow payload had no data list")
            for job in rows:
                if not isinstance(job, dict):
                    continue
                remote = bool(job.get("remote"))
                if not visa and not remote:
                    continue
                out.append({
                    "title": job.get("title"),
                    "company": job.get("company_name"),
                    "city": ("Remote" if remote and not job.get("location") else job.get("location")),
                    "text": text_from_html(job.get("description")),
                    "source_url": job.get("url"),
                    "external_id": job.get("slug"),
                    "tags": list(job.get("tags") or []),
                    "category": list(job.get("tags") or []),
                    "remote": remote,
                    "relocation": True if visa else None,
                })
        return out


class HimalayasConnector(FeedConnector):
    """https://himalayas.app/docs/remote-jobs-api — data refreshes once a day."""

    name = "Himalayas"
    entry_url = "https://himalayas.app/jobs/api/search"
    remote_default = True
    min_interval_hours = 24
    credit_note = (
        "Himalayas Remote Jobs API. Show a visible link back to himalayas.app and say the "
        "data is sourced from Himalayas."
    )
    queries = ("software", "developer", "devops", "data engineer")

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for q in self.queries:
            payload = self.client.get_json(f"{self.entry_url}?q={quote(q)}&sort=recent")
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(jobs, list):
                raise SourceFailed("himalayas payload had no jobs list")
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                places = []
                for loc in job.get("locationRestrictions") or []:
                    name = loc.get("name") if isinstance(loc, dict) else loc
                    if name:
                        places.append(clean(name))
                city = "Remote" + (f" ({', '.join(places[:3])})" if places else " (Worldwide)")
                cats = list(job.get("parentCategories") or []) + list(job.get("categories") or [])
                out.append({
                    "title": job.get("title"),
                    "company": job.get("companyName"),
                    "city": city,
                    "text": text_from_html(job.get("description") or job.get("excerpt")),
                    "source_url": job.get("applicationLink") or job.get("guid"),
                    "external_id": job.get("guid"),
                    "tags": cats,
                    # Specific categories ("QA-Engineer") before broad ones ("Developer").
                    "category": list(job.get("categories") or []) + list(job.get("parentCategories") or []),
                    "remote": True,
                })
        return out


class JobicyConnector(FeedConnector):
    """https://jobicy.com/jobs-rss-feed — public Jobs API, polled at most hourly."""

    name = "Jobicy"
    entry_url = "https://jobicy.com/api/v2/remote-jobs"
    remote_default = True
    min_interval_hours = 3
    credit_note = (
        "Jobicy public Jobs API. Credit Jobicy with a direct link to the source; the apply "
        "button must lead to the Jobicy listing URL from the feed."
    )

    def feed_items(self) -> list[dict]:
        payload = self.client.get_json(self.entry_url + "?count=200")
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise SourceFailed("jobicy payload had no jobs list")
        out: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            geo = clean(job.get("jobGeo"))
            out.append({
                "title": clean(job.get("jobTitle")),
                "company": job.get("companyName"),
                "city": f"Remote ({geo})" if geo else "Remote",
                "text": text_from_html(job.get("jobDescription") or job.get("jobExcerpt")),
                "source_url": job.get("url"),
                "external_id": job.get("id"),
                "category": job.get("jobIndustry") or [],
                "remote": True,
            })
        return out


class JobgetherConnector(FeedConnector):
    """https://jobgether.com — public astroapi JSON (robots Allow: /astroapi/ai/jobs.json)."""

    name = "Jobgether"
    entry_url = "https://jobgether.com/astroapi/ai/jobs.json"
    require_remote_or_relocation = True
    min_interval_hours = 3
    max_pages = 5
    # Feed has no description; the public offer page fills JobPosting text.
    detail = True
    credit_note = "Jobgether public astroapi jobs JSON. The link opens the Jobgether offer URL."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            url = self.entry_url if page == 1 else f"{self.entry_url}?page={page}"
            payload = self.client.get_json(url)
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(jobs, list):
                raise SourceFailed("jobgether payload had no jobs list")
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                source_url = clean(job.get("url"))
                if not source_url or source_url in seen:
                    continue
                funcs = [clean(f) for f in (job.get("jobFunctions") or []) if clean(f)]
                title = clean(job.get("title"))
                if not title:
                    continue
                remote_raw = clean(job.get("remote"))
                remote = bool(re.search(r"(?i)\bremote\b", remote_raw)) if remote_raw else None
                place = clean(job.get("location"))
                city = place
                if remote and place and not re.search(r"(?i)\bremote\b", place):
                    city = f"Remote ({place})"
                elif remote and not place:
                    city = "Remote"
                seen.add(source_url)
                out.append({
                    "title": title,
                    "company": job.get("company"),
                    "city": city,
                    "text": "",
                    "source_url": source_url,
                    "external_id": job.get("id"),
                    "tags": funcs,
                    "category": funcs,
                    "remote": True if remote else None,
                    "_stamp": job.get("postedAt"),
                })
            page_info = payload.get("pagination") if isinstance(payload, dict) else None
            if not isinstance(page_info, dict) or not page_info.get("hasMore"):
                break
        return out


class WorkingNomadsConnector(FeedConnector):
    """Working Nomads public jobs API linked from workingnomads.com."""

    name = "Working Nomads"
    entry_url = "https://www.workingnomads.com/api/exposed_jobs/"
    remote_default = True
    credit_note = "Working Nomads public jobs API. Name Working Nomads as the source."

    def feed_items(self) -> list[dict]:
        payload = self.client.get_json(self.entry_url)
        if not isinstance(payload, list):
            raise SourceFailed("working nomads payload was not a list")
        out: list[dict] = []
        for job in payload:
            if not isinstance(job, dict):
                continue
            place = clean(job.get("location"))
            out.append({
                "title": job.get("title"),
                "company": job.get("company_name"),
                "city": f"Remote ({place})" if place else "Remote",
                "text": text_from_html(job.get("description")),
                "source_url": job.get("url"),
                "external_id": (re.findall(r"\d+", str(job.get("url") or "")) or [""])[-1],
                "tags": job.get("tags") or "",
                "category": job.get("category_name") or "",
                "remote": True,
            })
        return out


class FourDayWeekConnector(FeedConnector):
    """https://4dayweek.io/developers — public v2 API, remote engineering roles."""

    name = "4 Day Week"
    entry_url = "https://4dayweek.io/api/v2/jobs"
    remote_default = True
    min_interval_hours = 3
    credit_note = "4dayweek.io public API. Link back to https://4dayweek.io."

    def feed_items(self) -> list[dict]:
        payload = self.client.get_json(
            self.entry_url + "?category=engineering&work_arrangement=remote&limit=100"
        )
        jobs = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise SourceFailed("4dayweek payload had no data list")
        out: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            places: list[str] = []
            for loc in job.get("locations") or []:
                if isinstance(loc, dict) and loc.get("country") and loc["country"] not in places:
                    places.append(loc["country"])
            company = job.get("company") or {}
            tags = [
                x.get("name")
                for key in ("stack", "skills", "tools")
                for x in (job.get(key) or [])
                if isinstance(x, dict)
            ]
            out.append({
                "title": job.get("title"),
                "company": company.get("name") if isinstance(company, dict) else "",
                "city": "Remote" + (f" ({', '.join(places[:3])})" if places else ""),
                "text": str(job.get("description") or "").replace("#### ", "").strip(),
                "source_url": job.get("url"),
                "external_id": job.get("id"),
                "tags": tags,
                # Every row is category=engineering (the query); the role is specific.
                "category": [x for x in (job.get("role"), job.get("category")) if x],
                "remote": job.get("work_arrangement") == "remote",
            })
        return out


class HnWhoIsHiringConnector(FeedConnector):
    """Hacker News "Ask HN: Who is hiring?" via the public Algolia HN Search API.

    Only top-level comments of the latest monthly thread that mention REMOTE or
    VISA/relocation are kept. news.ycombinator.com itself is not fetched.
    """

    name = "HN Who is hiring"
    entry_url = "https://hn.algolia.com/api/v1/search_by_date"
    require_remote_or_relocation = True
    min_interval_hours = 6
    credit_note = "Hacker News 'Who is hiring?' thread via the Algolia HN Search API."

    def feed_items(self) -> list[dict]:
        stories = self.client.get_json(
            self.entry_url + "?tags=story,author_whoishiring&hitsPerPage=6"
        )
        hits = stories.get("hits") if isinstance(stories, dict) else None
        if not isinstance(hits, list):
            raise SourceFailed("hn payload had no hits")
        thread = next(
            (h for h in hits if "who is hiring" in str(h.get("title") or "").lower()),
            None,
        )
        if not thread:
            return []
        story_id = str(thread.get("objectID"))
        payload = self.client.get_json(
            f"{self.entry_url}?tags=comment,story_{story_id}&hitsPerPage=300"
        )
        out: list[dict] = []
        for hit in payload.get("hits") or []:
            if str(hit.get("parent_id")) != story_id:
                continue
            item = parse_hn_comment(str(hit.get("comment_text") or ""))
            if not item:
                continue
            item["source_url"] = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            item["external_id"] = str(hit.get("objectID") or "")
            out.append(item)
        return out


_FLAG_SEG = re.compile(
    r"(?i)^(?:remote.*|onsite.*|on-site.*|hybrid.*|full[\s-]?time.*|part[\s-]?time.*|ft|pt|"
    r"contract(?:or)?.*|intern(?:ship)?s?|visa.*|no visa.*|\$.*|€.*|£.*|.*equity.*|"
    r"https?://.*|www\..*|[\w.-]+\.(?:com|io|ai|dev|co|org|net|app)(?:/.*)?)$"
)
_ROLE_HINT = re.compile(
    r"(?i)engineer|developer|programmer|scientist|architect|designer|devops|\bsre\b|"
    r"manager|lead|head of|cto|analyst|roles|positions|researcher|founding"
)


def parse_hn_comment(html: str) -> dict | None:
    text = text_from_html(html)
    if not text:
        return None
    head = text.split("\n", 1)[0]
    parts = [clean(p) for p in head.split("|") if clean(p)]
    if len(parts) < 2:
        return None
    company = re.sub(r"\s*\(.*?\)\s*$", "", parts[0])[:120]
    rest = parts[1:]
    role = next((p for p in rest if _ROLE_HINT.search(p) and not _FLAG_SEG.match(p)), "")
    if not role:
        return None
    place = ""
    for p in rest:
        if p == role or _ROLE_HINT.search(p):
            continue
        if _FLAG_SEG.match(p):
            if not place and re.match(r"(?i)^remote\b", p):
                place = p
            continue
        place = p
        break
    remote = bool(re.search(r"(?i)\bremote\b", head)) and not re.search(
        r"(?i)\bno remote\b|\bnot remote\b", head
    )
    visa = bool(re.search(r"(?i)\bvisa\b|relocat", head)) and not re.search(
        r"(?i)\bno visa\b|visa:\s*no", head
    )
    return {
        "title": role[:200],
        "company": company,
        "city": place or ("Remote" if remote else ""),
        "text": text,
        "remote": True if remote else None,
        "relocation": True if visa else None,
    }
