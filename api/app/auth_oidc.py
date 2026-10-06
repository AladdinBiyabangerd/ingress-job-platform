"""Verify Academy access tokens. No local password and no token logging."""

from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from app.config import settings

_jwks: PyJWKClient | None = None
_log = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class VerifiedAccess:
    subject: str
    scopes: frozenset[str]
    name: str = ""


def _jwks_client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(
            settings.oidc_jwks_url,
            cache_keys=True,
            lifespan=3600,
            timeout=3,
            headers={"User-Agent": "ingress-job-api/0.1"},
        )
    return _jwks


def verify_access_token(token: str) -> VerifiedAccess:
    if not token or len(token) > 8192 or token.count(".") != 2:
        raise AuthError(401, "Hesab tələb olunur")
    issuer = settings.issuer()
    audiences = [part.strip() for part in settings.oidc_audience.split(",") if part.strip()]
    issuers = [value for value in (issuer, issuer.rstrip("/")) if value]
    issuers = list(dict.fromkeys(issuers))
    if not issuers or not audiences or not settings.oidc_jwks_url.strip():
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
            audience=audiences if len(audiences) > 1 else audiences[0],
            issuer=issuers,
            leeway=60,
            options={"require": ["aud", "exp", "iat", "iss", "sub"]},
        )
    except (InvalidTokenError, PyJWKClientError, TimeoutError) as exc:
        token_aud = None
        try:
            token_aud = jwt.decode(
                token,
                algorithms=["RS256"],
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_exp": False,
                    "verify_iss": False,
                },
            ).get("aud")
        except InvalidTokenError:
            token_aud = None
        _log.warning(
            "access_token_rejected: %s: %s token_aud=%r expected=%r",
            type(exc).__name__,
            exc,
            token_aud,
            audiences,
        )
        raise AuthError(401, "Hesab tələb olunur") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise AuthError(401, "Hesab tələb olunur")
    scope_value = claims.get("scope") or ""
    if not isinstance(scope_value, str):
        raise AuthError(401, "Hesab tələb olunur")
    scopes = frozenset(part for part in scope_value.split() if part)
    name = claims.get("name")
    if not isinstance(name, str):
        name = ""
    return VerifiedAccess(subject=subject.strip(), scopes=scopes, name=name.strip())


def _id_token_claims(token: str, *, verify_aud: bool = True) -> dict | None:
    if not token or token.count(".") != 2:
        return None
    issuer = settings.issuer()
    audience = settings.oidc_client_id.strip()
    issuers = [value for value in (issuer, issuer.rstrip("/")) if value]
    issuers = list(dict.fromkeys(issuers))
    if not issuers or (verify_aud and not audience):
        return None
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        kwargs: dict = {
            "algorithms": ["RS256"],
            "issuer": issuers,
            "leeway": 60,
            "options": {
                "require": ["aud", "exp", "iat", "iss", "sub"] if verify_aud else ["exp", "iat", "iss", "sub"],
                "verify_aud": verify_aud,
            },
        }
        if verify_aud:
            kwargs["audience"] = audience
        return jwt.decode(token, signing_key.key, **kwargs)
    except (InvalidTokenError, PyJWKClientError, TimeoutError) as exc:
        _log.warning("id_token_rejected: verify_aud=%s %s: %s", verify_aud, type(exc).__name__, exc)
        return None


def id_token_nonce_status(token: object, nonce: str) -> str:
    """ok | mismatch | unverified. Only mismatch must fail the code grant."""
    if not isinstance(token, str) or not nonce:
        return "unverified"
    claims = _id_token_claims(token) or _id_token_claims(token, verify_aud=False)
    if not isinstance(claims, dict):
        return "unverified"
    got = claims.get("nonce")
    if not isinstance(got, str) or not hmac.compare_digest(got, nonce):
        return "mismatch"
    return "ok"


def id_token_nonce_matches(token: object, nonce: str) -> bool:
    """True when the verified Academy id_token carries this authorize nonce."""
    return id_token_nonce_status(token, nonce) == "ok"


def identity_from_id_token(token: str) -> tuple[str, str, str] | None:
    """Read the verified subject, email, and display name from an Academy id_token."""
    claims = _id_token_claims(token)
    if not isinstance(claims, dict):
        return None
    subject = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name")
    if not isinstance(subject, str):
        return None
    subject = subject.strip()
    email = email.strip() if isinstance(email, str) else ""
    if not isinstance(name, str) or not name.strip():
        first = claims.get("given_name") if isinstance(claims.get("given_name"), str) else ""
        last = claims.get("family_name") if isinstance(claims.get("family_name"), str) else ""
        name = " ".join(part.strip() for part in (first, last) if part.strip())
    name = name.strip()
    if not subject or (not email and not name):
        return None
    return subject, email, name


def email_from_id_token(token: str) -> tuple[str, str] | None:
    """Read sub and email from an Academy id_token. Access tokens do not carry email."""
    found = identity_from_id_token(token)
    if not found or not found[1]:
        return None
    return found[0], found[1]
