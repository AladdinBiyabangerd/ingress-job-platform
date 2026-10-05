"""ai_gateway: redact, cache, budget, feature flag (plan §11)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import complete_json, ensure_ai_tables, mask_pii
from worker.db import Store


class RedactTest(unittest.TestCase):
    def test_masks_known_and_regex_pii(self):
        text = (
            "Aysel Məmmədli\n"
            "aysel.mammadli@example.com\n"
            "+994 50 111 22 33\n"
            "https://github.com/ayselm\n"
            "12 Main Street, Baku\n"
            "Java Spring\n"
        )
        known = {
            "full_name": "Aysel Məmmədli",
            "email": "aysel.mammadli@example.com",
            "phone": "+994 50 111 22 33",
            "links": {"github": "https://github.com/ayselm"},
        }
        out = mask_pii(text, known=known)
        self.assertNotIn("Aysel", out)
        self.assertNotIn("aysel.mammadli@example.com", out)
        self.assertNotIn("111 22 33", out)
        self.assertIn("[NAME]", out)
        self.assertIn("[EMAIL]", out)
        self.assertIn("[PHONE]", out)
        self.assertIn("[URL]", out)
        self.assertIn("[ADDRESS]", out)
        self.assertIn("Java Spring", out)


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        ensure_ai_tables(self.store.conn)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_disabled_without_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "AI_GATEWAY_ENABLED": ""}, clear=False):
            result = complete_json(
                purpose="cv_parse",
                prompt_version="t1",
                system="sys",
                user="hello@example.com knows Java",
                schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"headline": {"type": "string"}},
                    "required": ["headline"],
                },
                conn=self.store.conn,
            )
        self.assertFalse(result.ok)
        self.assertIn(result.error, {"ai_disabled", "ai_no_key"})

    def test_cache_hit_skips_provider(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"headline": {"type": "string"}},
            "required": ["headline"],
        }
        fake = {
            "data": {"headline": "Backend Developer"},
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        env = {
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("worker.ai_gateway.gateway._openai_json", return_value=fake) as api:
                first = complete_json(
                    purpose="cv_parse",
                    prompt_version="t1",
                    system="sys",
                    user="Java Spring Kafka",
                    schema=schema,
                    conn=self.store.conn,
                )
                second = complete_json(
                    purpose="cv_parse",
                    prompt_version="t1",
                    system="sys",
                    user="Java Spring Kafka",
                    schema=schema,
                    conn=self.store.conn,
                )
        self.assertTrue(first.ok)
        self.assertFalse(first.cached)
        self.assertTrue(second.ok)
        self.assertTrue(second.cached)
        self.assertEqual(api.call_count, 1)
        self.assertEqual(second.data["headline"], "Backend Developer")

    def test_daily_budget_blocks(self):
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"headline": {"type": "string"}},
            "required": ["headline"],
        }
        env = {
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "1",
        }
        fake = {
            "data": {"headline": "X"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("worker.ai_gateway.gateway._openai_json", return_value=fake):
                first = complete_json(
                    purpose="cv_parse",
                    prompt_version="t1",
                    system="sys",
                    user="one",
                    schema=schema,
                    conn=self.store.conn,
                )
                second = complete_json(
                    purpose="cv_parse",
                    prompt_version="t1",
                    system="sys",
                    user="two different",
                    schema=schema,
                    conn=self.store.conn,
                )
        self.assertTrue(first.ok)
        self.assertFalse(second.ok)
        self.assertEqual(second.error, "ai_budget_exceeded")


if __name__ == "__main__":
    unittest.main()
