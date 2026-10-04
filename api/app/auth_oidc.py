"""Verify Academy access tokens. No local password and no token logging."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from app.config import settings

_jwks: PyJWKClient | None = None


class AuthError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class VerifiedAccess:
    subject: str
    scopes: frozenset[str]


def _jwks_client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(
            settings.oidc_jwks_url,
            cache_keys=True,
            lifespan=300,
            timeout=3,
            headers={"User-Agent": "ingress-job-api/0.1"},
        )
    return _jwks


def verify_access_token(token: str) -> VerifiedAccess:
    if not token or len(token) > 8192 or token.count(".") != 2:
        raise AuthError(401, "Hesab tələb olunur")
    issuer = settings.issuer()
    audience = settings.oidc_audience.strip()
    if not issuer or not audience or not settings.oidc_jwks_url.strip():
        raise AuthError(503, "OIDC konfiqurasiyası tam deyil")
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        raise AuthError(401, "Hesab tələb olunur") from exc
    if str(header.get("typ") or "").lower() != "at+jwt":
        raise AuthError(401, "Hesab tələb olunur")
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={"require": ["aud", "exp", "iat", "iss", "sub"]},
        )
    except (InvalidTokenError, PyJWKClientError, TimeoutError) as exc:
        raise AuthError(401, "Hesab tələb olunur") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise AuthError(401, "Hesab tələb olunur")
    scope_value = claims.get("scope") or ""
    if not isinstance(scope_value, str):
        raise AuthError(401, "Hesab tələb olunur")
    scopes = frozenset(part for part in scope_value.split() if part)
    return VerifiedAccess(subject=subject.strip(), scopes=scopes)


def email_from_id_token(token: str) -> tuple[str, str] | None:
    """Read sub and email from an Academy id_token. Access tokens do not carry email."""
    if not token or token.count(".") != 2:
        return None
    issuer = settings.issuer()
    audience = settings.oidc_client_id.strip()
    if not issuer or not audience:
        return None
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={"require": ["aud", "exp", "iat", "iss", "sub"]},
        )
    except (InvalidTokenError, PyJWKClientError, TimeoutError):
        return None
    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not isinstance(email, str):
        return None
    subject = subject.strip()
    email = email.strip()
    if not subject or not email:
        return None
    return subject, email
