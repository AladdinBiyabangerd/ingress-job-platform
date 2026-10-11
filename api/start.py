"""Start uvicorn using the PORT env var. Railway start commands do not expand $PORT."""

import os

import uvicorn


def listen_port() -> int:
    raw = str(os.environ.get("PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 8080 if os.environ.get("RAILWAY_ENVIRONMENT") else 8010


def _forwarded_allow_ips() -> str:
    # Never use "*". Comma-separated trusted proxy IPs/CIDRs (Cloudflare / Railway).
    raw = (os.environ.get("FORWARDED_ALLOW_IPS") or "").strip()
    if raw:
        return raw
    return "127.0.0.1"


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="::",
        port=listen_port(),
        proxy_headers=True,
        forwarded_allow_ips=_forwarded_allow_ips(),
    )
