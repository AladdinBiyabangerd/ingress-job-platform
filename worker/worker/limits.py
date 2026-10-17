"""How many new ads one source may save per pass, and how long one pass may run.

New ads per source per pass (the runner stops a source once it has *created*
this many; updates and rejects do not count):

1. ``catalog.MAX_NEW_OVERRIDES[name]`` when set (Reed and Jooble stay at 30:
   their monthly request budgets are sized for that);
2. otherwise the connector's own ``create_cap`` when it sets one (hand-tuned
   sources such as Djinni or Himalayas);
3. otherwise the tier default, configurable by environment variable:

   ========  ==============================  =======  ===============================
   tier      sources                         default  variable
   ========  ==============================  =======  ===============================
   api       official APIs, ATS boards        150      ``MAX_NEW_PER_SOURCE``
   feed      RSS / JSON feeds                 100      ``MAX_NEW_PER_SOURCE_FEED``
   html      HTML pages read one by one        50      ``MAX_NEW_PER_SOURCE_HTML``
   ========  ==============================  =======  ===============================

Politeness does not depend on the cap: PoliteClient keeps >= 1 s between
requests per host (one shared lock per host across all sources), and every
source still has its wall-clock budget (runner.source_budget). The whole
pass has a budget too (``PASS_TIME_BUDGET_SECONDS``, default 50 minutes) so
an hourly pass always ends before the next one starts.
"""

from __future__ import annotations

import os

TIER_DEFAULTS = {"api": 150, "feed": 100, "html": 50}
TIER_ENV = {
    "api": "MAX_NEW_PER_SOURCE",
    "feed": "MAX_NEW_PER_SOURCE_FEED",
    "html": "MAX_NEW_PER_SOURCE_HTML",
}
# The old single cap, kept for sources without a catalog row (tests, probes).
LEGACY_CAP = 30
MAX_CAP = 1000

PASS_BUDGET_ENV = "PASS_TIME_BUDGET_SECONDS"
PASS_BUDGET_DEFAULT = 50 * 60
PASS_BUDGET_MIN = 5 * 60


def _env_int(name: str, default: int, *, low: int, high: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(high, value))


def tier_cap(tier: str) -> int:
    default = TIER_DEFAULTS.get(tier, LEGACY_CAP)
    env = TIER_ENV.get(tier)
    return _env_int(env, default, low=1, high=MAX_CAP) if env else default


def source_tier(name: str) -> str | None:
    """api / feed / html for a catalog source, None when it has no row."""
    from worker.catalog import HTML_SOURCES, SOURCES

    if name in HTML_SOURCES:
        return "html"
    for row in SOURCES:
        if row["name"] == name:
            kind = str(row.get("connector") or "")
            if kind in {"official_api", "json_api"}:
                return "api"
            if kind == "rss":
                return "feed"
            return "html"
    return None


def max_new(connector) -> int:
    """New ads this connector may save in one pass (see module docstring)."""
    from worker.catalog import MAX_NEW_OVERRIDES

    name = str(getattr(connector, "name", "") or "")
    if name in MAX_NEW_OVERRIDES:
        return int(MAX_NEW_OVERRIDES[name])
    own = getattr(type(connector), "create_cap", None)
    if own is None:
        own = getattr(connector, "__dict__", {}).get("create_cap")
    if own:
        return int(own)
    tier = source_tier(name)
    return tier_cap(tier) if tier else LEGACY_CAP


def pass_budget() -> int:
    """Seconds one pass may spend starting and running sources."""
    return _env_int(PASS_BUDGET_ENV, PASS_BUDGET_DEFAULT, low=PASS_BUDGET_MIN, high=24 * 3600)
