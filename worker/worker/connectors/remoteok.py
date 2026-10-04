"""Remote OK JSON API only. The disallowed AJAX endpoint is never called."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from worker.catalog import REMOTE_OK_CREDIT
from worker.db import Store
from worker.http import Disallowed, PoliteClient, SourceBlocked, SourceFailed
from worker.parsing import clean, html_to_text

API = "https://remoteok.com/api"
CAP = 30


class RemoteOkConnector:
    name = "Remote OK"
    entry_url = API

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store
        self._raw: dict[str, str] = {}

    def discover(self) -> list[str]:
        if "action=get_jobs" in self.entry_url:
            raise SourceBlocked("refused ?action=get_jobs")
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        try:
            payload = self.client.get_json(self.entry_url)
        except (SourceBlocked, Disallowed):
            raise
        except Exception as exc:
            raise SourceFailed(f"api unreadable: {exc.__class__.__name__}") from exc
        if not isinstance(payload, list):
            raise SourceFailed("api payload was not a list")
        legal = ""
        urls: list[str] = []
        for obj in payload:
            if not isinstance(obj, dict):
                continue
            if "position" not in obj and obj.get("legal"):
                legal = str(obj.get("legal") or "").strip()
                continue
            url = str(obj.get("url") or "").strip()
            if not _public_job_url(url):
                continue
            if self.store.has_source_url(url):
                continue
            if not self.client.allowed(url):
                continue
            self._raw[url] = json.dumps(obj, ensure_ascii=False)
            urls.append(url)
            if len(urls) >= CAP:
                break
        credit = REMOTE_OK_CREDIT
        if legal:
            credit = f"{REMOTE_OK_CREDIT}\n\n{legal}"
        self.store.set_credit_note(self.name, credit)
        self._credit = credit
        return urls

    def fetch(self, url: str) -> str:
        raw = self._raw.get(url)
        if raw is None:
            raise SourceFailed(f"api item missing for {url}")
        if not self.client.allowed(url):
            raise Disallowed(url)
        return raw

    def normalize(self, raw: str, url: str) -> dict | None:
        try:
            job = json.loads(raw)
            title = clean(job.get("position"))
            if not title:
                return None
            city = clean(job.get("location")) or "Remote"
            return {
                "title": title,
                "company": clean(job.get("company")),
                "city": city,
                "text": html_to_text(str(job.get("description") or "")),
                "source_url": url,
                "source_name": self.name,
                "external_id": clean(job.get("id") or "")[:200],
                "credit_note": getattr(self, "_credit", REMOTE_OK_CREDIT),
            }
        except Exception:
            return None

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)


def _public_job_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in {"remoteok.com", "www.remoteok.com"}:
        return False
    if "action=get_jobs" in parsed.query.lower():
        return False
    path = parsed.path.lower()
    if path.startswith("/l/") or "/l/" in path:
        return False
    return path.startswith("/remote-jobs/")
