"""S3-compatible CV storage. Local files are used when bucket credentials are absent.

Same variable names as ingress-academy: BUCKET_NAME, BUCKET_ACCESS_KEY,
BUCKET_SECRET_KEY, BUCKET_REGION, BUCKET_ENDPOINT. Academy switches the default
file backend to storages.backends.s3boto3.S3Boto3Storage only when BUCKET_NAME
is set, and it uses path-style addressing on a private bucket.
"""

from __future__ import annotations

import os
from functools import lru_cache


def _clean(name: str) -> str:
    return os.environ.get(name, "").strip()


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


def put_object(key: str, data: bytes, content_type: str) -> None:
    config = bucket_config()
    client = _client()
    if config is None or client is None:
        raise RuntimeError("bucket is not configured")
    client.put_object(
        Bucket=config["bucket_name"],
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def get_object(key: str) -> bytes | None:
    config = bucket_config()
    client = _client()
    if config is None or client is None:
        return None
    from botocore.exceptions import ClientError

    try:
        response = client.get_object(Bucket=config["bucket_name"], Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise
    body = response["Body"].read()
    return body if isinstance(body, bytes) else None


def delete_object(key: str) -> None:
    config = bucket_config()
    client = _client()
    if config is None or client is None:
        return
    client.delete_object(Bucket=config["bucket_name"], Key=key)
