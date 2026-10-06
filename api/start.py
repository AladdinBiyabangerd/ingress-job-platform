"""Start uvicorn using the PORT env var. Railway start commands do not expand $PORT."""

import os

import uvicorn


def listen_port() -> int:
    raw = str(os.environ.get("PORT") or "").strip()
    if raw.isdigit():
        return int(raw)
    return 8080 if os.environ.get("RAILWAY_ENVIRONMENT") else 8010


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="::", port=listen_port(), proxy_headers=True)
