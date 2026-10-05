"""Shared base for public APIs and RSS feeds.

discover() reads the feed once, keeps tech roles only, and remembers each item
by its public listing URL. fetch() returns that remembered item. When the feed
text is short and ``detail`` is set, fetch() also reads the public listing page
once and takes the schema.org JobPosting text. The runner adds tech stack,
remote and relocation flags and caps new ads per pass.
"""

from __future__ import annotations

import json
import re
from html import unescape
from xml.etree import ElementTree as ET

from worker.connectors.sitemap import CANDIDATES
from worker.db import Store
from worker.http import Disallowed, NotFound, PoliteClient, SourceBlocked, SourceFailed
from worker.parsing import clean, html_to_text, posting_item
from worker.techstack import is_tech_job

RSS_ACCEPT = "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"


class FeedConnector:
    name = ""
    entry_url = ""
    remote_default = False
    relocation_default = False
    require_remote_or_relocation = False
    min_interval_hours = 0
    detail = False
    detail_min_text = 600
    credit_note = ""

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store
        self._items: dict[str, dict] = {}

    # Subclasses return dicts with title, company, city, text, source_url and
    # optional external_id, tags, category, remote, relocation.
    def feed_items(self) -> list[dict]:
        raise NotImplementedError

    def discover(self) -> list[str]:
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        try:
            items = self.feed_items()
        except (SourceBlocked, SourceFailed, Disallowed):
            raise
        except NotFound as exc:
            raise SourceFailed(f"feed not found: {exc}") from exc
        except Exception as exc:
            raise SourceFailed(f"feed unreadable: {exc.__class__.__name__}") from exc
        urls: list[str] = []
        for item in items:
            url = str(item.get("source_url") or "").strip()
            title = clean(item.get("title"))
            if not url or not title or url in self._items:
                continue
            if not is_tech_job(title, item.get("category"), item.get("tags")):
                continue
            if self.store.has_source_url(url):
                continue
            if not self.client.allowed(url):
                continue
            item["title"] = title
            item["source_url"] = url
            self._items[url] = item
            urls.append(url)
            if len(urls) >= CANDIDATES:
                break
        return urls

    def fetch(self, url: str) -> str:
        item = self._items.get(url)
        if item is None:
            raise SourceFailed(f"feed item missing for {url}")
        if not self.client.allowed(url):
            raise Disallowed(url)
        short = len(str(item.get("text") or "")) < self.detail_min_text
        if self.detail and (short or not item.get("company")):
            try:
                page = posting_item(self.client.get_text(url))
            except (NotFound, Disallowed):
                page = None
            if page:
                if len(page.get("text") or "") > len(str(item.get("text") or "")):
                    item["text"] = page["text"]
                for key in ("company", "city", "external_id"):
                    if not item.get(key) and page.get(key):
                        item[key] = page[key]
        return json.dumps(item, ensure_ascii=False)

    def normalize(self, raw: str, url: str) -> dict | None:
        try:
            item = json.loads(raw)
        except Exception:
            return None
        title = clean(item.get("title"))
        if not title:
            return None
        item["title"] = title[:300]
        item["company"] = clean(item.get("company"))[:200]
        item["city"] = clean(item.get("city"))[:200]
        item["text"] = str(item.get("text") or "").strip()
        item["external_id"] = clean(item.get("external_id") or "")[:200]
        item["source_url"] = url
        item["source_name"] = self.name
        if self.credit_note and not item.get("credit_note"):
            item["credit_note"] = self.credit_note
        return item

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)


def text_from_html(fragment: object, limit: int = 20000) -> str:
    raw = str(fragment or "")
    if "&lt;" in raw and "<" not in raw.replace("&lt;", ""):
        raw = unescape(raw)
    return html_to_text(raw, limit)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def rss_items(xml_text: str) -> list[dict]:
    """RSS/Atom items as {local tag name: text or [texts]}. Tolerates broken XML."""
    raw = xml_text.lstrip("\ufeff").strip()
    try:
        root = ET.fromstring(raw.encode("utf-8"))
    except ET.ParseError:
        return _rss_items_loose(raw)
    out: list[dict] = []
    nodes = [el for el in root.iter() if _local(str(el.tag)) in {"item", "entry"}]
    for node in nodes:
        item: dict = {}
        for child in node:
            key = _local(str(child.tag))
            value = (child.text or "").strip()
            if key == "link" and not value:
                value = child.attrib.get("href", "")
            if not value and child.attrib.get("url"):
                value = child.attrib["url"]
            if key in item:
                if not isinstance(item[key], list):
                    item[key] = [item[key]]
                item[key].append(value)
            else:
                item[key] = value
        out.append(item)
    return out


_ITEM = re.compile(r"<item\b[^>]*>(.*?)</item>", re.S | re.I)
_CHILD = re.compile(r"<([A-Za-z][\w:.-]*)\b[^>]*>(.*?)</\1>", re.S)


def _rss_items_loose(raw: str) -> list[dict]:
    out: list[dict] = []
    for body in _ITEM.findall(raw):
        item: dict = {}
        for tag, value in _CHILD.findall(body):
            key = tag.rsplit(":", 1)[-1].lower()
            value = value.strip()
            if value.startswith("<![CDATA[") and value.endswith("]]>"):
                value = value[9:-3]
            elif key not in {"description", "encoded"}:
                value = unescape(value)
            if key in item:
                continue
            item[key] = value.strip()
        out.append(item)
    return out


def first(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if value:
        return [str(value)]
    return []


def read_rss(client: PoliteClient, url: str) -> list[dict]:
    return rss_items(client.get_text(url, accept=RSS_ACCEPT))
