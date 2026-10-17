"""P0 (worker): jobs embed as NVIDIA "passage", profiles as "query"; one model key."""

from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from worker import embeddings as emb
from worker.ai_gateway import gateway
from worker.ai_gateway.gateway import EmbedResult

NV = "nvidia/nemotron-3-embed-1b"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, category TEXT, text TEXT,
            status TEXT, hidden INTEGER, merged_into INTEGER, remote INTEGER,
            relocation INTEGER, tech_stack TEXT);
        CREATE TABLE skill_dictionary (id INTEGER PRIMARY KEY, canonical_name TEXT);
        CREATE TABLE job_skill (job_id INTEGER, skill_id INTEGER);
        CREATE TABLE embeddings (entity_type TEXT, entity_id TEXT, model TEXT,
            content_hash TEXT, dims INTEGER, embedding TEXT, updated_at TEXT);
        INSERT INTO jobs VALUES (1, 'Java Developer', 'backend', 'Spring Boot', 'published',
            0, NULL, 1, 0, '["Java"]');
        INSERT INTO jobs VALUES (2, 'Go Developer', 'backend', 'gRPC', 'published',
            0, NULL, 1, 0, '["Go"]');
        """
    )
    return conn


class WorkerInputTypeTests(unittest.TestCase):
    def _patches(self, fake):
        return (
            patch.object(emb, "ensure_embedding_tables", return_value=True),
            patch.object(emb, "embedding_model", return_value=NV),
            patch("worker.ai_flags.feature_on", return_value=True),
            patch("worker.ai_gateway.enabled", return_value=True),
            patch("worker.ai_gateway.embed", return_value=fake),
            patch.object(emb, "upsert_job_embedding", return_value=True),
        )

    def test_stale_jobs_use_passage_and_reader_key(self):
        fake = EmbedResult(ok=True, vectors=[[0.1], [0.2]], model=NV)
        p = self._patches(fake)
        with p[0], p[1], p[2], p[3], p[4] as embed_mock, p[5] as upsert:
            stats = emb.embed_stale_jobs(_conn(), limit=10)
        self.assertEqual(stats["embedded"], 2)
        self.assertEqual(embed_mock.call_args.kwargs["input_type"], "passage")
        self.assertEqual({c.kwargs["model"] for c in upsert.call_args_list}, {NV})

    def test_stale_jobs_stop_on_model_mismatch(self):
        fake = EmbedResult(ok=True, vectors=[[0.1], [0.2]], model="text-embedding-3-small")
        p = self._patches(fake)
        with p[0], p[1], p[2], p[3], p[4], p[5] as upsert:
            stats = emb.embed_stale_jobs(_conn(), limit=10)
        self.assertEqual(stats["embedded"], 0)
        upsert.assert_not_called()

    def test_embed_job_uses_passage(self):
        fake = EmbedResult(ok=True, vectors=[[0.1]], model=NV)
        p = self._patches(fake)
        with p[0], p[1], p[2], p[3], p[4] as embed_mock, p[5]:
            self.assertTrue(emb.embed_job(_conn(), 1))
        self.assertEqual(embed_mock.call_args.kwargs["input_type"], "passage")

    def test_embed_profile_uses_query(self):
        fake = EmbedResult(ok=True, vectors=[[0.1, 0.2]], model=NV)
        calls = []

        class Conn:
            def execute(self, sql, params=()):
                calls.append((sql, params))

        with patch.object(emb, "ensure_embedding_tables", return_value=True), patch.object(
            emb, "embedding_model", return_value=NV
        ), patch("worker.ai_flags.feature_on", return_value=True), patch(
            "worker.ai_gateway.embed", return_value=fake
        ) as embed_mock, patch.object(emb, "dims_match", return_value=True):
            ok = emb.embed_profile(Conn(), user_id="u1", profile={"headline": "Java dev"})
        self.assertTrue(ok)
        self.assertEqual(embed_mock.call_args.kwargs["input_type"], "query")
        self.assertEqual(calls[-1][1][2], NV)


class WorkerGatewayTests(unittest.TestCase):
    def setUp(self):
        gateway._cooldown_reset()
        self.addCleanup(gateway._cooldown_reset)

    def test_single_provider_and_input_type(self):
        env = {
            "NVIDIA_API_KEY": "nv-test",
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_EMBEDDING_MODEL": "",
            "NVIDIA_EMBED_MODEL": "",
            "AI_EMBED_PROVIDERS": "",
        }
        payload = {"data": [{"index": 0, "embedding": [0.1, 0.2]}], "usage": {}}
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual([p.name for p in gateway._embed_providers()], ["nvidia"])
            with patch.object(gateway, "_http_json", return_value=payload) as http:
                result = gateway.embed(
                    texts=["Go"], purpose="embed_job", conn=None, input_type="passage"
                )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(http.call_args.kwargs["body"]["input_type"], "passage")


if __name__ == "__main__":
    unittest.main()
