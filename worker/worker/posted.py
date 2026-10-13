"""Source posting dates and mixed-language titles.

parse_posted() turns whatever a source gives (ISO 8601, RFC 822 pubDate,
epoch seconds/milliseconds) into the same ISO form as db.now_iso(), or ''
when the value is missing, unparseable, in the future or older than a year.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

MAX_AGE = timedelta(days=366)
FUTURE_SLACK = timedelta(hours=12)


def parse_posted(value: object, *, now: datetime | None = None) -> str:
    if value is None or value == "" or isinstance(value, bool):
        return ""
    when: datetime | None = None
    raw = str(value).strip()
    try:
        if isinstance(value, (int, float)) or re.fullmatch(r"\d{9,15}(\.\d+)?", raw):
            num = float(raw)
            if num <= 0:
                return ""
            if num > 1e11:  # milliseconds
                num /= 1000.0
            when = datetime.fromtimestamp(num, tz=timezone.utc)
        elif re.match(r"\d{4}-\d{2}-\d{2}", raw):
            text = raw.replace("Z", "+00:00").replace(" ", "T", 1)
            text = re.sub(r"(\.\d{6})\d+", r"\1", text)
            when = datetime.fromisoformat(text)
        else:
            when = parsedate_to_datetime(raw)
    except (ValueError, TypeError, OverflowError, OSError, IndexError):
        return ""
    if when is None:
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if when > now + FUTURE_SLACK or when < now - MAX_AGE:
        return ""
    return when.astimezone().isoformat(timespec="seconds")


_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]")
_LATIN = re.compile(r"[A-Za-z]")
_SPLIT = re.compile(r"\s+[/|｜／]\s+|\s*[／｜]\s*")


def _cjk_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _CJK.match(c)) / len(letters)


def latin_title(title: str) -> str:
    """'Backend Engineer / バックエンドエンジニア' -> 'Backend Engineer' (either order).

    Only splits on a separator between a Latin half and a mostly CJK half;
    anything else comes back unchanged.
    """
    text = str(title or "").strip()
    if not _CJK.search(text) or not _LATIN.search(text):
        return text
    parts = [p.strip() for p in _SPLIT.split(text) if p.strip()]
    if len(parts) < 2:
        return text
    latin = [p for p in parts if _LATIN.search(p) and not _CJK.search(p)]
    if not latin:
        return text
    tail = ""
    for part in parts:
        if _CJK.search(part):
            # "バックエンドエンジニア (Core Banking)" keeps its Latin suffix.
            found = re.search(r"(\([^()]*\))\s*$", part)
            if found and not _CJK.search(found.group(1)):
                tail = " " + found.group(1)
    return " / ".join(latin) + tail
