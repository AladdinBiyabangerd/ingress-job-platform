"""Public company directory built from the visible jobs. Counts only, no applicant data."""

from fastapi import APIRouter, HTTPException, Query

from app.companies import SORTS
from app.sqlite_jobs import query_companies, query_company

router = APIRouter(prefix="/api/v1", tags=["companies"])


@router.get("/companies")
def read_companies(
    q: str = Query("", max_length=100),
    sort: str = Query("jobs"),
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(24, ge=1, le=60),
) -> dict:
    return query_companies(
        q=q.strip(),
        sort=sort if sort in SORTS else "jobs",
        page=page,
        per_page=per_page,
    )


@router.get("/companies/{slug}")
def read_company(
    slug: str,
    page: int = Query(1, ge=1, le=10000),
    per_page: int = Query(20, ge=1, le=60),
) -> dict:
    found = query_company(slug.strip().lower()[:120], page=page, per_page=per_page)
    if found is None:
        raise HTTPException(status_code=404, detail="Şirkət tapılmadı")
    return found
