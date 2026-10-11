"""Cloudflare Turnstile server-side verification."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app.rate_limit import SlowDown


def turnstile_secret() -> str:
    return (os.environ.get("TURNSTILE_SECRET_KEY") or "").strip()


def turnstile_required() -> bool:
    """When secret is set, protected routes must present a valid token."""
    return bool(turnstile_secret())


def verify_turnstile_token(token: str | None, *, remoteip: str | None = None) -> bool:
    secret = turnstile_secret()
    if not secret:
        return True
    response = (token or "").strip()
    if not response:
        return False
    data = {"secret": secret, "response": response}
    if remoteip:
        data["remoteip"] = remoteip
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError):
        return False
    return bool(payload.get("success") is True)


def require_turnstile_token(token: str | None, *, remoteip: str | None = None) -> None:
    if not turnstile_required():
        return
    if verify_turnstile_token(token, remoteip=remoteip):
        return
    raise SlowDown("rateLimit.verifyHuman", 30, status=403)
