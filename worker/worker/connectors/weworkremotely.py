"""We Work Remotely public RSS. The partner API is not called."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from worker.db import Store
from worker.http import PoliteClient, SourceBlocked, SourceFailed
from worker.parsing import clean, html_to_text

CAP = 30


class WeWorkRemotelyConnector:
    name = "We Work Remotely"
    entry_url = "https://weworkremotely.com/remote-jobs.rss"
    remote_default = True

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store
        self._raw: dict[str, str] = {}

    def discover(self) -> list[str]:
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        try:
            text = self.client.get_text(self.entry_url, accept="application/rss+xml,application/xml,text/xml,*/*")
            root = ET.fromstring(text.lstrip("\ufeff").encode("utf-8"))
        except (SourceBlocked,):
            raise
        except Exception as exc:
            raise SourceFailed(f"rss unreadable: {exc.__class__.__name__}") from exc
        urls: list[str] = []
        for item in root.iter("item"):
            link = _child(item, "link")
            if not link or self.store.has_source_url(link):
                continue
            if not self.client.allowed(link):
                continue
            self._raw[link] = ET.tostring(item, encoding="unicode")
            urls.append(link)
            if len(urls) >= CAP:
                break
        return urls

    def fetch(self, url: str) -> str:
        raw = self._raw.get(url)
        if raw is None:
            raise SourceFailed(f"rss item missing for {url}")
        if not self.client.allowed(url):
            from worker.http import Disallowed
            raise Disallowed(url)
        return raw

    def normalize(self, raw: str, url: str) -> dict | None:
        try:
            item = ET.fromstring(raw)
            full = clean(_child(item, "title"))
            if ":" in full:
                company, title = full.split(":", 1)
                company, title = clean(company), clean(title)
            else:
                company, title = "", full
            if not title:
                return None
            return {
                "title": title,
                "company": company,
                "city": clean(_child(item, "region")),
                "text": html_to_text(_child(item, "description")),
                "source_url": url,
                "source_name": self.name,
                "external_id": clean(_child(item, "guid") or url)[:200],
                "category": clean(_child(item, "category")),
                "tags": [clean(el.text or "") for el in item.findall("skills")],
                "remote": True,
            }
        except Exception:
            return None

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)


def _child(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""
