"""IP-first Redis rate limits with benefit-framed 429 bodies."""

from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request
from starlette.responses import JSONResponse

_IP_RE = re.compile(
    r"^(?:\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F:]+)$"
)

# bucket -> (limit, window_seconds, message_key, fail_closed_default)
BUCKETS: dict[str, tuple[int, int, str, bool]] = {
    "global": (100, 60, "rateLimit.gentle", False),
    "public_read": (40, 60, "rateLimit.gentle", False),
    "auth_tx": (15, 60, "rateLimit.signInPause", True),
    "auth_token": (30, 60, "rateLimit.signInPause", True),
    "click_unsub": (40, 60, "rateLimit.gentle", False),
    "apply_cv": (20, 3600, "rateLimit.savePause", True),
    "cabinet_create": (10, 3600, "rateLimit.postPause", True),
    "cabinet_create_day": (30, 86400, "rateLimit.postPause", True),
    "ai_burst": (10, 60, "rateLimit.gentle", True),
}

_FALLBACK_MESSAGES = {
    "rateLimit.gentle": (
        "Let’s pause briefly so the site stays fast for you. "
        "Try again in a few seconds."
    ),
    "rateLimit.signInPause": (
        "Let’s pause briefly so sign-in stays secure for you. "
        "Try again in a few seconds."
    ),
    "rateLimit.savePause": (
        "Let’s pause briefly so your application can be saved cleanly. "
        "Try again in a few seconds."
    ),
    "rateLimit.postPause": (
        "Let’s pause briefly so your listing can be reviewed properly. "
        "Try again in a few seconds."
    ),
    "rateLimit.verifyHuman": (
        "Please complete the quick security check so we can keep your "
        "account safe. Then try again."
    ),
}

_memory_lock = threading.Lock()
_memory: dict[str, tuple[int, float]] = {}
_redis_client: Any = None
_redis_failed = False


def rate_limit_enabled() -> bool:
    raw = (os.environ.get("RATE_LIMIT_ENABLED") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool((os.environ.get("RAILWAY_ENVIRONMENT") or "").strip())


def _fail_closed_env() -> bool:
    raw = (os.environ.get("RATE_LIMIT_FAIL_CLOSED") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _redis_url() -> str:
    try:
        from app.config import settings

        return (settings.redis_url or os.environ.get("REDIS_URL") or "").strip()
    except Exception:
        return (os.environ.get("REDIS_URL") or "").strip()


def _get_redis():
    global _redis_client, _redis_failed
    if _redis_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        _redis_client = redis.Redis.from_url(url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        _redis_failed = True
        print(f"rate_limit: redis unavailable ({exc})", flush=True)
        return None


def reset_rate_limit_state_for_tests() -> None:
    """Clear in-memory counters and redis client cache (unit tests)."""
    global _redis_client, _redis_failed
    with _memory_lock:
        _memory.clear()
    _redis_client = None
    _redis_failed = False


def client_ip(request: Request) -> str:
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf and _IP_RE.match(cf) and len(cf) < 64:
        return cf
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def slow_down_payload(message_key: str, retry_after: int) -> dict:
    key = message_key if message_key in _FALLBACK_MESSAGES else "rateLimit.gentle"
    return {
        "error": "slow_down",
        "message_key": key,
        "retry_after_seconds": max(1, int(retry_after)),
        "message": _FALLBACK_MESSAGES[key],
    }


class SlowDown(Exception):
    """Raised for rate limits; handler returns flat benefit-framed JSON."""

    def __init__(self, message_key: str = "rateLimit.gentle", retry_after: int = 60, *, status: int = 429):
        self.message_key = message_key
        self.retry_after = max(1, int(retry_after))
        self.status = status
        self.payload = slow_down_payload(message_key, self.retry_after)


def raise_slow_down(message_key: str = "rateLimit.gentle", retry_after: int = 60) -> None:
    raise SlowDown(message_key, retry_after)


def slow_down_response(message_key: str = "rateLimit.gentle", retry_after: int = 60) -> JSONResponse:
    payload = slow_down_payload(message_key, retry_after)
    return JSONResponse(
        status_code=429,
        content=payload,
        headers={"Retry-After": str(payload["retry_after_seconds"])},
    )


def _incr_memory(key: str, window_s: int) -> tuple[int, int]:
    now = time.time()
    with _memory_lock:
        count, expires = _memory.get(key, (0, now + window_s))
        if now >= expires:
            count, expires = 0, now + window_s
        count += 1
        _memory[key] = (count, expires)
        retry = max(1, int(expires - now))
        return count, retry


def _incr_redis(client: Any, key: str, window_s: int) -> tuple[int, int]:
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = pipe.execute()
    if ttl is None or int(ttl) < 0:
        client.expire(key, window_s)
        ttl = window_s
    return int(count), max(1, int(ttl))


def check_rate(
    bucket: str,
    identity: str,
    *,
    fail_closed: bool | None = None,
) -> None:
    if not rate_limit_enabled():
        return
    meta = BUCKETS.get(bucket)
    if meta is None:
        return
    limit, window_s, message_key, bucket_fail_closed = meta
    closed = bucket_fail_closed if fail_closed is None else fail_closed
    if _fail_closed_env() and bucket_fail_closed:
        closed = True

    key = f"rl:{bucket}:{identity}"
    client = _get_redis()
    try:
        if client is not None:
            count, retry = _incr_redis(client, key, window_s)
        else:
            if closed and _redis_url():
                raise SlowDown(message_key, 30, status=503)
            count, retry = _incr_memory(key, window_s)
    except SlowDown:
        raise
    except Exception as exc:
        print(f"rate_limit: check failed bucket={bucket} ({exc})", flush=True)
        if closed:
            raise SlowDown(message_key, 30, status=503) from exc
        return

    if count > limit:
        print(f"rate_limit: exceeded bucket={bucket} id={identity}", flush=True)
        raise_slow_down(message_key, retry)


def limit_ip(bucket: str) -> Callable:
    async def _dep(request: Request) -> None:
        check_rate(bucket, client_ip(request))

    return _dep


def limit_user(bucket: str) -> Callable:
    """Rate limit by JWT subject when present; else IP."""

    async def _dep(request: Request) -> None:
        subject = ""
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token:
                try:
                    from app.account import verify_access_token

                    user = verify_access_token(token)
                    subject = str(getattr(user, "subject", "") or "").strip()
                except Exception:
                    subject = ""
        check_rate(bucket, subject or client_ip(request))

    return _dep


class RateLimitMiddleware:
    """Global IP budget for all HTTP requests (skips health/OPTIONS)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not rate_limit_enabled():
            await self.app(scope, receive, send)
            return
        method = scope.get("method") or "GET"
        path = scope.get("path") or "/"
        if method == "OPTIONS" or path in {"/health", "/api/v1/health", "/api/health"}:
            await self.app(scope, receive, send)
            return

        # Build a minimal Request for IP extraction.
        request = Request(scope, receive=receive)
        try:
            check_rate("global", client_ip(request), fail_closed=False)
        except SlowDown as exc:
            response = JSONResponse(
                status_code=exc.status,
                content=exc.payload,
                headers={"Retry-After": str(exc.retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


# FastAPI Depends helpers (sync wrappers for sync routes)
def dep_ip(bucket: str):
    def _inner(request: Request) -> None:
        check_rate(bucket, client_ip(request))

    return Depends(_inner)


def dep_user(bucket: str):
    def _inner(request: Request) -> None:
        subject = ""
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token:
                try:
                    from app.account import verify_access_token

                    user = verify_access_token(token)
                    subject = str(getattr(user, "subject", "") or "").strip()
                except Exception:
                    subject = ""
        check_rate(bucket, subject or client_ip(request))

    return Depends(_inner)
