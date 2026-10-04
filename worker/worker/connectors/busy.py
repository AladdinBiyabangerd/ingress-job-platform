"""Busy.az public vacancy pages from the sitemap."""

from __future__ import annotations

import re

from worker.connectors.sitemap import SitemapConnector, path_is, vacancy_sitemap
from worker.parsing import clean, html_to_text, job_postings


class BusyConnector(SitemapConnector):
    name = "Busy.az"
    entry_url = "https://busy.az/sitemap_all.xml"

    def accept_sitemap(self, url: str) -> bool:
        return vacancy_sitemap(url)

    def accept_page(self, url: str) -> bool:
        if "/remote" in urlparse_path(url):
            return False
        return path_is(url, r"/vacancy/\d+(?:/[^/]+)?")

    def parse_page(self, html: str, url: str) -> dict | None:
        postings = job_postings(html)
        if not postings:
            return None
        job = postings[0]
        title = clean(job.get("title"))
        org = job.get("hiringOrganization") or {}
        company = clean(org.get("name")) if isinstance(org, dict) else ""
        city = _city(job.get("jobLocation"))
        text = html_to_text(str(job.get("description") or ""))
        ident = job.get("identifier") or {}
        external_id = ""
        if isinstance(ident, dict) and ident.get("value") is not None:
            external_id = clean(ident.get("value"))
        if not external_id:
            match = re.search(r"/vacancy/(\d+)", url)
            external_id = match.group(1) if match else ""
        if not title:
            return None
        return {
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": external_id,
        }


def urlparse_path(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).path


def _city(location: object) -> str:
    if isinstance(location, list):
        location = location[0] if location else {}
    if not isinstance(location, dict):
        return ""
    address = location.get("address") or {}
    if isinstance(address, list):
        address = address[0] if address else {}
    if not isinstance(address, dict):
        return ""
    return clean(address.get("addressLocality") or "")
