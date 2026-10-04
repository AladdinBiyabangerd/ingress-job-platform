"""Small defensive parsers shared by connectors."""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

_WS = re.compile(r"\s+")
_ZW = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def clean(value: object) -> str:
    text = unescape(str(value or ""))
    text = _ZW.sub("", text).replace("\xa0", " ")
    return _WS.sub(" ", text).strip()


def html_to_text(fragment: str, limit: int = 20000) -> str:
    soup = BeautifulSoup(fragment or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit]


def meta_content(soup: BeautifulSoup, attr: str, key: str) -> str:
    tag = soup.find("meta", attrs={attr: key})
    if tag is None:
        return ""
    return clean(tag.get("content") or "")


def job_postings(html: str) -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    found: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        found.extend(_walk_jobs(data))
    return found


def _walk_jobs(data: object) -> list[dict]:
    out: list[dict] = []
    if isinstance(data, list):
        for item in data:
            out.extend(_walk_jobs(item))
        return out
    if not isinstance(data, dict):
        return out
    typ = data.get("@type")
    types = typ if isinstance(typ, list) else [typ]
    if "JobPosting" in types:
        out.append(data)
    if data.get("@graph"):
        out.extend(_walk_jobs(data["@graph"]))
    return out


def styled_text(html: str, soup: BeautifulSoup, component: str, limit: int = 20000) -> str:
    hashes: list[str] = []
    for match in re.finditer(r'id="([^"]+)"\]\{content:"([^"]*)"\}', html):
        if component not in match.group(1):
            continue
        token = match.group(2).split(",")[0].strip()
        if token and re.fullmatch(r"[A-Za-z0-9_-]+", token):
            hashes.append(token)
    parts: list[str] = []
    seen: set[str] = set()
    for token in hashes:
        if token in seen:
            continue
        seen.add(token)
        for el in soup.select(f".{token}"):
            text = el.get_text("\n", strip=True)
            if text:
                parts.append(text)
    return "\n".join(parts)[:limit]


def parse_sitemap(xml_text: str) -> tuple[bool, list[str]]:
    raw = xml_text.lstrip("\ufeff").strip()
    raw = re.sub(r'\sxmlns(?::\w+)?="[^"]*"', "", raw)
    root = ET.fromstring(raw.encode("utf-8"))
    locs: list[str] = []
    for el in root.iter():
        if not str(el.tag).lower().endswith("loc"):
            continue
        if el.text and el.text.strip():
            locs.append(el.text.strip())
    return str(root.tag).lower().endswith("sitemapindex"), locs


def last_number(url: str) -> int:
    nums = re.findall(r"\d+", urlparse(url).path)
    if not nums:
        return -1
    try:
        return int(nums[-1])
    except ValueError:
        return -1


def norm_key(title: str, company: str, city: str) -> str:
    def norm(value: str) -> str:
        text = clean(value).casefold()
        text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
        return _WS.sub(" ", text).strip()

    return "|".join((norm(title), norm(company), norm(city)))


def address_locality(location: object) -> str:
    """City names from schema.org jobLocation. Several places stay readable."""
    if isinstance(location, list):
        cities: list[str] = []
        for item in location:
            city = address_locality(item)
            if city and city not in cities:
                cities.append(city)
        return ", ".join(cities[:3])
    if not isinstance(location, dict):
        return ""
    address = location.get("address") or {}
    if isinstance(address, list):
        address = address[0] if address else {}
    if not isinstance(address, dict):
        return ""
    return clean(address.get("addressLocality") or "")


def posting_item(html: str) -> dict | None:
    """First public JobPosting: title, company, city, text, external id."""
    postings = job_postings(html)
    if not postings:
        return None
    job = postings[0]
    title = clean(job.get("title"))
    if not title:
        return None
    org = job.get("hiringOrganization") or {}
    company = clean(org.get("name")) if isinstance(org, dict) else ""
    ident = job.get("identifier") or {}
    external_id = ""
    if isinstance(ident, dict) and ident.get("value") is not None:
        external_id = clean(ident.get("value"))
    return {
        "title": title,
        "company": company,
        "city": address_locality(job.get("jobLocation")),
        "text": html_to_text(str(job.get("description") or "")),
        "external_id": external_id,
    }
