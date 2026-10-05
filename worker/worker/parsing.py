"""Small defensive parsers shared by connectors."""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, Comment, Declaration, Doctype, NavigableString, ProcessingInstruction, Tag

_WS = re.compile(r"\s+")
_ZW = re.compile(r"[\u200b\u200c\u200d\ufeff]")


def clean(value: object) -> str:
    text = unescape(str(value or ""))
    text = _ZW.sub("", text).replace("\xa0", " ")
    return _WS.sub(" ", text).strip()


_BLOCK_TAGS = frozenset(
    "p div section article header footer main aside blockquote pre table thead tbody tfoot tr "
    "dl dt dd figure figcaption form fieldset address center details summary".split()
)
_CELL_TAGS = frozenset(("td", "th"))
_HEADING_TAGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))
_LIST_TAGS = frozenset(("ul", "ol", "menu"))
_BOLD_TAGS = frozenset(("strong", "b"))
_SKIP_TAGS = frozenset(("script", "style", "noscript", "template", "svg", "img", "button", "input", "select", "textarea", "iframe"))
_HAS_STRUCTURE = re.compile(r"<\s*(?:p|div|br|li|ul|ol|h[1-6]|table|tr|section|article)\b", re.I)
_RULE_LINE = re.compile(r"^[-_=*~•.\s]{3,}$")


class _Lines:
    """Collects inline text into lines; blank lines separate blocks."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.cur: list[str] = []
        self.bold_only = True
        self.prefix = ""
        self.depth = 0
        self.after_br = False

    def text(self, value: str, bold: bool) -> None:
        if not value:
            return
        if value.strip():
            self.after_br = False
            if not bold:
                self.bold_only = False
        self.cur.append(value)

    def br(self) -> None:
        # One <br> ends a line; <br><br> (an empty line) ends a paragraph.
        if self.after_br and not "".join(self.cur).strip():
            self.blank()
        else:
            self.end_line()
        self.after_br = True

    def end_line(self) -> None:
        line = _WS.sub(" ", "".join(self.cur)).strip()
        self.cur = []
        bold_only, self.bold_only = self.bold_only, True
        if not line:
            return
        if _RULE_LINE.match(line):
            self.blank()
            return
        if not re.search(r"\w", line):
            return
        if self.prefix:
            line = self.prefix + line
            self.prefix = ""
        elif bold_only and self.depth == 0 and len(line) <= 90 and not re.search(r"[.!?:;,]$", line):
            # A line that is only bold text reads as a section heading.
            line += ":"
        self.lines.append(line)

    def blank(self) -> None:
        self.end_line()
        if self.lines and self.lines[-1] != "":
            self.lines.append("")

    def block(self) -> None:
        if self.depth:
            self.end_line()
        else:
            self.blank()

    def result(self) -> str:
        self.end_line()
        out = "\n".join(self.lines).strip()
        return re.sub(r"\n{3,}", "\n\n", out)


def _walk(node, out: _Lines, bold: bool, keep_newlines: bool) -> None:
    for child in node.children:
        if isinstance(child, (Comment, Doctype, ProcessingInstruction, Declaration)):
            continue
        if isinstance(child, NavigableString):
            value = _ZW.sub("", str(child)).replace("\xa0", " ")
            if keep_newlines and "\n" in value:
                parts = re.split(r"\n", value)
                for index, part in enumerate(parts):
                    if index:
                        if not part.strip() and index < len(parts) - 1:
                            out.blank()
                        else:
                            out.end_line()
                    out.text(part, bold)
            else:
                out.text(value, bold)
            continue
        if not isinstance(child, Tag):
            continue
        name = (child.name or "").lower()
        if name in _SKIP_TAGS:
            continue
        if name == "br":
            out.br()
            continue
        if name == "hr":
            out.blank()
            continue
        if name in _HEADING_TAGS:
            out.block()
            heading = _WS.sub(" ", child.get_text(" ", strip=True)).strip()
            if heading:
                if out.depth == 0 and not re.search(r"[.!?:;]$", heading):
                    heading += ":"
                out.lines.append(out.prefix + heading)
                out.prefix = ""
            out.block()
            continue
        if name in _LIST_TAGS:
            out.block()
            out.depth += 1
            number = 0
            for item in child.children:
                if isinstance(item, Tag) and (item.name or "").lower() == "li":
                    number += 1
                    out.end_line()
                    out.prefix = f"{number}. " if name == "ol" else "• "
                    _walk(item, out, bold, keep_newlines)
                    out.end_line()
                    out.prefix = ""
                elif isinstance(item, Tag):
                    _walk(item, out, bold, keep_newlines)
                elif str(item).strip():
                    out.text(str(item), bold)
            out.depth -= 1
            out.block()
            continue
        if name == "li":
            out.end_line()
            out.prefix = "• "
            _walk(child, out, bold, keep_newlines)
            out.end_line()
            out.prefix = ""
            continue
        if name in _CELL_TAGS:
            if out.cur and "".join(out.cur).strip():
                out.text(" · ", bold)
            _walk(child, out, bold, keep_newlines)
            continue
        if name in _BLOCK_TAGS:
            out.block()
            _walk(child, out, bold, keep_newlines)
            out.block()
            continue
        _walk(child, out, bold or name in _BOLD_TAGS, keep_newlines)


def html_to_text(fragment: str, limit: int = 20000) -> str:
    """Readable plain text from an HTML description.

    Inline tags (strong, a, em, span) stay inside their sentence, block tags
    become paragraphs separated by a blank line, list items become "• " or
    "1. " lines and bold-only lines / h1-h6 become "Heading:" lines. Plain text
    without HTML structure keeps its own line breaks.
    """
    raw = fragment or ""
    soup = BeautifulSoup(raw, "html.parser")
    out = _Lines()
    _walk(soup, out, False, keep_newlines=not _HAS_STRUCTURE.search(raw))
    return out.result()[:limit]


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
    category = job.get("occupationalCategory") or job.get("category") or ""
    skills = job.get("skills") or job.get("keywords") or []
    return {
        "title": title,
        "company": company,
        "city": address_locality(job.get("jobLocation")),
        "text": html_to_text(str(job.get("description") or "")),
        "external_id": external_id,
        # The source's own labels; the runner maps them to a normalized category.
        "category": category if isinstance(category, (str, list)) else "",
        "tags": skills if isinstance(skills, (str, list)) else [],
    }
