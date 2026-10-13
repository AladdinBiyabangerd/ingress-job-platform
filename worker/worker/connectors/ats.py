"""Employers' public applicant-tracking job boards (Greenhouse, Lever, Workable,
Teamtailor, Recruitee, Personio).

Each ATS publishes a documented, unauthenticated JSON/XML/RSS board per
employer, made for career sites and job aggregators. We read only that board
for a curated list of tech employers, keep tech titles, put remote roles first,
mix employers round-robin so one big board cannot fill a pass, and keep the
employer's own posting URL. The employer's department/team is the source
category. robots.txt is checked for the API host and for every posting URL.
"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from worker.ats_boards import ATS_MAX_BOARDS, GROUPS
from worker.connectors.feed import RSS_ACCEPT, FeedConnector, text_from_html
from worker.http import Disallowed, NotFound, SourceBlocked, SourceFailed
from worker.parsing import clean
from worker.techstack import is_tech_job

_REMOTE = re.compile(r"\b(remote|anywhere|distributed|work from home|wfh)\b", re.IGNORECASE)
PER_BOARD = 25


def round_robin(groups: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    depth = max((len(g) for g in groups), default=0)
    for i in range(depth):
        for group in groups:
            if i < len(group):
                out.append(group[i])
    return out


def _board_company(value: object) -> str:
    """Board titles like "Careers at Eucalyptus" or "Wolt - English" as the company name."""
    name = re.sub(r"^(?:careers|jobs) at\s+", "", clean(value), flags=re.IGNORECASE)
    return re.sub(r"\s+-\s+English$", "", name).strip()


def _remote_hint(*places: object) -> bool | None:
    """True when the board itself says remote; None lets text detection decide."""
    joined = " ".join(str(p or "") for p in places)
    return True if _REMOTE.search(joined) else None


def _rank(rows: list[dict], stamp_key: str = "_stamp") -> list[dict]:
    rows.sort(key=lambda r: str(r.get(stamp_key) or ""), reverse=True)
    rows.sort(key=lambda r: 0 if r.get("remote") else 1)
    for row in rows:
        row.pop(stamp_key, None)
    return rows[:PER_BOARD]


class AtsConnector(FeedConnector):
    boards: tuple[str, ...] = ()
    # Employer boards mix onsite and remote; keep only remote / relocation.
    require_remote_or_relocation = True
    # Employer boards change slowly: read each group at most every 3 hours,
    # look at no more than 80 new candidates, and rotate large groups so one
    # pass reads at most ATS_MAX_BOARDS boards.
    min_interval_hours = 3
    candidates = 80
    max_boards = ATS_MAX_BOARDS

    def board_items(self, slug: str) -> list[dict]:
        raise NotImplementedError

    @classmethod
    def rotation_slots(cls) -> int:
        """Passes needed so every board is read once (1 for groups that fit one pass)."""
        n = len(cls.boards)
        return max(1, -(-n // cls.max_boards))

    def boards_this_pass(self, now: float | None = None) -> tuple[str, ...]:
        boards = tuple(self.boards)
        if len(boards) <= self.max_boards:
            return boards
        slot = int((now if now is not None else time.time()) // (3600 * max(1, self.min_interval_hours)))
        start = (slot * self.max_boards) % len(boards)
        rotated = boards[start:] + boards[:start]
        return rotated[: self.max_boards]

    def feed_items(self) -> list[dict]:
        groups: list[list[dict]] = []
        failed = 0
        picked = self.boards_this_pass()
        deadline = getattr(self, "deadline", None)
        clock = getattr(self, "clock", time.monotonic)
        for slug in picked:
            if deadline is not None and clock() >= deadline:
                # Time budget spent: keep what was read, next pass rotates on.
                break
            try:
                rows = self.board_items(slug)
            except (NotFound, SourceFailed, ValueError, ET.ParseError):
                # One retired or broken employer board does not stop the rest.
                failed += 1
                continue
            groups.append(_rank([r for r in rows if r.get("title") and r.get("source_url")]))
        if picked and failed == len(picked):
            raise SourceFailed(f"no {self.name} board could be read")
        return round_robin(groups)


# ---------------------------------------------------------------- Greenhouse


class GreenhouseConnector(AtsConnector):
    """https://developers.greenhouse.io/job-board.html — public Job Board API.

    The list call is light (no content); the posting text, departments and
    offices come from the per-job call, made only for new tech candidates.
    """

    entry_url = "https://boards-api.greenhouse.io/v1/boards"
    credit_note = (
        "Employer's public Greenhouse job board (Job Board API). The link opens the "
        "employer's original posting."
    )

    def board_items(self, slug: str) -> list[dict]:
        payload = self.client.get_json(f"{self.entry_url}/{slug}/jobs")
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise SourceFailed(f"greenhouse board {slug} had no jobs list")
        rows: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict) or not job.get("id"):
                continue
            title = clean(job.get("title"))
            if not title or not is_tech_job(title):
                continue
            place = clean((job.get("location") or {}).get("name"))
            rows.append({
                "title": title,
                "company": _board_company(job.get("company_name")) or slug,
                "city": place,
                "text": "",
                "source_url": job.get("absolute_url") or f"https://job-boards.greenhouse.io/{slug}/jobs/{job['id']}",
                "external_id": f"gh-{slug}-{job['id']}",
                "remote": _remote_hint(place),
                "_api": f"{self.entry_url}/{slug}/jobs/{job['id']}",
                "_stamp": job.get("first_published") or job.get("updated_at"),
            })
        return rows

    def fetch(self, url: str) -> str:
        item = self._items.get(url)
        if item is not None and item.get("_api"):
            detail = self.client.get_json(item.pop("_api"))
            if isinstance(detail, dict):
                item["text"] = text_from_html(detail.get("content"))
                deps = [clean(d.get("name")) for d in detail.get("departments") or [] if isinstance(d, dict)]
                deps = [d for d in deps if d]
                if deps:
                    item["category"] = deps
                    item["tags"] = deps
                offices = [clean(o.get("location") or o.get("name")) for o in detail.get("offices") or []
                           if isinstance(o, dict)]
                offices = [o for o in offices if o]
                if offices and len(item.get("city") or "") < 4:
                    item["city"] = "; ".join(offices[:3])
        return super().fetch(url)




# --------------------------------------------------------------------- Lever


LEVER_NAMES = {
    "woven-by-toyota": "Woven by Toyota", "ninjavan": "Ninja Van", "dlocal": "dLocal",
    "jumpcloud": "JumpCloud", "cred": "CRED", "zeta": "Zeta", "meesho": "Meesho",
    "paytm": "Paytm", "binance": "Binance", "toptal": "Toptal", "kavak": "Kavak",
    "deputy": "Deputy", "palantir": "Palantir", "spotify": "Spotify", "outreach": "Outreach",
    "qonto": "Qonto", "swile": "Swile", "aircall": "Aircall", "zopa": "Zopa", "farfetch": "Farfetch",
    "malt": "Malt", "blablacar": "BlaBlaCar", "contentsquare": "Contentsquare",
    "pipedrive": "Pipedrive", "lodgify": "Lodgify", "jobandtalent": "Jobandtalent",
    "dreamgames": "Dream Games", "peakgames": "Peak Games", "trendyol": "Trendyol",
    "anchorage": "Anchorage Digital", "olo": "Olo", "fullscript": "Fullscript", "ro": "Ro",
    "zoox": "Zoox", "wattpad": "Wattpad", "relay": "Relay", "mindtickle": "Mindtickle",
    "fampay": "FamPay", "crypto": "Crypto.com", "lalamove": "Lalamove", "nium": "Nium",
    "immutable": "Immutable",
}


class LeverConnector(AtsConnector):
    """https://github.com/lever/postings-api — public Postings API, full text per call."""

    entry_url = "https://api.lever.co/v0/postings"
    credit_note = (
        "Employer's public Lever job board (Postings API). The link opens the employer's "
        "original posting on jobs.lever.co."
    )

    def board_items(self, slug: str) -> list[dict]:
        jobs = self.client.get_json(f"{self.entry_url}/{slug}?mode=json")
        if not isinstance(jobs, list):
            raise SourceFailed(f"lever board {slug} was not a list")
        rows: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            title = clean(job.get("text"))
            cats = job.get("categories") or {}
            team = [clean(cats.get(k)) for k in ("team", "department") if clean(cats.get(k))]
            if not title or not is_tech_job(title, team, team):
                continue
            places = [clean(p) for p in cats.get("allLocations") or [] if clean(p)]
            place = "; ".join(places[:3]) or clean(cats.get("location"))
            workplace = str(job.get("workplaceType") or "").lower()
            parts = [str(job.get("descriptionPlain") or job.get("openingPlain") or "")]
            for block in job.get("lists") or []:
                if isinstance(block, dict):
                    parts.append(clean(block.get("text")))
                    parts.append(text_from_html(block.get("content")))
            parts.append(str(job.get("additionalPlain") or ""))
            rows.append({
                "title": title,
                "company": LEVER_NAMES.get(slug) or slug.replace("-", " ").title(),
                "city": place,
                "text": "\n".join(p for p in parts if p).strip(),
                "source_url": job.get("hostedUrl"),
                "external_id": f"lever-{slug}-{job.get('id')}",
                "category": team,
                "tags": team,
                "remote": True if workplace == "remote" else _remote_hint(place),
                "_stamp": f"{int(job.get('createdAt') or 0):015d}",
            })
        return rows




# ------------------------------------------------------------------ Workable


class WorkableConnector(AtsConnector):
    """Workable's public careers widget API (the endpoint career-site widgets use)."""

    name = "Workable boards (Europe)"
    entry_url = "https://apply.workable.com/api/v1/widget/accounts"
    # mercari / huggingface / 1password / peoplecert / orfium checked 2026-10-10.
    boards = (
        "skroutz", "blueground", "persado", "epignosis", "mercari", "huggingface",
        "1password", "peoplecert", "orfium",
    )
    credit_note = "Employer's public Workable careers widget. The link opens the employer's posting on apply.workable.com."

    def board_items(self, slug: str) -> list[dict]:
        payload = self.client.get_json(f"{self.entry_url}/{slug}?details=true")
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise SourceFailed(f"workable board {slug} had no jobs list")
        company = clean(payload.get("name")) or slug
        rows: list[dict] = []
        for job in jobs:
            if not isinstance(job, dict):
                continue
            title = clean(job.get("title"))
            dept = [clean(job.get("department"))] if clean(job.get("department")) else []
            if clean(job.get("function")):
                dept.append(clean(job.get("function")))
            if not title or not is_tech_job(title, dept, dept):
                continue
            place = ", ".join(x for x in (clean(job.get("city")), clean(job.get("country"))) if x)
            rows.append({
                "title": title,
                "company": company,
                "city": place,
                "text": text_from_html(job.get("description")),
                "source_url": job.get("url") or job.get("shortlink"),
                "external_id": f"workable-{slug}-{job.get('shortcode')}",
                "category": dept,
                "tags": dept,
                "remote": True if job.get("telecommuting") else _remote_hint(place),
                "_stamp": job.get("published_on") or job.get("created_at"),
            })
        return rows


# -------------------------------------------------------------------- Breezy


# Breezy localizes country names ("Україна"); the ISO code is stable, so the English name goes to
# the place text where the shared region rules can read it.
ISO_COUNTRIES = {
    "US": "United States", "CA": "Canada", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina",
    "CO": "Colombia", "CL": "Chile", "PE": "Peru", "UY": "Uruguay", "CR": "Costa Rica",
    "GB": "United Kingdom", "IE": "Ireland", "DE": "Germany", "FR": "France", "ES": "Spain",
    "PT": "Portugal", "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "LU": "Luxembourg",
    "CH": "Switzerland", "AT": "Austria", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "IS": "Iceland", "PL": "Poland", "CZ": "Czech Republic", "SK": "Slovakia",
    "HU": "Hungary", "RO": "Romania", "BG": "Bulgaria", "GR": "Greece", "CY": "Cyprus",
    "MT": "Malta", "HR": "Croatia", "SI": "Slovenia", "RS": "Serbia", "BA": "Bosnia",
    "ME": "Montenegro", "MK": "North Macedonia", "AL": "Albania", "EE": "Estonia", "LV": "Latvia",
    "LT": "Lithuania", "UA": "Ukraine", "BY": "Belarus", "MD": "Moldova", "TR": "Turkey",
    "IL": "Israel", "AE": "United Arab Emirates", "SA": "Saudi Arabia", "QA": "Qatar", "EG": "Egypt",
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "MA": "Morocco", "IN": "India",
    "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka", "PH": "Philippines", "VN": "Vietnam",
    "TH": "Thailand", "MY": "Malaysia", "SG": "Singapore", "ID": "Indonesia", "JP": "Japan",
    "KR": "South Korea", "CN": "China", "HK": "Hong Kong", "TW": "Taiwan", "AU": "Australia",
    "NZ": "New Zealand", "GE": "Georgia", "AM": "Armenia", "KZ": "Kazakhstan", "UZ": "Uzbekistan",
    "AZ": "Azerbaijan",
}


class BreezyConnector(AtsConnector):
    """Breezy HR career portals publish https://{company}.breezy.hr/json (title, remote flag,
    location, no text). The posting page's schema.org JobPosting gives the text, read only
    for new tech candidates."""

    detail = True
    entry_url = "https://abba.breezy.hr/json"
    credit_note = "Employer's public Breezy HR career portal. The link opens the employer's posting."

    def board_items(self, slug: str) -> list[dict]:
        url = f"https://{slug}.breezy.hr/json"
        if not self.client.allowed(url):
            return []
        payload = self.client.get_json(url)
        if not isinstance(payload, list):
            raise SourceFailed(f"breezy board {slug} was not a list")
        rows: list[dict] = []
        for job in payload:
            if not isinstance(job, dict) or not job.get("id"):
                continue
            title = clean(job.get("name"))
            dept = [clean(job.get("department"))] if clean(job.get("department")) else []
            if not title or not is_tech_job(title, dept, dept):
                continue
            loc = job.get("location") or {}
            place = clean(loc.get("name")) if isinstance(loc, dict) else ""
            code = clean(((loc.get("country") or {}) if isinstance(loc, dict) else {}).get("id")).upper()
            country = ISO_COUNTRIES.get(code, "")
            if isinstance(loc, dict) and loc.get("is_remote"):
                place = f"Remote ({country})" if country else "Remote"
            company = clean((job.get("company") or {}).get("name")) or slug
            rows.append({
                "title": title,
                "company": company,
                "city": place,
                "text": "",
                "source_url": job.get("url"),
                "external_id": f"breezy-{slug}-{job.get('id')}",
                "category": dept,
                "tags": dept,
                "remote": True if isinstance(loc, dict) and loc.get("is_remote") else _remote_hint(place),
                "_stamp": job.get("published_date"),
            })
        return rows


# ------------------------------------------------------------------ Pinpoint


class PinpointConnector(AtsConnector):
    """Pinpoint career sites publish https://{company}.pinpointhq.com/postings.json (full text,
    workplace type, location) — one request per board."""

    entry_url = "https://davies.pinpointhq.com/postings.json"
    credit_note = "Employer's public Pinpoint career site. The link opens the employer's posting."

    def board_items(self, slug: str) -> list[dict]:
        url = f"https://{slug}.pinpointhq.com/postings.json"
        if not self.client.allowed(url):
            return []
        payload = self.client.get_json(url)
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise SourceFailed(f"pinpoint board {slug} had no data list")
        rows: list[dict] = []
        for job in data:
            if not isinstance(job, dict) or not job.get("url"):
                continue
            title = clean(job.get("title"))
            meta = job.get("job") if isinstance(job.get("job"), dict) else {}
            dept = clean((meta.get("department") or {}).get("name")) if isinstance(meta.get("department"), dict) else ""
            dept_l = [dept] if dept else []
            if not title or not is_tech_job(title, dept_l, dept_l):
                continue
            loc = job.get("location") if isinstance(job.get("location"), dict) else {}
            place = ", ".join(x for x in (clean(loc.get("city")), clean(loc.get("province"))) if x) or clean(loc.get("name"))
            workplace = str(job.get("workplace_type") or "").lower()
            body = "\n\n".join(
                text_from_html(job.get(k))
                for k in ("description", "key_responsibilities", "skills_knowledge_expertise", "benefits") if job.get(k)
            )
            rows.append({
                "title": title,
                "company": clean(meta.get("company_name")) or slug.replace("-", " ").title(),
                "city": f"Remote ({place})" if workplace == "remote" and place else ("Remote" if workplace == "remote" else place),
                "text": body,
                "source_url": job.get("url"),
                "external_id": f"pinpoint-{slug}-{job.get('id')}",
                "category": dept_l,
                "tags": dept_l,
                "remote": True if workplace == "remote" else _remote_hint(place),
                "_stamp": job.get("deadline_at"),
            })
        return rows


# ---------------------------------------------------------------- Teamtailor


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


class TeamtailorConnector(AtsConnector):
    """Teamtailor career sites publish /jobs.rss (department, role, remote status, locations)."""

    credit_note = "Employer's public Teamtailor career-site RSS feed. The link opens the employer's posting."

    def board_items(self, slug: str) -> list[dict]:
        url = f"https://{slug}.teamtailor.com/jobs.rss"
        if not self.client.allowed(url):
            return []
        root = ET.fromstring(self.client.get_text(url, accept=RSS_ACCEPT).lstrip("\ufeff").strip().encode("utf-8"))
        rows: list[dict] = []
        for node in root.iter():
            if _local(node.tag) != "item":
                continue
            fields: dict[str, str] = {}
            places: list[str] = []
            for child in node:
                key = _local(child.tag)
                if key == "locations":
                    for loc in child:
                        bits = {_local(x.tag): clean(x.text) for x in loc}
                        label = ", ".join(b for b in (bits.get("city"), bits.get("country")) if b) or bits.get("name", "")
                        if label:
                            places.append(label)
                else:
                    fields[key] = (child.text or "").strip()
            title = clean(fields.get("title"))
            dept = [clean(fields.get(k)) for k in ("department", "role") if clean(fields.get(k))]
            if not title or not is_tech_job(title, dept, dept):
                continue
            status = fields.get("remotestatus", "").lower()
            place = "; ".join(places[:3])
            rows.append({
                "title": title,
                "company": clean(fields.get("company_name")) or slug.title(),
                "city": place,
                "text": text_from_html(fields.get("description")),
                "source_url": fields.get("link"),
                "external_id": f"teamtailor-{slug}-{fields.get('guid')}",
                "category": dept,
                "tags": dept,
                "remote": True if status in {"fully", "remote", "fully_remote"} else _remote_hint(place),
                "_stamp": fields.get("pubdate"),
            })
        return rows


# ----------------------------------------------------------------- Recruitee


class RecruiteeConnector(AtsConnector):
    """Recruitee careers API: https://{company}.recruitee.com/api/offers/ (public)."""

    name = "Recruitee boards (Netherlands)"
    entry_url = "https://bunq.recruitee.com/api/offers/"
    # effectory / mailerlite / adjust checked 2026-10-10 (public offers API, tech roles).
    boards = ("bunq", "channable", "effectory", "mailerlite", "adjust")
    credit_note = "Employer's public Recruitee careers API. The link opens the employer's posting."

    def board_items(self, slug: str) -> list[dict]:
        url = f"https://{slug}.recruitee.com/api/offers/"
        if not self.client.allowed(url):
            return []
        payload = self.client.get_json(url)
        offers = payload.get("offers") if isinstance(payload, dict) else None
        if not isinstance(offers, list):
            raise SourceFailed(f"recruitee board {slug} had no offers list")
        rows: list[dict] = []
        for job in offers:
            if not isinstance(job, dict) or job.get("status") not in (None, "published"):
                continue
            title = clean(job.get("title"))
            dept = [clean(job.get("department"))] if clean(job.get("department")) else []
            tags = dept + [clean(t) for t in job.get("tags") or [] if clean(t)]
            if not title or not is_tech_job(title, dept, tags):
                continue
            place = clean(job.get("location")) or ", ".join(
                x for x in (clean(job.get("city")), clean(job.get("country"))) if x)
            text = "\n".join(text_from_html(job.get(k)) for k in ("description", "requirements") if job.get(k))
            rows.append({
                "title": title,
                "company": clean(job.get("company_name")) or slug,
                "city": place,
                "text": text,
                "source_url": job.get("careers_url"),
                "external_id": f"recruitee-{slug}-{job.get('id')}",
                "category": dept,
                "tags": tags,
                "remote": True if job.get("remote") else _remote_hint(place),
                "_stamp": job.get("published_at") or job.get("created_at"),
            })
        return rows


# ------------------------------------------------------------------ Personio


class PersonioConnector(AtsConnector):
    """Personio career pages publish https://{company}.jobs.personio.de/xml (public)."""

    name = "Personio boards (Germany)"
    entry_url = "https://chrono24.jobs.personio.de/xml"
    boards = ("chrono24", "taxdoo", "1komma5grad", "ottonova")
    # Some boards ship the XML without descriptions; the posting page's
    # schema.org JobPosting fills the text then (one extra read per new ad).
    detail = True
    credit_note = "Employer's public Personio career-page XML feed. The link opens the employer's posting."

    def fetch(self, url: str) -> str:
        try:
            return super().fetch(url)
        except SourceBlocked as exc:
            # A closed posting redirects to personio.com; a refusal there must
            # not stop the employer boards. A refusal on the board host still does.
            if urlparse(url).netloc in str(exc):
                raise
            raise NotFound(url) from exc

    def board_items(self, slug: str) -> list[dict]:
        base = f"https://{slug}.jobs.personio.de"
        if not self.client.allowed(base + "/xml"):
            return []
        root = ET.fromstring(self.client.get_text(base + "/xml", accept="application/xml").strip().encode("utf-8"))
        rows: list[dict] = []
        for pos in root.iter("position"):
            get = lambda tag: clean(pos.findtext(tag))  # noqa: E731
            title = get("name")
            dept = [x for x in (get("department"), get("recruitingCategory"), get("occupationCategory")) if x]
            if not title or not get("id") or not is_tech_job(title, dept, dept):
                continue
            offices = [get("office")] + [clean(o.text) for o in pos.findall("additionalOffices/office")]
            place = "; ".join(o for o in offices if o)
            parts = []
            for desc in pos.findall("jobDescriptions/jobDescription"):
                head = clean(desc.findtext("name"))
                body = text_from_html(desc.findtext("value"))
                parts.append(f"{head}\n{body}" if head else body)
            rows.append({
                "title": title,
                "company": get("subcompany").split(" - ")[0] or slug,
                "city": place,
                "text": "\n\n".join(p for p in parts if p),
                "source_url": f"{base}/job/{get('id')}",
                "external_id": f"personio-{slug}-{get('id')}",
                "category": dept,
                "tags": dept,
                "remote": _remote_hint(place, title),
                "_stamp": get("createdAt"),
            })
        return rows


# ------------------------------------------------------------ regional groups

# --------------------------------------------------------------------- Ashby


def _ashby_app_data(html: str) -> dict:
    marker = "window.__appData = "
    i = html.find(marker)
    if i < 0:
        raise SourceFailed("ashby page had no app data")
    try:
        data, _ = json.JSONDecoder().raw_decode(html[i + len(marker):])
    except ValueError as exc:
        raise SourceFailed("ashby app data unreadable") from exc
    return data if isinstance(data, dict) else {}


class AshbyConnector(AtsConnector):
    """Employer boards hosted on jobs.ashbyhq.com.

    api.ashbyhq.com answers robots.txt with HTTP 401 (treated as blocked), so we
    read the robots-allowed hosted pages instead: the board page carries the job
    list (title, location, workplace type) and each posting page its full text.
    Only /api/, /b/ and /meeting/ are disallowed on jobs.ashbyhq.com."""

    entry_url = "https://jobs.ashbyhq.com/"
    credit_note = (
        "Employer's public Ashby job board (jobs.ashbyhq.com). The link opens the employer's "
        "original posting."
    )

    def board_items(self, slug: str) -> list[dict]:
        url = f"https://jobs.ashbyhq.com/{slug}"
        if not self.client.allowed(url):
            return []
        data = _ashby_app_data(self.client.get_text(url))
        board = data.get("jobBoard") or {}
        posts = board.get("jobPostings") if isinstance(board, dict) else None
        if not isinstance(posts, list):
            raise SourceFailed(f"ashby board {slug} had no postings")
        org = data.get("organization") or {}
        company = clean(org.get("name")) or slug
        teams = {t.get("id"): clean(t.get("name")) for t in board.get("teams") or [] if isinstance(t, dict)}
        rows: list[dict] = []
        for job in posts:
            if not isinstance(job, dict) or not job.get("id"):
                continue
            title = clean(job.get("title"))
            team = [teams[job.get("teamId")]] if teams.get(job.get("teamId")) else []
            if not title or not is_tech_job(title, team, team):
                continue
            places = [clean(job.get("locationName"))] + [
                clean(x.get("locationName") if isinstance(x, dict) else x)
                for x in job.get("secondaryLocations") or []]
            place = "; ".join(p for p in places if p)[:200]
            workplace = str(job.get("workplaceType") or "").lower()
            rows.append({
                "title": title,
                "company": company,
                "city": place,
                "text": "",
                "source_url": f"https://jobs.ashbyhq.com/{slug}/{job['id']}",
                "external_id": f"ashby-{slug}-{job['id']}",
                "category": team,
                "tags": team,
                "remote": True if workplace == "remote" else _remote_hint(place),
                "_stamp": job.get("publishedDate") or job.get("publishedAt") or "",
            })
        return rows

    def fetch(self, url: str) -> str:
        item = self._items.get(url)
        if item is None:
            raise SourceFailed(f"feed item missing for {url}")
        if not self.client.allowed(url):
            raise Disallowed(url)
        post = _ashby_app_data(self.client.get_text(url)).get("posting") or {}
        if isinstance(post, dict) and post:
            item["text"] = text_from_html(post.get("descriptionHtml") or "")
            names = [clean(post.get("locationName"))] + [clean(x) for x in post.get("secondaryLocationNames") or []]
            place = "; ".join(x for x in names if x)
            if place:
                item["city"] = place[:200]
            if str(post.get("workplaceType") or "").lower() == "remote":
                item["remote"] = True
        return json.dumps(item, ensure_ascii=False)


_BASES = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "teamtailor": TeamtailorConnector,
    "breezy": BreezyConnector,
    "pinpoint": PinpointConnector,
    "ashby": AshbyConnector,
    "workable": WorkableConnector,
    "recruitee": RecruiteeConnector,
}


def _group_class(name: str, ats: str, boards: tuple[str, ...]) -> type:
    base = _BASES[ats]
    attrs = {"name": name, "boards": boards, "__doc__": f"{name}: {', '.join(boards)}."}
    if ats == "teamtailor":
        attrs["entry_url"] = f"https://{boards[0]}.teamtailor.com/jobs.rss"
    elif ats == "breezy":
        attrs["entry_url"] = f"https://{boards[0]}.breezy.hr/json"
    elif ats == "pinpoint":
        attrs["entry_url"] = f"https://{boards[0]}.pinpointhq.com/postings.json"
    elif ats == "recruitee":
        attrs["entry_url"] = f"https://{boards[0]}.recruitee.com/api/offers/"
    cls_name = re.sub(r"[^A-Za-z]", "", name.title()) + "Connector"
    return type(cls_name, (base,), attrs)


# Source name -> connector class, one per region group in ats_boards.GROUPS.
ATS_GROUP_CONNECTORS: dict[str, type] = {
    name: _group_class(name, ats, boards) for name, ats, _region, boards in GROUPS
}
