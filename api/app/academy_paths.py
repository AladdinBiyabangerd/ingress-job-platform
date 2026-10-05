"""Ingress Academy career-path URL helper (plan §7.2 cross-sell).

Path IDs live on role_taxonomy.academy_career_path_id (worker-seeded).
"""

from __future__ import annotations

import os
from urllib.parse import urlencode

ACADEMY_CAREER_PATH_BASE = (
    os.environ.get("ACADEMY_CAREER_PATH_BASE")
    or os.environ.get("NEXT_PUBLIC_ACADEMY_CAREER_PATH_BASE")
    or "https://ingress.academy/career-paths/"
).rstrip("/") + "/"


def academy_career_path_url(path_id: str, *, utm_medium: str = "skill_gap") -> str:
    slug = str(path_id or "").strip().strip("/")
    if not slug:
        return ""
    qs = urlencode(
        {
            "utm_source": "ingress_job",
            "utm_medium": utm_medium,
            "utm_campaign": "academy_cross_sell",
        }
    )
    return f"{ACADEMY_CAREER_PATH_BASE}{slug}/?{qs}"
