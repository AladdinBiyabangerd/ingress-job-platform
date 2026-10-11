import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from app.observability import init_observability, otel_enabled
from app.rate_limit import RateLimitMiddleware, SlowDown
from app.runtime_env import load_local_env
from app.routers import (
    admin,
    applications,
    cabinet,
    companies,
    consents,
    email_prefs,
    health,
    jobs,
    linkedin_import,
    me,
    notifications,
    profile,
    talent,
    trends,
)
from app.account import router as account_router

load_local_env(Path(__file__).resolve().parents[1] / ".env")
init_observability("ingress-job-api")


def _debug() -> bool:
    raw = (os.environ.get("DEBUG") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return not bool((os.environ.get("RAILWAY_ENVIRONMENT") or "").strip())


def _allowed_hosts() -> list[str] | None:
    raw = (os.environ.get("ALLOWED_HOSTS") or "").strip()
    if not raw:
        return None
    return [h.strip() for h in raw.split(",") if h.strip()]


def _log_push_vapid_status() -> None:
    """Startup line so Railway logs show whether Web Push env is present."""
    try:
        from app.push import vapid_configured, vapid_missing_names

        if vapid_configured():
            print("push vapid: configured=True", flush=True)
        else:
            missing = ",".join(vapid_missing_names()) or "(unknown)"
            print(f"push vapid: configured=False missing={missing}", flush=True)
    except Exception as exc:
        print(f"push vapid: status check failed ({exc})", flush=True)


_log_push_vapid_status()


def _origins() -> list[str]:
    origins = [
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]
    for item in os.environ.get("CORS_ORIGINS", "").split(","):
        value = item.strip().rstrip("/")
        if value and value not in origins:
            origins.append(value)
    return origins


class RequestTrace:
    """Record method, path, and status. Query strings and headers are not attributes."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not otel_enabled():
            await self.app(scope, receive, send)
            return
        from opentelemetry import trace
        from opentelemetry.trace import SpanKind, Status, StatusCode

        method = scope.get("method") or "GET"
        path = scope.get("path") or "/"
        status_code = 500
        with trace.get_tracer("ingress-job-api").start_as_current_span(
            f"{method} {path}",
            kind=SpanKind.SERVER,
        ) as current:
            async def send_wrapper(message):
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = int(message["status"])
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                current.set_status(Status(StatusCode.ERROR))
                raise
            current.set_attribute("http.response.status_code", status_code)
            if status_code >= 500:
                current.set_status(Status(StatusCode.ERROR))


_docs = "/docs" if _debug() else None
app = FastAPI(
    title="Ingress Job",
    version="0.0.1",
    docs_url=_docs,
    redoc_url="/redoc" if _debug() else None,
    openapi_url="/openapi.json" if _debug() else None,
)


@app.exception_handler(SlowDown)
async def _slow_down_handler(_request: Request, exc: SlowDown) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content=exc.payload,
        headers={"Retry-After": str(exc.retry_after)},
    )


_MAX_BODY = int((os.environ.get("MAX_REQUEST_BODY_BYTES") or str(6 * 1024 * 1024)).strip() or 0) or (
    6 * 1024 * 1024
)


class LimitBodySize:
    """Reject oversized Content-Length before the app reads the body."""

    def __init__(self, app, max_bytes: int = _MAX_BODY):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            for key, value in scope.get("headers") or []:
                if key == b"content-length":
                    try:
                        length = int(value.decode("latin1"))
                    except ValueError:
                        length = 0
                    if length > self.max_bytes:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "error": "slow_down",
                                "message_key": "rateLimit.gentle",
                                "retry_after_seconds": 60,
                                "message": "Please send a smaller file so we can process it reliably.",
                            },
                        )
                        await response(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)


# Last added runs first: RateLimit → Body → TrustedHost → CORS → RequestTrace → app
app.add_middleware(RequestTrace)
app.add_middleware(LimitBodySize)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_origin_regex=r"^chrome-extension://[a-z]{32}$",
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
_hosts = _allowed_hosts()
if _hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)
app.add_middleware(RateLimitMiddleware)
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(trends.router)
app.include_router(companies.router)
app.include_router(account_router)
app.include_router(cabinet.router)
app.include_router(admin.router)
app.include_router(linkedin_import.router)
app.include_router(applications.router)
app.include_router(talent.router)
app.include_router(consents.router)
app.include_router(email_prefs.router)
app.include_router(profile.router)
app.include_router(me.router)
app.include_router(notifications.router)
