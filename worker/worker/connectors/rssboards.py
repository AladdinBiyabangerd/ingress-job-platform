"""Public RSS feeds of foreign tech job boards.

Only the feed URL and, where the feed text is short, the public listing page
(schema.org JobPosting) are read. Query-string pages are never fetched.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from worker.connectors.feed import FeedConnector, as_list, first, read_rss, text_from_html
from worker.parsing import clean


class PythonOrgJobsConnector(FeedConnector):
    name = "Python.org Jobs"
    entry_url = "https://www.python.org/jobs/feed/rss/"
    require_remote_or_relocation = True
    credit_note = "Python.org job board RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = clean(first(it.get("title")))
            title, company = (full.rsplit(", ", 1) + [""])[:2] if ", " in full else (full, "")
            desc = first(it.get("description"))
            place_line, _, body = desc.partition("\n")
            places = []
            for part in place_line.split(","):
                part = clean(part)
                if part and part not in places and "<" not in part:
                    places.append(part)
            out.append({
                "title": title,
                "company": company,
                "city": ", ".join(places[:3]),
                "text": text_from_html(body or desc),
                "source_url": first(it.get("link")),
                "external_id": (re.findall(r"/jobs/(\d+)", first(it.get("link"))) or [""])[0],
                "tags": ["Python"],
            })
        return out


_ROLE_NOISE = re.compile(
    r"(?i)\b(?:blockchain|cryptocurrency|crypto|web3|defi|nft|remote|full[\s-]time|part[\s-]time|"
    r"senior|junior|entry level|jobs?)\b"
)


class CryptoJobsListConnector(FeedConnector):
    name = "Crypto Jobs List"
    entry_url = "https://api.cryptojobslist.com/jobs.rss"
    require_remote_or_relocation = True
    credit_note = "CryptoJobsList public RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            link = first(it.get("canonical")) or first(it.get("link"))
            desc = first(it.get("description"))
            desc = re.sub(r"(?is)^\s*<img[^>]*>\s*", "", desc)
            tags = re.findall(r'<a href="https://cryptojobslist\.com/[^"]*">([^<]+)</a>', desc[:3000])
            out.append({
                "title": first(it.get("title")),
                "company": first(it.get("creator")),
                "city": clean(first(it.get("location")))[:160],
                "text": text_from_html(desc),
                "source_url": link,
                "external_id": link.rstrip("/").rsplit("/", 1)[-1],
                "tags": [t for t in tags if t.lower() != "web3 jobs"],
                # Tags read like "Web3 Ios Jobs" or "Blockchain Full Time Jobs";
                # only the role part ("Ios") is a category.
                "category": [r for r in (_ROLE_NOISE.sub(" ", t).strip() for t in tags) if r],
            })
        return out


class RealWorkFromAnywhereConnector(FeedConnector):
    name = "Real Work From Anywhere"
    entry_url = "https://www.realworkfromanywhere.com/rss.xml"
    remote_default = True
    credit_note = "Real Work From Anywhere public RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = clean(first(it.get("title")))
            company = clean(first(it.get("author")))
            title = full
            if company and full.endswith(" at " + company):
                title = full[: -len(" at " + company)]
            elif " at " in full:
                title, company = full.rsplit(" at ", 1)
            link = first(it.get("link"))
            out.append({
                "title": title,
                "company": company,
                "city": "Remote (Worldwide)",
                "text": text_from_html(first(it.get("description"))),
                "source_url": link,
                "external_id": link.rstrip("/").rsplit("-", 1)[-1],
                "remote": True,
            })
        return out


class BerlinStartupJobsConnector(FeedConnector):
    name = "Berlin Startup Jobs"
    entry_url = "https://berlinstartupjobs.com/feed/"
    detail = True
    credit_note = "Berlin Startup Jobs public RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = clean(first(it.get("title")))
            title, _, company = full.partition(" // ")
            link = first(it.get("link"))
            section = urlparse(link).path.strip("/").split("/")[0] if link else ""
            cats = as_list(it.get("category"))
            out.append({
                "title": title,
                "company": company,
                "city": "Berlin",
                "text": text_from_html(first(it.get("encoded")) or first(it.get("description"))),
                "source_url": link,
                "external_id": first(it.get("post-id")),
                "tags": cats,
                "category": [section.replace("-", " ")] + cats[:1],
            })
        return out


class GolangProjectsConnector(FeedConnector):
    name = "Golang Projects"
    entry_url = "https://www.golangprojects.com/rss.xml"
    detail = True
    credit_note = "Golangprojects.com public RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            full = clean(first(it.get("title")))
            title, _, company = full.partition(" @ ")
            desc = first(it.get("description"))
            place = clean(desc.split(" - ", 1)[0]) if " - " in desc[:80] else ""
            link = first(it.get("link"))
            out.append({
                "title": title,
                "company": company,
                "city": place,
                "text": text_from_html(desc),
                "source_url": link,
                "external_id": (re.findall(r"job-([a-z0-9]+)-", link) or [""])[0],
                "tags": ["Go"],
                "remote": True if re.search(r"(?i)remotework\.html$|^remote\b", link + " " + place) else None,
            })
        return out


class ElixirJobsConnector(FeedConnector):
    name = "Elixir Jobs"
    entry_url = "https://elixirjobs.net/rss"
    detail = True
    credit_note = "Elixir Jobs public RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            desc = text_from_html(first(it.get("description")))
            place = (re.findall(r"Job location:\s*(.+)", desc) or [""])[0]
            mode = (re.findall(r"Job place:\s*(.+)", desc) or [""])[0]
            link = first(it.get("link"))
            out.append({
                "title": first(it.get("title")),
                "company": "",
                "city": clean(place),
                "text": desc,
                "source_url": link,
                "external_id": link.rstrip("/").rsplit("-", 1)[-1],
                "tags": ["Elixir"],
                "remote": True if clean(mode).lower() == "remote" else None,
            })
        return out


class JobspressoConnector(FeedConnector):
    name = "Jobspresso"
    # WP Job Manager path feed. robots.txt blocks every "/*?" URL, so the
    # ?post_type= feed is never used.
    entry_url = "https://jobspresso.co/feed/job_feed/"
    remote_default = True
    credit_note = "Jobspresso public job RSS feed."

    def feed_items(self) -> list[dict]:
        out: list[dict] = []
        for it in read_rss(self.client, self.entry_url):
            place = clean(first(it.get("location")))
            out.append({
                "title": first(it.get("title")),
                "company": first(it.get("company")),
                "city": f"Remote ({place})" if place else "Remote",
                "text": text_from_html(first(it.get("encoded")) or first(it.get("description"))),
                "source_url": first(it.get("link")),
                "external_id": first(it.get("post-id")),
                "category": first(it.get("job_type")),
                "remote": True,
            })
        return out
