"""Refresh maps invalid_grant to 401 and upstream failures to 502."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.main import app


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self, _n: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def _http_error(code: int, body: dict | bytes | None) -> urllib.error.HTTPError:
    if body is None:
        fp = io.BytesIO(b"")
    elif isinstance(body, bytes):
        fp = io.BytesIO(body)
    else:
        fp = io.BytesIO(json.dumps(body).encode())
    return urllib.error.HTTPError(
        url="http://academy.test/portal/oauth/token",
        code=code,
        msg="error",
        hdrs=None,
        fp=fp,
    )


@contextmanager
def _urlopen(result):
    kwargs = {"side_effect": result} if isinstance(result, BaseException) else {"return_value": result}
    with patch("urllib.request.urlopen", **kwargs) as mocked:
        yield mocked


class AuthRefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "accounts.sqlite"
        self.patches = [
            patch("app.profiles.DATA_PATH", self.db),
            patch("app.notifications.unread_count", return_value=0),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.body = {"refresh_token": "r" * 40}

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def test_invalid_grant_returns_401(self):
        with _urlopen(_http_error(400, {"error": "invalid_grant", "error_description": "expired"})):
            response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Sessiya yenilənmədi")

    def test_invalid_token_returns_401(self):
        with _urlopen(_http_error(401, {"error": "invalid_token"})):
            response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 401)

    def test_academy_5xx_returns_502(self):
        with _urlopen(_http_error(503, {"error": "server_error"})):
            response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Academy token mübadiləsi alınmadı")

    def test_academy_timeout_returns_502(self):
        with _urlopen(TimeoutError("timed out")):
            response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 502)

    def test_academy_network_error_returns_502(self):
        with _urlopen(urllib.error.URLError("connection refused")):
            response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 502)

    def test_successful_refresh_returns_tokens(self):
        payload = {
            "access_token": "access-new",
            "expires_in": 900,
            "refresh_token": "r" * 40,
            "refresh_expires_in": 3600,
        }
        user = VerifiedAccess(subject="42", scopes=frozenset({"job:candidate"}))
        with _urlopen(_FakeResponse(json.dumps(payload).encode())):
            with patch("app.account.verify_access_token", return_value=user):
                response = self.client.post("/api/v1/auth/refresh", json=self.body)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["access_token"], "access-new")
        self.assertEqual(data["refresh_token"], "r" * 40)
        self.assertEqual(data["expires_in"], 900)
        self.assertTrue(data["me"]["authenticated"])
        self.assertIn("email", data["me"])

    def test_exchange_rejects_id_token_nonce_mismatch(self):
        from app.profiles import save_transaction

        save_transaction(
            state="s" * 22,
            verifier="v" * 43,
            nonce="expected-nonce-value-0123456789ab",
            return_to="/",
            intent="job_candidate",
            redirect_uri="http://localhost:3010/api/auth/callback",
        )
        payload = {
            "access_token": "access-new",
            "id_token": "x.y.z",
            "expires_in": 900,
            "refresh_token": "r" * 40,
        }
        user = VerifiedAccess(subject="42", scopes=frozenset({"job:candidate"}))
        with _urlopen(_FakeResponse(json.dumps(payload).encode())):
            with patch("app.account.verify_access_token", return_value=user):
                with patch("app.account.id_token_nonce_status", return_value="mismatch"):
                    response = self.client.post(
                        "/api/v1/auth/exchange",
                        json={
                            "state": "s" * 22,
                            "code": "auth-code-value",
                            "redirect_uri": "http://localhost:3010/api/auth/callback",
                        },
                    )
        self.assertEqual(response.status_code, 502)

    def test_exchange_accepts_matching_nonce(self):
        from app.profiles import save_transaction

        save_transaction(
            state="t" * 22,
            verifier="v" * 43,
            nonce="expected-nonce-value-0123456789ab",
            return_to="/profile",
            intent="job_candidate",
            redirect_uri="http://localhost:3010/api/auth/callback",
        )
        payload = {
            "access_token": "access-new",
            "id_token": "x.y.z",
            "expires_in": 900,
            "refresh_token": "r" * 40,
        }
        user = VerifiedAccess(subject="42", scopes=frozenset({"job:candidate"}))
        with _urlopen(_FakeResponse(json.dumps(payload).encode())):
            with patch("app.account.verify_access_token", return_value=user):
                with patch("app.account.id_token_nonce_status", return_value="ok"):
                    response = self.client.post(
                        "/api/v1/auth/exchange",
                        json={
                            "state": "t" * 22,
                            "code": "auth-code-value",
                            "redirect_uri": "http://localhost:3010/api/auth/callback",
                        },
                    )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["access_token"], "access-new")
        self.assertEqual(data["return_to"], "/profile")

    def test_exchange_allows_unverified_id_token(self):
        from app.profiles import save_transaction

        save_transaction(
            state="u" * 22,
            verifier="v" * 43,
            nonce="expected-nonce-value-0123456789ab",
            return_to="/",
            intent="job_candidate",
            redirect_uri="http://localhost:3010/api/auth/callback",
        )
        payload = {
            "access_token": "access-new",
            "expires_in": 900,
            "refresh_token": "r" * 40,
        }
        user = VerifiedAccess(subject="42", scopes=frozenset({"job:candidate"}))
        with _urlopen(_FakeResponse(json.dumps(payload).encode())):
            with patch("app.account.verify_access_token", return_value=user):
                with patch("app.account.id_token_nonce_status", return_value="unverified"):
                    response = self.client.post(
                        "/api/v1/auth/exchange",
                        json={
                            "state": "u" * 22,
                            "code": "auth-code-value",
                            "redirect_uri": "http://localhost:3010/api/auth/callback",
                        },
                    )
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()
