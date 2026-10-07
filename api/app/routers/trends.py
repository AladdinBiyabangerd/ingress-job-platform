"""Public skill trends API (plan §7.1 / §13)."""

from fastapi import APIRouter, Header, HTTPException, Query

from app.trends import (
    MAX_DETAIL_JOBS,
    MAX_LIMIT,
    MAX_WINDOW_DAYS,
    get_trend_detail,
    list_trends,
)

router = APIRouter(prefix="/api/v1", tags=["trends"])


def _optional_user_id(authorization: str | None) -> str | None:
    """Best-effort subject for personalized you-vs-trend; never 401 on public detail."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        # Import via account so tests that patch account.verify_access_token apply.
        from app.account import verify_access_token

        user = verify_access_token(token)
    except Exception:
        return None
    scopes = getattr(user, "scopes", frozenset()) or frozenset()
    if "job:candidate" not in scopes and "job:staff" not in scopes:
        return None
    return str(user.subject or "").strip() or None


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


@router.get("/trends/{skill_id}")
def read_trend_detail(
    skill_id: int,
    category: str | None = Query(default=None, max_length=80),
    region: str | None = Query(default=None, max_length=80),
    window_days: int | None = Query(default=None, ge=1, le=MAX_WINDOW_DAYS),
    jobs_limit: int | None = Query(default=None, ge=0, le=MAX_DETAIL_JOBS),
    jobs_page: int | None = Query(default=None, ge=1, le=10000),
    lang: str | None = Query(default=None, max_length=8),
    authorization: str | None = Header(default=None),
) -> dict:
    """Single skill market detail, paginated jobs, and optional you-vs-trend."""
    payload = get_trend_detail(
        skill_id=skill_id,
        category=category,
        region=region,
        window_days=window_days,
        jobs_limit=jobs_limit,
        jobs_page=jobs_page,
        lang=lang,
        user_id=_optional_user_id(authorization),
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return payload
