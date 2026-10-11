"""Rate limit: IP budgets and benefit-framed slow_down bodies."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rate_limit import BUCKETS, reset_rate_limit_state_for_tests


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_state_for_tests()
        self.env = patch.dict(
            os.environ,
            {
                "RATE_LIMIT_ENABLED": "1",
                "REDIS_URL": "",
                "RAILWAY_ENVIRONMENT": "",
            },
            clear=False,
        )
        self.env.start()
        # Force empty redis via settings too
        self.redis_patch = patch("app.rate_limit._redis_url", return_value="")
        self.redis_patch.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.redis_patch.stop()
        self.env.stop()
        reset_rate_limit_state_for_tests()
        os.environ.pop("RATE_LIMIT_ENABLED", None)

    def test_public_read_returns_slow_down_json(self):
        limit, _window, _key, _fc = BUCKETS["public_read"]
        # Also burns global bucket; temporarily raise global for this test.
        with patch.dict(
            "app.rate_limit.BUCKETS",
            {
                **BUCKETS,
                "global": (10_000, 60, "rateLimit.gentle", False),
                "public_read": (3, 60, "rateLimit.gentle", False),
            },
            clear=False,
        ):
            reset_rate_limit_state_for_tests()
            for _ in range(3):
                res = self.client.get("/api/v1/jobs")
                self.assertIn(res.status_code, {200, 429})
            res = self.client.get("/api/v1/jobs")
            self.assertEqual(res.status_code, 429)
            body = res.json()
            self.assertEqual(body.get("error"), "slow_down")
            self.assertEqual(body.get("message_key"), "rateLimit.gentle")
            self.assertIn("retry_after_seconds", body)
            self.assertNotIn("banned", str(body).lower())
            self.assertNotIn("abuse", str(body).lower())
            self.assertTrue(res.headers.get("Retry-After"))

    def test_cf_connecting_ip_used(self):
        with patch.dict(
            "app.rate_limit.BUCKETS",
            {
                **BUCKETS,
                "global": (10_000, 60, "rateLimit.gentle", False),
                "auth_tx": (2, 60, "rateLimit.signInPause", True),
            },
            clear=False,
        ):
            reset_rate_limit_state_for_tests()
            payload = {
                "state": "a" * 32,
                "verifier": "b" * 43,
                "nonce": "c" * 32,
                "return_to": "/",
                "intent": "",
                "redirect_uri": "http://localhost:3010/api/auth/callback",
            }
            # Invalid body may 400 before rate — use valid-shaped after mocking save
            headers = {"cf-connecting-ip": "203.0.113.9"}
            with patch("app.account.save_transaction"):
                for _ in range(2):
                    self.client.post("/api/v1/auth/transactions", json=payload, headers=headers)
                res = self.client.post("/api/v1/auth/transactions", json=payload, headers=headers)
            self.assertEqual(res.status_code, 429)
            self.assertEqual(res.json().get("message_key"), "rateLimit.signInPause")

    def test_disabled_skips_limits(self):
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "0"}, clear=False):
            reset_rate_limit_state_for_tests()
            with patch.dict(
                "app.rate_limit.BUCKETS",
                {**BUCKETS, "public_read": (1, 60, "rateLimit.gentle", False), "global": (1, 60, "rateLimit.gentle", False)},
            ):
                for _ in range(5):
                    res = self.client.get("/api/v1/jobs")
                    self.assertNotEqual(res.status_code, 429)


if __name__ == "__main__":
    unittest.main()
