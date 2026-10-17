"""Embedding calls use their own daily pool and cannot starve chat (CV/matching)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import complete_json, embed, ensure_ai_tables
from worker.ai_gateway import gateway
from worker.db import Store

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"headline": {"type": "string"}},
    "required": ["headline"],
}
CHAT_FAKE = {"data": {"headline": "X"}, "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
EMBED_FAKE = {"vectors": [[0.1, 0.2]], "usage": {"prompt_tokens": 2}}


class EmbedBudgetTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "jobs.sqlite", sqlite_only=True)
        ensure_ai_tables(self.store.conn)
        gateway._cooldown_reset()

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()
        gateway._cooldown_reset()

    def _env(self, chat: str, emb: str) -> dict:
        return {
            "OPENAI_API_KEY": "sk-test",
            "NVIDIA_API_KEY": "",
            "AI_GATEWAY_ENABLED": "1",
            "AI_EMBED_PROVIDERS": "openai",
            "AI_EMBEDDING_MODEL": "",
            "AI_GATEWAY_DAILY_CALL_LIMIT": chat,
            "AI_EMBED_DAILY_CALL_LIMIT": emb,
        }

    def test_embeddings_do_not_consume_chat_pool(self):
        with patch.dict(os.environ, self._env("1", "5"), clear=False):
            with patch("worker.ai_gateway.gateway._call_embed", return_value=dict(EMBED_FAKE)):
                for i in range(3):
                    r = embed(texts=[f"job {i}"], purpose="embed_job", conn=self.store.conn)
                    self.assertTrue(r.ok, r.error)
            with patch("worker.ai_gateway.gateway._call_chat_json", return_value=CHAT_FAKE):
                chat = complete_json(
                    purpose="cv_parse", prompt_version="t1", system="s", user="u",
                    schema=SCHEMA, conn=self.store.conn,
                )
        self.assertTrue(chat.ok, chat.error)
        self.assertEqual(gateway.daily_calls(self.store.conn, embed=True), 3)
        self.assertEqual(gateway.daily_calls(self.store.conn, embed=False), 1)

    def test_embed_pool_has_its_own_cap(self):
        with patch.dict(os.environ, self._env("100", "2"), clear=False):
            with patch("worker.ai_gateway.gateway._call_embed", return_value=dict(EMBED_FAKE)):
                results = [
                    embed(texts=[f"job {i}"], purpose="embed_job", conn=self.store.conn)
                    for i in range(3)
                ]
        self.assertEqual([r.ok for r in results], [True, True, False])
        self.assertEqual(results[2].error, "ai_budget_exceeded")

    def test_default_embed_limit(self):
        with patch.dict(os.environ, {"AI_EMBED_DAILY_CALL_LIMIT": ""}, clear=False):
            os.environ.pop("AI_EMBED_DAILY_CALL_LIMIT", None)
            self.assertEqual(gateway.embed_daily_call_limit(), 500)


if __name__ == "__main__":
    unittest.main()
