"""User text inside SQL LIKE: %, _ and \\ are literal, not wildcards.

Use with ``LIKE ? ESCAPE '\\'`` (LIKE_ESCAPE). Works on SQLite and Postgres
(standard_conforming_strings, the default, keeps '\\' a one-char literal).
"""

LIKE_ESCAPE = "ESCAPE '\\'"


def escape_like(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def like_contains(value: str) -> str:
    return f"%{escape_like(value)}%"
