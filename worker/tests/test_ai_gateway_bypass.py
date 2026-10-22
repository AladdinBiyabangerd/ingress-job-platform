"""ai_gateway bypass_cache: staff re-check asks the provider again (still writes cache)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import complete_json, ensure_ai_tables
from worker.db import Store

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}
ENV = {
    "OPENAI_API_KEY": "sk-test",
    "AI_GATEWAY_ENABLED": "1",
    "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
}


def _fake(answer: str) -> dict:
    return {"data": {"answer": answer}, "usage": {"prompt_tokens": 5, "completion_tokens": 5}}


class GatewayBypassCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        ensure_ai_tables(self.store.conn)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _call(self, **kwargs):
        return complete_json(
            purpose="market_fit",
            prompt_version="test-v1",
            system="sys",
            user="same prompt",
            schema=SCHEMA,
            conn=self.store.conn,
            **kwargs,
        )

    def test_bypass_calls_provider_and_replaces_cached_answer(self):
        with patch.dict(os.environ, ENV, clear=False):
            with patch("worker.ai_gateway.gateway._call_chat_json", return_value=_fake("old")):
                first = self._call()
            with patch("worker.ai_gateway.gateway._call_chat_json") as api:
                hit = self._call()
                api.assert_not_called()
            with patch(
                "worker.ai_gateway.gateway._call_chat_json", return_value=_fake("new")
            ) as api:
                fresh = self._call(bypass_cache=True)
                api.assert_called_once()
            with patch("worker.ai_gateway.gateway._call_chat_json") as api:
                after = self._call()
                api.assert_not_called()
        self.assertFalse(first.cached)
        self.assertTrue(hit.cached)
        self.assertEqual(hit.data["answer"], "old")
        self.assertFalse(fresh.cached)
        self.assertEqual(fresh.data["answer"], "new")
        self.assertTrue(after.cached)
        self.assertEqual(after.data["answer"], "new")

    def test_bypass_still_respects_budget(self):
        env = dict(ENV, AI_GATEWAY_DAILY_CALL_LIMIT="1")
        with patch.dict(os.environ, env, clear=False):
            with patch("worker.ai_gateway.gateway._call_chat_json", return_value=_fake("a")):
                self._call()
            with patch("worker.ai_gateway.gateway._call_chat_json") as api:
                blocked = self._call(bypass_cache=True)
                api.assert_not_called()
        self.assertFalse(blocked.ok)
        self.assertEqual(blocked.error, "ai_budget_exceeded")


if __name__ == "__main__":
    unittest.main()
