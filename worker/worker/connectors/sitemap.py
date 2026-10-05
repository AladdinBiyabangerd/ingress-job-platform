"""Small shared limits and URL checks for the list-based connectors."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Candidate URLs one pass may look at per source. New ads are capped separately (30).
CANDIDATES = 80


def path_is(url: str, pattern: str) -> bool:
    return re.fullmatch(pattern, urlparse(url).path) is not None
