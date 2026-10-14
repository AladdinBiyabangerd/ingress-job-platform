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
        env = {
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "AI_GATEWAY_ENABLED": "",
        }
        with patch.dict(os.environ, env, clear=False):
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
            with patch("worker.ai_gateway.gateway._call_chat_json", return_value=fake) as api:
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

    def test_cache_survives_reconnect_without_caller_commit(self):
        """Gateway must commit cache itself — skill-gap closes without commit."""
        import sqlite3

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"headline": {"type": "string"}},
            "required": ["headline"],
        }
        fake = {
            "data": {"headline": "Persisted Coach"},
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }
        path = Path(self.tmp.name) / "cache-persist.sqlite"
        env = {
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
        }
        conn1 = sqlite3.connect(path)
        try:
            ensure_ai_tables(conn1)
            with patch.dict(os.environ, env, clear=False):
                with patch("worker.ai_gateway.gateway._call_chat_json", return_value=fake):
                    first = complete_json(
                        purpose="role_coach",
                        prompt_version="t1",
                        system="sys",
                        user="stable skills prompt",
                        schema=schema,
                        conn=conn1,
                    )
            # Mimic skill_gap: close without an extra caller commit.
            conn1.close()
        finally:
            try:
                conn1.close()
            except Exception:
                pass

        self.assertTrue(first.ok)
        self.assertFalse(first.cached)

        conn2 = sqlite3.connect(path)
        try:
            with patch.dict(os.environ, env, clear=False):
                with patch("worker.ai_gateway.gateway._call_chat_json") as api:
                    second = complete_json(
                        purpose="role_coach",
                        prompt_version="t1",
                        system="sys",
                        user="stable skills prompt",
                        schema=schema,
                        conn=conn2,
                    )
            api.assert_not_called()
        finally:
            conn2.close()

        self.assertTrue(second.ok)
        self.assertTrue(second.cached)
        self.assertEqual(second.data["headline"], "Persisted Coach")

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
            with patch("worker.ai_gateway.gateway._call_chat_json", return_value=fake):
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

    def test_db_gateway_off_skips_with_key(self):
        from worker.ai_flags import set_flags

        set_flags(self.store.conn, {"gateway": False}, updated_by="test")
        env = {"OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with patch("worker.ai_gateway.gateway._call_chat_json") as api:
                result = complete_json(
                    purpose="cv_parse",
                    prompt_version="t1",
                    system="sys",
                    user="Java",
                    schema={
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"headline": {"type": "string"}},
                        "required": ["headline"],
                    },
                    conn=self.store.conn,
                )
        api.assert_not_called()
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "ai_disabled")

    def test_chat_falls_back_to_next_provider(self):
        from worker.ai_gateway import gateway as gw

        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"headline": {"type": "string"}},
            "required": ["headline"],
        }
        env = {
            "GEMINI_API_KEY": "g-test",
            "GROQ_API_KEY": "groq-test",
            "OPENAI_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "AI_GATEWAY_ENABLED": "1",
            "AI_CHAT_PROVIDERS": "gemini,groq",
            "GEMINI_MODELS": "gemini-3.8-flash",
            "GROQ_MODELS": "openai/gpt-oss-20b",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
        }
        calls: list[str] = []

        def fake_chat(*, provider, system, user, schema, schema_name, timeout):
            calls.append(provider.name)
            if provider.name == "gemini":
                raise RuntimeError("gemini_down")
            return {
                "data": {"headline": "From Groq"},
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        with patch.dict(os.environ, env, clear=False):
            with patch.object(gw, "_chat_json", side_effect=fake_chat):
                result = complete_json(
                    purpose="cv_parse",
                    prompt_version="fb1",
                    system="sys",
                    user="Java",
                    schema=schema,
                    conn=self.store.conn,
                )
        self.assertTrue(result.ok)
        self.assertEqual(result.data["headline"], "From Groq")
        self.assertEqual(calls, ["gemini", "groq"])
        self.assertEqual(result.meta.get("provider"), "groq")


if __name__ == "__main__":
    unittest.main()


def _unique_provider_names(providers) -> list[str]:
    out: list[str] = []
    for p in providers:
        if p.name not in out:
            out.append(p.name)
    return out


class ChatProviderOrderTest(unittest.TestCase):
    """Free providers first; OpenAI only as the very last resort."""

    def test_openai_is_forced_last_even_if_env_lists_it_first(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "openai,gemini,groq,nvidia,openrouter",
            "GEMINI_API_KEY": "g", "GROQ_API_KEY": "q", "NVIDIA_API_KEY": "n",
            "OPENROUTER_API_KEY": "o", "OPENAI_API_KEY": "x",
            "GEMINI_MODELS": "gemini-3.5-flash-lite,gemini-3.8-flash",
            "GROQ_MODELS": "openai/gpt-oss-20b",
            "NVIDIA_MODELS": "nvidia/nemotron-3.5-lightning-30b-a3b",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            for k in (
                "GEMINI_API_KEY_2", "GEMINI_API_KEYS", "GEMINI_MODEL",
                "GROQ_API_KEY_2", "GROQ_API_KEYS", "GROQ_MODEL",
                "NVIDIA_CHAT_MODEL",
            ):
                os.environ.pop(k, None)
            providers = gw._chat_providers()
            names = _unique_provider_names(providers)
            gemini = [p for p in providers if p.name == "gemini"]
        self.assertEqual(names, ["gemini", "groq", "nvidia", "openrouter", "openai"])
        self.assertEqual(
            [p.model for p in gemini],
            ["gemini-3.5-flash-lite", "gemini-3.8-flash"],
        )

    def test_default_order_and_missing_keys_skip(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {"GROQ_API_KEY": "q", "OPENAI_API_KEY": "x"}
        with mock.patch.dict(os.environ, env, clear=False):
            for k in (
                "AI_CHAT_PROVIDERS",
                "GEMINI_API_KEY",
                "GEMINI_API_KEY_2",
                "GEMINI_API_KEYS",
                "GROQ_API_KEY_2",
                "GROQ_API_KEYS",
                "NVIDIA_API_KEY",
                "OPENROUTER_API_KEY",
            ):
                os.environ.pop(k, None)
            os.environ["GROQ_MODELS"] = "openai/gpt-oss-20b"
            names = [p.name for p in gw._chat_providers()]
        self.assertEqual(names, ["groq", "openai"])

    def test_groq_expands_models_and_keys(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "groq",
            "GROQ_API_KEY": "q1",
            "GROQ_API_KEY_2": "q2",
            "GROQ_MODELS": "m-a,m-b",
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("GROQ_API_KEYS", None)
            os.environ.pop("GROQ_MODEL", None)
            slots = gw._chat_providers()
        self.assertEqual(
            [(p.key, p.model, p.cooldown_id) for p in slots],
            [
                ("q1", "m-a", "groq:k0:m-a"),
                ("q1", "m-b", "groq:k0:m-b"),
                ("q2", "m-a", "groq:k1:m-a"),
                ("q2", "m-b", "groq:k1:m-b"),
            ],
        )

    def test_gemini_expands_models_and_keys(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "gemini",
            "GEMINI_API_KEY": "k1",
            "GEMINI_API_KEY_2": "k2",
            "GEMINI_MODELS": "m-a,m-b",
            "GROQ_API_KEY": "",
            "OPENAI_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("GEMINI_API_KEYS", None)
            slots = gw._chat_providers()
        self.assertEqual(
            [(p.key, p.model, p.cooldown_id) for p in slots],
            [
                ("k1", "m-a", "gemini:k0:m-a"),
                ("k1", "m-b", "gemini:k0:m-b"),
                ("k2", "m-a", "gemini:k1:m-a"),
                ("k2", "m-b", "gemini:k1:m-b"),
            ],
        )

    def test_nvidia_expands_models(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "nvidia",
            "NVIDIA_API_KEY": "n",
            "NVIDIA_MODELS": "n-a,n-b",
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "OPENAI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NVIDIA_CHAT_MODEL", None)
            slots = gw._chat_providers()
        self.assertEqual(
            [(p.name, p.model, p.cooldown_id) for p in slots],
            [
                ("nvidia", "n-a", "nvidia:n-a"),
                ("nvidia", "n-b", "nvidia:n-b"),
            ],
        )

    def test_nvidia_model_cascade_tries_next(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "nvidia,groq",
            "NVIDIA_API_KEY": "n",
            "NVIDIA_MODELS": "n1,n2",
            "GROQ_API_KEY": "q",
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }
        calls: list[tuple[str, str]] = []

        def fake_chat(*, provider, **kw):
            calls.append((provider.name, provider.model))
            if provider.model != "n2":
                raise gw.ProviderHTTPError("HTTP 429", 429)
            return {"data": {"ok": True}, "usage": {}}

        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("NVIDIA_CHAT_MODEL", None)
            gw._cooldown_reset()
            with mock.patch.object(gw, "_chat_json", side_effect=fake_chat):
                out = gw._call_chat_json(
                    system="s", user="u", schema={}, schema_name="x", timeout=1
                )
        self.assertEqual(calls, [("nvidia", "n1"), ("nvidia", "n2")])
        self.assertEqual(out["model"], "n2")
        self.assertEqual(out["provider"], "nvidia")

    def test_gemini_model_cascade_tries_next_before_other_providers(self):
        import os
        from unittest import mock

        from worker.ai_gateway import gateway as gw

        env = {
            "AI_CHAT_PROVIDERS": "gemini,groq",
            "GEMINI_API_KEY": "g",
            "GEMINI_MODELS": "m1,m2",
            "GROQ_API_KEY": "q",
            "OPENAI_API_KEY": "",
            "NVIDIA_API_KEY": "",
            "OPENROUTER_API_KEY": "",
        }
        calls: list[tuple[str, str]] = []

        def fake_chat(*, provider, **kw):
            calls.append((provider.name, provider.model))
            if provider.model != "m2":
                raise gw.ProviderHTTPError("HTTP 429", 429)
            return {"data": {"ok": True}, "usage": {}}

        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("GEMINI_API_KEY_2", None)
            os.environ.pop("GEMINI_API_KEYS", None)
            gw._cooldown_reset()
            with mock.patch.object(gw, "_chat_json", side_effect=fake_chat):
                out = gw._call_chat_json(
                    system="s", user="u", schema={}, schema_name="x", timeout=1
                )
        self.assertEqual(calls, [("gemini", "m1"), ("gemini", "m2")])
        self.assertEqual(out["model"], "m2")
        self.assertEqual(out["provider"], "gemini")
