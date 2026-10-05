import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.observability import init_observability, otel_enabled
from app.runtime_env import load_local_env
from app.routers import admin, applications, cabinet, companies, consents, health, jobs, me, notifications, profile, trends
from app.account import router as account_router

load_local_env(Path(__file__).resolve().parents[1] / ".env")
init_observability("ingress-job-api")

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


app = FastAPI(title="Ingress Job", version="0.0.1")
app.add_middleware(RequestTrace)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(trends.router)
app.include_router(companies.router)
app.include_router(account_router)
app.include_router(cabinet.router)
app.include_router(admin.router)
app.include_router(applications.router)
app.include_router(consents.router)
app.include_router(profile.router)
app.include_router(me.router)
app.include_router(notifications.router)
