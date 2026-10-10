"""Temporary product-surface gates (recommendations + roadmap).

Unset / empty → off. Set to 1/true/on to re-enable.
API tests force both on via api/tests/__init__.py.
"""

from __future__ import annotations

import os

_FALSE = {"0", "false", "no", "off"}
_TRUE = {"1", "true", "yes", "on"}


def _env_on(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in _FALSE:
        return False
    if raw in _TRUE:
        return True
    return False


def recommendations_enabled() -> bool:
    """Candidate recommendations hub + related HTTP surfaces."""
    return _env_on("PRODUCT_RECOMMENDATIONS_ENABLED")


def roadmap_enabled() -> bool:
    """Learning roadmap / insights hub + coach_weekly growth fanout."""
    return _env_on("PRODUCT_ROADMAP_ENABLED")
