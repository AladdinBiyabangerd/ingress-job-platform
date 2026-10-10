"""Who the caller is, and whether the employer profile gate is still open."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.auth_oidc import AuthError, VerifiedAccess, id_token_nonce_status, verify_access_token
from app.config import settings
from app.profiles import (
    academy_name_for,
    account_fields_for,
    candidate_profile_for,
    contact_email_for,
    profile_for,
    remember_academy_name,
    save_candidate_profile,
    save_profile,
    save_transaction,
    take_transaction,
)

router = APIRouter(prefix="/api/v1", tags=["account"])

_SAFE_RETURN = re.compile(
    r"^/(?:(?:en|ru)(?:/jobs/\d+|/post|/company|/admin|/applications|/saved|/talent|/profile(?:/review)?|/me/(?:recommendations|skills)|/settings/emails|/notifications|/trends(?:/\d+)?)?|jobs/\d+|post|company|admin|applications|saved|talent|profile(?:/review)?|me/(?:recommendations|skills)|settings/emails|notifications|trends(?:/\d+)?)?$"
)
_INTENTS = {"", "job_employer", "job_candidate"}
_STATE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_VERIFIER = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


def current_user(authorization: str | None = Header(default=None)) -> VerifiedAccess:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Hesab tələb olunur")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return verify_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


def _remember_access_identity(user: VerifiedAccess) -> None:
    """Persist display name from the access token so /me survives refresh without id_token."""
    name = (user.name or "").strip()
    if name:
        remember_academy_name(user.subject, name)


def account_payload(user: VerifiedAccess, *, lang: str | None = None) -> dict:
    from app.cabinet_store import _LOCK, _connect
    from app.consents import consents_payload
    from app.notifications import unread_count_on

    _remember_access_identity(user)
    fields = account_fields_for(user.subject)
    profile = fields["company_profile"]
    candidate_profile = fields["candidate_profile"]
    employer = "job:employer" in user.scopes
    candidate = "job:candidate" in user.scopes
    staff = "job:staff" in user.scopes
    name = (user.name or "").strip() or fields["academy_name"]
    email = (candidate_profile.get("email") or "").strip() or fields["contact_email"]
    unread = 0
    consents = None
    with _LOCK:
        conn = _connect()
        try:
            unread = unread_count_on(conn, user.subject)
            if candidate or staff:
                try:
                    consents = consents_payload(conn, user_id=user.subject, lang=lang)
                except Exception:
                    consents = None
        finally:
            conn.close()
    payload = {
        "authenticated": True,
        "subject": user.subject,
        "scopes": sorted(user.scopes),
        "employer": employer,
        "candidate": candidate,
        "staff": staff,
        "name": name,
        "email": email,
        "company_profile": profile,
        "candidate_profile": candidate_profile,
        "needs_company_profile": employer and not staff and not profile["complete"],
        # Seeds the header bell from SSR getMe — no second /notifications round-trip.
        "unread_notifications": unread,
    }
    # Seeds /profile privacy fields so the page skips GET /consents.
    if consents is not None:
        payload["consents"] = consents
    return payload


def safe_return_to(value: str | None) -> str:
    text = (value or "").strip() or "/"
    if not _SAFE_RETURN.fullmatch(text):
        return "/"
    return text


class CandidateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(max_length=80)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=120)


class CompanyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(max_length=120)
    city: str = Field(max_length=80)
    about: str = Field(max_length=400)
    address: str = Field(default="", max_length=160)
    website: str = Field(default="", max_length=200)
    industry: str = Field(default="", max_length=80)
    size: str = Field(default="", max_length=40)


class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    verifier: str
    nonce: str
    return_to: str
    intent: str = ""
    redirect_uri: str


class ExchangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    code: str = Field(min_length=1, max_length=4096)
    redirect_uri: str


class RefreshIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=20, max_length=4096)


def _remember_login_identity(id_token, subject: str) -> None:
    if not isinstance(id_token, str) or id_token.count(".") != 2:
        return
    try:
        from app.auth_oidc import identity_from_id_token

        found = identity_from_id_token(id_token)
    except Exception:
        return
    if not found or found[0] != subject:
        return
    if found[2]:
        remember_academy_name(subject, found[2])
    if found[1]:
        from app.profiles import remember_contact_email

        remember_contact_email(subject, found[1])


_GRANT_ERRORS = frozenset({"invalid_grant", "invalid_token"})


def _oauth_error(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    return error if isinstance(error, str) and error in _GRANT_ERRORS else None


def _reject_grant(exc: BaseException | None = None) -> HTTPException:
    error = HTTPException(status_code=401, detail="Sessiya yenilənmədi")
    if exc is not None:
        raise error from exc
    raise error


def _client_secret() -> str:
    secret = (settings.oidc_client_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="OIDC client secret konfiqurasiya edilməyib",
        )
    return secret


def _post_form(body: dict) -> dict:
    payload = {**body, "client_secret": _client_secret()}
    data = urllib.parse.urlencode(payload).encode()
    request = urllib.request.Request(
        settings.oidc_token_url,
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ingress-job-api/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read(65536)
            payload = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            err_raw = exc.read(65536)
            err_payload = json.loads(err_raw.decode("utf-8")) if err_raw else {}
        except (json.JSONDecodeError, UnicodeError, TypeError):
            err_payload = {}
        if _oauth_error(err_payload):
            _reject_grant(exc)
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeError) as exc:
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı")
    if _oauth_error(payload):
        _reject_grant()
    return payload


def _tokens_from(payload: dict, *, require_refresh: bool, expected_nonce: str | None = None) -> dict:
    if _oauth_error(payload):
        _reject_grant()
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı")
    try:
        user = verify_access_token(access)
    except AuthError as exc:
        raise HTTPException(status_code=502, detail="Academy token qəbul edilmədi") from exc
    if expected_nonce:
        nonce_status = id_token_nonce_status(payload.get("id_token"), expected_nonce)
        if nonce_status == "mismatch":
            raise HTTPException(status_code=502, detail="Academy token qəbul edilmədi")
    refresh = payload.get("refresh_token")
    if require_refresh and (not isinstance(refresh, str) or len(refresh) < 20):
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı")
    if refresh is not None and (not isinstance(refresh, str) or len(refresh) > 4096):
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı")
    expires_in = payload.get("expires_in") or 900
    refresh_expires = payload.get("refresh_expires_in") or 365 * 24 * 60 * 60
    try:
        expires_in = int(expires_in)
        refresh_expires = int(refresh_expires)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Academy token mübadiləsi alınmadı") from exc
    _remember_access_identity(user)
    _remember_login_identity(payload.get("id_token"), user.subject)
    issued = {
        "access_token": access,
        "expires_in": max(1, min(expires_in, 3600)),
        "refresh_token": refresh if isinstance(refresh, str) else None,
        "refresh_expires_in": max(1, min(refresh_expires, 365 * 24 * 60 * 60)),
        "me": account_payload(user),
    }
    return issued


@router.get("/me")
def read_me(
    lang: str | None = Query(default=None, max_length=8),
    user: VerifiedAccess = Depends(current_user),
) -> dict:
    return account_payload(user, lang=lang)


@router.post("/company-profile")
def write_company_profile(body: CompanyIn, user: VerifiedAccess = Depends(current_user)) -> dict:
    if "job:employer" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Şirkət profili işəgötürən hesabı tələb edir")
    try:
        profile = save_profile(
            user.subject,
            body.company_name,
            body.city,
            body.about,
            address=body.address,
            website=body.website,
            industry=body.industry,
            size=body.size,
        )
    except ValueError as exc:
        detail = {
            "incomplete": "Şirkət adı, şəhər və qısa təsvir doldurulmalıdır",
            "website": "Vebsayt ünvanı düzgün deyil",
            "size": "Şirkət ölçüsü düzgün deyil",
        }.get(str(exc), "Şirkət adı, şəhər və qısa təsvir doldurulmalıdır")
        raise HTTPException(status_code=422, detail=detail) from exc
    return account_payload(
        VerifiedAccess(subject=user.subject, scopes=user.scopes)
    ) | {"company_profile": profile, "needs_company_profile": (
        "job:employer" in user.scopes and "job:staff" not in user.scopes and not profile["complete"]
    )}


@router.post("/candidate-profile")
def write_candidate_profile(body: CandidateIn, user: VerifiedAccess = Depends(current_user)) -> dict:
    if "job:candidate" not in user.scopes and "job:staff" not in user.scopes:
        raise HTTPException(status_code=403, detail="Namizəd profili namizəd hesabı tələb edir")
    try:
        profile = save_candidate_profile(user.subject, body.display_name, body.phone, body.email)
    except ValueError as exc:
        detail = {
            "name": "Görünən ad yazılmalıdır",
            "phone": "Telefon nömrəsi düzgün deyil",
            "email": "E-poçt düzgün deyil",
        }.get(str(exc), "Görünən ad yazılmalıdır")
        raise HTTPException(status_code=422, detail=detail) from exc
    payload = account_payload(VerifiedAccess(subject=user.subject, scopes=user.scopes))
    payload["candidate_profile"] = profile
    return payload


@router.post("/auth/transactions", status_code=204)
def create_transaction(body: TransactionIn) -> None:
    if not _STATE.fullmatch(body.state) or not _VERIFIER.fullmatch(body.verifier):
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    if not _STATE.fullmatch(body.nonce):
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    if body.intent not in _INTENTS:
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    if body.redirect_uri not in settings.redirect_uri_list():
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    save_transaction(
        state=body.state,
        verifier=body.verifier,
        nonce=body.nonce,
        return_to=safe_return_to(body.return_to),
        intent=body.intent,
        redirect_uri=body.redirect_uri,
    )


@router.post("/auth/exchange")
def exchange(body: ExchangeIn) -> dict:
    if not _STATE.fullmatch(body.state):
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    row = take_transaction(body.state)
    if row is None or row["redirect_uri"] != body.redirect_uri:
        raise HTTPException(status_code=400, detail="Giriş sorğusu yanlışdır")
    payload = _post_form(
        {
            "grant_type": "authorization_code",
            "code": body.code,
            "redirect_uri": row["redirect_uri"],
            "client_id": settings.oidc_client_id,
            "code_verifier": row["verifier"],
        }
    )
    issued = _tokens_from(payload, require_refresh=False, expected_nonce=row["nonce"])
    issued["return_to"] = safe_return_to(row["return_to"])
    issued["intent"] = row["intent"]
    return issued


@router.post("/auth/refresh")
def refresh(body: RefreshIn) -> dict:
    payload = _post_form(
        {
            "grant_type": "refresh_token",
            "refresh_token": body.refresh_token,
            "client_id": settings.oidc_client_id,
        }
    )
    return _tokens_from(payload, require_refresh=False)
