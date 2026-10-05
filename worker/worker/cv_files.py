"""Read CV bytes for parse_cv_queue drain.

Local files when bucket credentials are absent (same as the API).
When BUCKET_* is set, reads from the S3-compatible bucket under cvs/.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

_STORED = re.compile(r"^[a-f0-9]{32}\.(?:pdf|doc|docx)$")


def _clean(name: str) -> str:
    return os.environ.get(name, "").strip()


def cv_root() -> Path:
    configured = _clean("CV_ROOT")
    if configured:
        return Path(configured)
    # Repo layout: worker/worker/cv_files.py → repo/api/data/cvs
    return Path(__file__).resolve().parents[2] / "api" / "data" / "cvs"


def object_key(stored: str) -> str:
    return f"cvs/{stored}"


def bucket_config() -> dict | None:
    name = _clean("BUCKET_NAME")
    access_key = _clean("BUCKET_ACCESS_KEY")
    secret_key = _clean("BUCKET_SECRET_KEY")
    if not name or not access_key or not secret_key:
        return None
    return {
        "bucket_name": name,
        "access_key": access_key,
        "secret_key": secret_key,
        "region_name": _clean("BUCKET_REGION") or "auto",
        "endpoint_url": _clean("BUCKET_ENDPOINT").rstrip("/"),
    }


@lru_cache(maxsize=1)
def _client():
    config = bucket_config()
    if config is None:
        return None
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"],
        region_name=config["region_name"],
        endpoint_url=config["endpoint_url"] or None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=20,
            retries={"max_attempts": 2},
        ),
    )


def read_cv(stored: str, *, root: Path | None = None) -> bytes | None:
    """Return CV bytes for a stored filename, or None when missing/invalid."""
    if not _STORED.fullmatch(stored or ""):
        return None
    if bucket_config() is not None:
        client = _client()
        config = bucket_config()
        if client is not None and config is not None:
            from botocore.exceptions import ClientError

            try:
                response = client.get_object(
                    Bucket=config["bucket_name"], Key=object_key(stored)
                )
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in {"NoSuchKey", "404", "NotFound"}:
                    return None
                raise
            body = response["Body"].read()
            return body if isinstance(body, bytes) else None
    base = (root or cv_root()).resolve()
    path = (base / stored).resolve()
    if path.parent != base or not path.is_file():
        return None
    return path.read_bytes()
