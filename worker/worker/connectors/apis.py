"""Official public JSON APIs. No key, no HTML scraping of the list pages.

Each class reads only the documented endpoint, keeps the source's own listing
URL, and honours the polling advice the source publishes.
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

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
    # Each new tech candidate costs one offer-page request (robots Crawl-delay 2),
    # so cap new candidates per run: 25 pages is about a minute at 2 s each.
    detail = True
    candidates = 25
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
        # Remote offers first: with the per-run candidate cap they are the ones
        # that get an offer-page read; on-site rows only fill what is left.
        out.sort(key=lambda it: it.get("remote") is not True)
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


class DevITjobsUkConnector(FeedConnector):
    """https://devitjobs.uk — public ``/api/jobsLight`` JSON (robots.txt allows it for every
    bot except Meta-ExternalAgent). Most of the ~2300 rows are office jobs, so only
    ``workplace == remote`` and rows with ``hasVisaSponsorship == Yes`` are kept
    (the visa flag becomes the relocation signal). The long text comes from the
    site's public ``/rss`` (one request, only when a new candidate exists)."""

    name = "DevITjobs UK"
    entry_url = "https://devitjobs.uk/api/jobsLight"
    rss_url = "https://devitjobs.uk/rss"
    job_base = "https://devitjobs.uk/jobs/"
    require_remote_or_relocation = True
    min_interval_hours = 6
    candidates = 120
    credit_note = "DevITjobs UK public jobs API. The link opens the listing on devitjobs.uk."

    @staticmethod
    def _slug(url: str) -> str:
        return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]

    def _rss_text(self) -> dict[str, str]:
        from worker.connectors.feed import first, read_rss

        out: dict[str, str] = {}
        try:
            for it in read_rss(self.client, self.rss_url):
                slug = self._slug(first(it.get("link")))
                if slug:
                    out[slug] = text_from_html(first(it.get("description")))
        except SourceFailed:
            return {}
        return out

    def feed_items(self) -> list[dict]:
        payload = self.client.get_json(self.entry_url)
        if not isinstance(payload, list):
            raise SourceFailed("devitjobs payload was not a list")
        rows: list[dict] = []
        for job in payload:
            if not isinstance(job, dict) or job.get("isPaused") or not job.get("jobUrl") or not job.get("name"):
                continue
            remote = str(job.get("workplace") or "").lower() == "remote"
            visa = str(job.get("hasVisaSponsorship") or "").lower() == "yes"
            if not (remote or visa):
                continue
            rows.append((job, remote, visa))
        rows.sort(key=lambda r: str(r[0].get("activeFrom") or ""), reverse=True)
        from worker.market_fit import is_rejected

        conn = getattr(self.store, "conn", None)
        # Already stored or already rejected (e.g. UK-only remote) rows need no 10 MB RSS read.
        fresh = [
            r for r in rows
            if not self.store.has_source_url(self.job_base + str(r[0]["jobUrl"]))
            and not is_rejected(conn, self.job_base + str(r[0]["jobUrl"]))
        ]
        texts = self._rss_text() if fresh else {}
        out: list[dict] = []
        for job, remote, visa in rows:
            slug = str(job["jobUrl"])
            place = clean(job.get("actualCity") or job.get("cityCategory")).title()
            tech = [clean(t) for t in (job.get("technologies") or []) if clean(t)]
            body = texts.get(slug) or (
                f"{job.get('name')} at {job.get('company')}. Workplace: {job.get('workplace')}. "
                f"Level: {job.get('expLevel') or '-'}. Technologies: {', '.join(tech) or '-'}."
            )
            if visa:
                # The structured flag is the sponsorship statement; say it in the text so the
                # shared visa/relocation rules (which read text) see it.
                body += "\n\nVisa sponsorship: yes (DevITjobs UK hasVisaSponsorship flag)."
            city = "Remote (UK)" if remote else (place or "UK")
            if remote and place:
                city = f"Remote ({place}, UK)"
            out.append({
                "title": clean(job.get("name")),
                "company": clean(job.get("company")),
                "city": city,
                "text": body,
                "source_url": self.job_base + slug,
                "external_id": str(job.get("_id") or slug),
                "tags": tech,
                "category": [x for x in (job.get("techCategory"), job.get("metaCategory")) if x] + tech[:2],
                "remote": True if remote else None,
                "relocation": True if visa else None,
            })
        return out


class TheMuseConnector(FeedConnector):
    """https://www.themuse.com/developers/api/v2 — public jobs API (no key), engineering
    and data categories, only rows listing "Flexible / Remote". Mostly US employers, so
    the shared region gate does most of the filtering."""

    name = "The Muse"
    entry_url = "https://www.themuse.com/api/public/jobs"
    require_remote_or_relocation = True
    min_interval_hours = 6
    max_pages = 4
    categories = ("Software Engineering", "Data and Analytics")
    credit_note = "The Muse public jobs API. The link opens the listing on themuse.com."

    _US_STATE = re.compile(r",\s*[A-Z]{2}$")
    _OPEN = re.compile(r"(?i)\b(?:worldwide|anywhere|work from anywhere|global(?:ly)? remote|any country|EMEA)\b")
    _US_PAY = re.compile(r"(?i)401\(?k\)?|\$\s?\d{2,3},\d{3}|\bUSD\b|\bU\.?S\.?[- ]based\b|United States")

    @classmethod
    def not_us_only(cls, others: list[str], body: str) -> bool:
        """The Muse says only "Flexible / Remote" for US-resident remote roles too. Keep a row
        when it names a non-US place or the text is explicitly open; drop it when the text
        carries US pay/benefit signals (401k, $120,000 ranges, "United States")."""
        if cls._OPEN.search(body[:4000]):
            return True
        if cls._US_PAY.search(body):
            return False
        return any(not cls._US_STATE.search(p) and not p.endswith("United States") for p in others)

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for cat in self.categories:
            for page in range(1, self.max_pages + 1):
                url = (
                    f"{self.entry_url}?category={quote(cat)}&location={quote('Flexible / Remote')}"
                    f"&page={page}"
                )
                payload = self.client.get_json(url)
                rows = payload.get("results") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise SourceFailed("the muse payload had no results list")
                for job in rows:
                    if not isinstance(job, dict):
                        continue
                    link = clean((job.get("refs") or {}).get("landing_page"))
                    if not link or link in seen:
                        continue
                    places = [clean(l.get("name")) for l in job.get("locations") or [] if isinstance(l, dict)]
                    if not any(re.search(r"(?i)remote|flexible", p) for p in places):
                        continue
                    others = [p for p in places if p and not re.search(r"(?i)remote|flexible", p)]
                    body = text_from_html(job.get("contents"))
                    if not self.not_us_only(others, body):
                        continue
                    seen.add(link)
                    out.append({
                        "title": clean(job.get("name")),
                        "company": clean((job.get("company") or {}).get("name")),
                        "city": "Remote" + (f" ({'; '.join(others[:3])})" if others else ""),
                        "text": body,
                        "source_url": link,
                        "external_id": str(job.get("id") or ""),
                        # The Muse's own categories are loose (a "Software Engineering" row can be
                        # legal counsel), so the role is judged from the title only.
                        "category": [],
                        "tags": [],
                        "remote": True,
                        "_stamp": job.get("publication_date"),
                    })
                if page >= int(payload.get("page_count") or 0):
                    break
        out.sort(key=lambda it: str(it.get("_stamp") or ""), reverse=True)
        return out


class WorkableAggregatorConnector(FeedConnector):
    """https://jobs.workable.com — Workable's public job-search API (robots.txt only blocks
    /search*; /api/v1/jobs is open). Every Workable employer in one feed. A remote role is
    repeated once per country, so rows are merged on company + title and the listing is shown
    as plain "Remote" (the posting text, not the per-country row, decides region locks)."""

    name = "Workable jobs"
    entry_url = "https://jobs.workable.com/api/v1/jobs"
    require_remote_or_relocation = True
    min_interval_hours = 6
    pages_per_query = 3
    candidates = 40
    # (query, extra params): remote tech roles, Azerbaijan-based openings, relocation / visa offers.
    queries: tuple[tuple[str, str], ...] = (
        ("software engineer", "&workplace=remote"),
        ("developer", "&workplace=remote"),
        ("devops engineer", "&workplace=remote"),
        ("data engineer", "&workplace=remote"),
        ("qa engineer", "&workplace=remote"),
        ("software engineer", "&location=Azerbaijan"),
        ("developer relocation", ""),
        ("engineer visa sponsorship", ""),
    )
    credit_note = "Workable's public job search API. The link opens the posting on jobs.workable.com."

    @staticmethod
    def dedup_key(company: object, title: object) -> str:
        norm = lambda v: re.sub(r"[^a-z0-9]+", " ", str(v or "").lower()).strip()  # noqa: E731
        return f"{norm(company)}|{norm(title)}"

    def feed_items(self) -> list[dict]:
        out: dict[str, dict] = {}
        for query, extra in self.queries:
            token = ""
            for _page in range(self.pages_per_query):
                url = f"{self.entry_url}?query={quote(query)}{extra}"
                if token:
                    url += f"&pageToken={quote(token)}"
                payload = self.client.get_json(url)
                rows = payload.get("jobs") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise SourceFailed("workable payload had no jobs list")
                for job in rows:
                    if not isinstance(job, dict) or job.get("state") not in (None, "published"):
                        continue
                    if str(job.get("language") or "en").lower() not in {"en", ""}:
                        continue
                    company = clean((job.get("company") or {}).get("title"))
                    title = clean(job.get("title"))
                    link = clean(job.get("url"))
                    if not (company and title and link):
                        continue
                    key = self.dedup_key(company, title)
                    remote = str(job.get("workplace") or "").lower() == "remote" or "TELECOMMUTE" in (
                        job.get("locations") or [])
                    loc = job.get("location") or {}
                    place = ", ".join(x for x in (clean(loc.get("city")), clean(loc.get("countryName"))) if x)
                    prev = out.get(key)
                    if prev is not None:
                        # Same job, another country row: keep the first, remember the country.
                        if place and place not in prev["_places"]:
                            prev["_places"].append(place)
                        continue
                    body = "\n\n".join(
                        text_from_html(job.get(k))
                        for k in ("description", "requirementsSection", "benefitsSection") if job.get(k)
                    )
                    out[key] = {
                        "title": title,
                        "company": company,
                        "city": "Remote" if remote else place,
                        "text": body,
                        "source_url": link,
                        "external_id": f"workable-agg-{job.get('id')}",
                        "tags": [],
                        "category": [],
                        "remote": True if remote else None,
                        "_places": [place] if place else [],
                        "_stamp": job.get("created"),
                    }
                token = str(payload.get("nextPageToken") or "") if isinstance(payload, dict) else ""
                if not token:
                    break
        rows = sorted(out.values(), key=lambda r: str(r.pop("_stamp", "")), reverse=True)
        for row in rows:
            row.pop("_places", None)
        return rows
