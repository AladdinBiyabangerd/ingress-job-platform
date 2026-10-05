"""Open HTML boards for relocation and remote tech jobs.

One public list page, then each job page. No query strings, no login pages.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import clean, html_to_text, job_postings, meta_content, posting_item


def _requirements(job: dict) -> list[str]:
    raw = job.get("applicantLocationRequirements") or []
    if isinstance(raw, dict):
        raw = [raw]
    names: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        name = clean(item.get("name")) if isinstance(item, dict) else clean(item)
        if name and name not in names:
            names.append(name)
    return names


def _telecommute(job: dict) -> bool:
    kind = job.get("jobLocationType")
    kinds = kind if isinstance(kind, list) else [kind]
    return any(str(k or "").upper() == "TELECOMMUTE" for k in kinds)


class RelocateMeConnector(OpenListConnector):
    """relocate.me — tech jobs abroad, each with a relocation package."""

    name = "Relocate.me"
    entry_url = "https://relocate.me/international-jobs"
    relocation_default = True
    credit_note = "Relocate.me public job pages."

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if not path_is(url, r"/[a-z-]+/[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+-\d+"):
                continue
            path = urlparse(url).path
            if path.startswith(("/remote/", "/blog/", "/moving-to")) or "/the-global-move/" in path:
                continue
            urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        title = clean(heading.get_text(" ", strip=True) if heading else "")
        if not title:
            return None
        parts = urlparse(url).path.strip("/").split("/")
        country, city, company_slug = (parts + ["", "", ""])[:3]
        company_el = soup.select_one(".job-info__company")
        company = clean(company_el.get_text(" ", strip=True)) if company_el else ""
        if not company:
            og = meta_content(soup, "property", "og:title")
            found = re.search(r" at (.+?) in ", og)
            company = found.group(1) if found else company_slug.replace("-", " ").title()
        place = ", ".join(
            p.replace("-", " ").title() for p in (city, country) if p
        )
        body = soup.select_one(".job-info__description") or soup.select_one(".job-info")
        text = html_to_text(str(body)) if body else meta_content(soup, "name", "description")
        tags = [clean(t.get_text(" ", strip=True)) for t in soup.select(".job__tag")]
        return {
            "title": title,
            "company": company,
            "city": place,
            "text": text,
            "external_id": (re.findall(r"-(\d+)$", url) or [""])[0],
            "tags": [t for t in tags if t],
            "category": [t for t in tags if t],
            # On-site jobs abroad. Never marked remote from loose text mentions.
            "remote": False,
            "relocation": True,
            "credit_note": self.credit_note,
        }


class JapanDevConnector(OpenListConnector):
    """japan-dev.com — English-speaking tech jobs in Japan, many with visa sponsorship."""

    name = "Japan Dev"
    entry_url = "https://japan-dev.com/jobs"
    credit_note = "Japan Dev public job pages."

    def links(self, html: str, page_url: str) -> list[str]:
        return [u for u, _t in page_links(html, page_url) if path_is(u, r"/jobs/[a-z0-9-]+/[a-z0-9-]+")]

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        job = job_postings(html)[0]
        reqs = _requirements(job)
        overseas = len(reqs) > 1 or any(r.upper() not in {"JP", "JAPAN"} for r in reqs)
        item["remote"] = True if _telecommute(job) else None
        item["relocation"] = True if overseas else None
        item["credit_note"] = self.credit_note
        if not item.get("city"):
            item["city"] = "Japan"
        return item


class RemoteFirstJobsConnector(OpenListConnector):
    """remotefirstjobs.com — remote roles at remote-first companies."""

    name = "Remote First Jobs"
    entry_url = "https://remotefirstjobs.com/jobs/software-development"
    remote_default = True
    credit_note = "Remote First Jobs public job pages."

    def list_pages(self) -> list[str]:
        return [self.entry_url, "https://remotefirstjobs.com/jobs/cybersecurity"]

    def links(self, html: str, page_url: str) -> list[str]:
        return [
            u for u, _t in page_links(html, page_url)
            if path_is(u, r"/companies/[a-z0-9-]+/jobs/[a-z0-9-]+-\d+")
        ]

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        job = job_postings(html)[0]
        reqs = _requirements(job)
        item["city"] = "Remote" + (f" ({', '.join(reqs[:3])})" if reqs else "")
        item["remote"] = True
        item["credit_note"] = self.credit_note
        return item
