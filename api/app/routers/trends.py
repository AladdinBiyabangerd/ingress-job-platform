"""Public skill trends API (plan §7.1 / §13)."""

from fastapi import APIRouter, Query

from app.trends import MAX_LIMIT, MAX_WINDOW_DAYS, list_trends

router = APIRouter(prefix="/api/v1", tags=["trends"])


@router.get("/trends")
def read_trends(
    category: str | None = Query(default=None, max_length=80),
    region: str | None = Query(default=None, max_length=80),
    limit: int | None = Query(default=None, ge=1, le=MAX_LIMIT),
    window_days: int | None = Query(default=None, ge=1, le=MAX_WINDOW_DAYS),
    lang: str | None = Query(default=None, max_length=8),
) -> dict:
    """Skill demand share and week-over-week growth from crawled jobs."""
    return list_trends(
        category=category,
        region=region,
        limit=limit,
        window_days=window_days,
        lang=lang,
    )
