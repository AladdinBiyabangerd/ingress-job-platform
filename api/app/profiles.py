"""Company profile fields required before an employer can post.

Candidate display name, phone, and email stay in this same job-site database.
They are not written to Academy.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "accounts.sqlite"
_LOCK = Lock()
_ACCOUNTS_ENSURED: set[str] = set()

NAME_MAX = 120
CITY_MAX = 80
ABOUT_MAX = 400
CANDIDATE_NAME_MAX = 80
PHONE_MAX = 40
EMAIL_MAX = 120
_PHONE_RE = re.compile(r"^[0-9+\-() ]{5,40}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _connect() -> sqlite3.Connection:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA_PATH)
    conn.row_factory = sqlite3.Row
    key = str(DATA_PATH)
    if key in _ACCOUNTS_ENSURED:
        return conn
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS company_profiles (
            subject TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            city TEXT NOT NULL,
            about TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            subject TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS contact_emails (
            subject TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS academy_identities (
            subject TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oidc_transactions (
            state TEXT PRIMARY KEY,
            verifier TEXT NOT NULL,
            nonce TEXT NOT NULL,
            return_to TEXT NOT NULL,
            intent TEXT NOT NULL,
            redirect_uri TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    _ACCOUNTS_ENSURED.add(key)
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: str, limit: int) -> str:
    text = (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text[:limit]


def _company_view(row) -> dict:
    if row is None:
        return {"company_name": "", "city": "", "about": "", "complete": False}
    name = (row["company_name"] or "").strip()
    city = (row["city"] or "").strip()
    about = (row["about"] or "").strip()
    return {
        "company_name": name,
        "city": city,
        "about": about,
        "complete": bool(name and city and about),
    }


def _candidate_view(row) -> dict:
    if row is None:
        return empty_candidate_profile()
    return {
        "display_name": (row["display_name"] or "").strip(),
        "phone": (row["phone"] or "").strip(),
        "email": (row["email"] or "").strip(),
    }


def account_fields_for(subject: str) -> dict:
    """Company, candidate, academy name, and contact email in one accounts open."""
    who = (subject or "").strip()
    with _LOCK:
        conn = _connect()
        try:
            company = conn.execute(
                "SELECT company_name, city, about FROM company_profiles WHERE subject = ?",
                (who,),
            ).fetchone()
            candidate = conn.execute(
                "SELECT display_name, phone, email FROM candidate_profiles WHERE subject = ?",
                (who,),
            ).fetchone()
            academy = conn.execute(
                "SELECT name FROM academy_identities WHERE subject = ?",
                (who,),
            ).fetchone()
            contact = conn.execute(
                "SELECT email FROM contact_emails WHERE subject = ?",
                (who,),
            ).fetchone()
        finally:
            conn.close()
    return {
        "company_profile": _company_view(company),
        "candidate_profile": _candidate_view(candidate),
        "academy_name": (academy["name"] or "").strip() if academy is not None else "",
        "contact_email": (contact["email"] or "").strip().lower() if contact is not None else "",
    }


def profile_for(subject: str) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT company_name, city, about FROM company_profiles WHERE subject = ?",
                (subject,),
            ).fetchone()
        finally:
            conn.close()
    return _company_view(row)


def save_profile(subject: str, company_name: str, city: str, about: str) -> dict:
    name = _clean(company_name, NAME_MAX)
    city_value = _clean(city, CITY_MAX)
    about_value = _clean(about, ABOUT_MAX)
    if not name or not city_value or not about_value:
        raise ValueError("incomplete")
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO company_profiles (subject, company_name, city, about, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    company_name = excluded.company_name,
                    city = excluded.city,
                    about = excluded.about,
                    updated_at = excluded.updated_at
                """,
                (subject, name, city_value, about_value, _now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    return profile_for(subject)



def empty_candidate_profile() -> dict:
    return {"display_name": "", "phone": "", "email": ""}


def academy_name_for(subject: str) -> str:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT name FROM academy_identities WHERE subject = ?",
                (subject,),
            ).fetchone()
        finally:
            conn.close()
    return (row["name"] or "").strip() if row is not None else ""


def remember_academy_name(subject: str, name: str) -> None:
    who = (subject or "").strip()
    value = _clean(name, NAME_MAX)
    if not who or not value:
        return
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO academy_identities (subject, name, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    name = excluded.name,
                    updated_at = excluded.updated_at
                """,
                (who, value, _now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def candidate_profile_for(subject: str) -> dict:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT display_name, phone, email FROM candidate_profiles WHERE subject = ?",
                (subject,),
            ).fetchone()
        finally:
            conn.close()
    return _candidate_view(row)


def save_candidate_profile(subject: str, display_name: str, phone: str, email: str) -> dict:
    name = _clean(display_name, CANDIDATE_NAME_MAX)
    phone_value = " ".join((phone or "").split())
    email_value = (email or "").strip().lower()
    if not name:
        raise ValueError("name")
    if phone_value:
        digits = sum(char.isdigit() for char in phone_value)
        if digits < 5 or len(phone_value) > PHONE_MAX or not _PHONE_RE.fullmatch(phone_value):
            raise ValueError("phone")
    if email_value and (len(email_value) > EMAIL_MAX or not _EMAIL_RE.fullmatch(email_value)):
        raise ValueError("email")
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO candidate_profiles (subject, display_name, phone, email, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    display_name = excluded.display_name,
                    phone = excluded.phone,
                    email = excluded.email,
                    updated_at = excluded.updated_at
                """,
                (subject, name, phone_value, email_value, _now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    if email_value:
        remember_contact_email(subject, email_value)
    return candidate_profile_for(subject)


def remember_contact_email(subject: str, email: str) -> None:
    """Store the address used for job mail. Empty or invalid values are ignored."""
    who = (subject or "").strip()
    address = (email or "").strip().lower()
    if not who or len(who) > 255 or len(address) > EMAIL_MAX or not _EMAIL_RE.fullmatch(address):
        return
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO contact_emails (subject, email, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    email = excluded.email,
                    updated_at = excluded.updated_at
                """,
                (who, address, _now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def contact_email_for(subject: str) -> str:
    who = (subject or "").strip()
    if not who:
        return ""
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT email FROM contact_emails WHERE subject = ?",
                (who,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return ""
    return (row["email"] or "").strip().lower()


def save_transaction(
    *,
    state: str,
    verifier: str,
    nonce: str,
    return_to: str,
    intent: str,
    redirect_uri: str,
) -> None:
    cutoff = (_now() - timedelta(minutes=10)).isoformat()
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM oidc_transactions WHERE created_at < ?", (cutoff,))
            conn.execute(
                """
                INSERT INTO oidc_transactions
                    (state, verifier, nonce, return_to, intent, redirect_uri, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (state, verifier, nonce, return_to, intent, redirect_uri, _now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def take_transaction(state: str) -> dict | None:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT verifier, nonce, return_to, intent, redirect_uri, created_at
                FROM oidc_transactions WHERE state = ?
                """,
                (state,),
            ).fetchone()
            if row is None:
                return None
            conn.execute("DELETE FROM oidc_transactions WHERE state = ?", (state,))
            conn.commit()
        finally:
            conn.close()
    created = datetime.fromisoformat(row["created_at"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if (_now() - created).total_seconds() > 600:
        return None
    return {
        "verifier": row["verifier"],
        "nonce": row["nonce"],
        "return_to": row["return_to"],
        "intent": row["intent"],
        "redirect_uri": row["redirect_uri"],
    }
