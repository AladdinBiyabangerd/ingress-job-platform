"""P0: one active embedding provider, NVIDIA input_type, writer == reader key."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.ai_gateway import gateway
from app import embeddings as emb

BOTH_KEYS = {
    "NVIDIA_API_KEY": "nv-test",
    "OPENAI_API_KEY": "sk-test",
    "AI_GATEWAY_ENABLED": "1",
    "AI_EMBEDDING_MODEL": "",
    "NVIDIA_EMBED_MODEL": "",
    "AI_EMBED_PROVIDERS": "",
}


def _fake_embed_payload(n: int = 1, dims: int = 3) -> dict:
    return {
        "data": [{"index": i, "embedding": [0.1] * dims} for i in range(n)],
        "usage": {"prompt_tokens": 3, "total_tokens": 3},
    }


class ActiveProviderTests(unittest.TestCase):
    def setUp(self):
        gateway._cooldown_reset()
        self.addCleanup(gateway._cooldown_reset)

    def test_default_order_picks_nvidia_only(self):
        with patch.dict(os.environ, BOTH_KEYS, clear=False):
            providers = gateway._embed_providers()
            self.assertEqual([p.name for p in providers], ["nvidia"])
            self.assertEqual(gateway.embedding_model_name(), "nvidia/nemotron-3-embed-1b")
            self.assertEqual(emb.embedding_model(), "nvidia/nemotron-3-embed-1b")

    def test_order_env_picks_openai(self):
        env = dict(BOTH_KEYS, AI_EMBED_PROVIDERS="openai,nvidia")
        with patch.dict(os.environ, env, clear=False):
            providers = gateway._embed_providers()
            self.assertEqual([p.name for p in providers], ["openai"])
            self.assertEqual(gateway.embedding_model_name(), "text-embedding-3-small")

    def test_explicit_model_pins_provider(self):
        env = dict(BOTH_KEYS, AI_EMBEDDING_MODEL="text-embedding-3-small")
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual([p.name for p in gateway._embed_providers()], ["openai"])
        env = dict(BOTH_KEYS, AI_EMBEDDING_MODEL="nvidia/nemotron-3-embed-1b",
                   AI_EMBED_PROVIDERS="openai")
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual([p.name for p in gateway._embed_providers()], ["nvidia"])

    def test_no_key_no_provider(self):
        env = dict(BOTH_KEYS, NVIDIA_API_KEY="", OPENAI_API_KEY="")
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(gateway._embed_providers(), [])


class InputTypeTests(unittest.TestCase):
    def setUp(self):
        gateway._cooldown_reset()
        self.addCleanup(gateway._cooldown_reset)

    def test_nvidia_body_carries_input_type(self):
        with patch.dict(os.environ, BOTH_KEYS, clear=False):
            with patch.object(gateway, "_http_json", return_value=_fake_embed_payload()) as http:
                result = gateway.embed(
                    texts=["Java Spring"], purpose="embed_job", conn=None, input_type="passage"
                )
        self.assertTrue(result.ok, result.error)
        body = http.call_args.kwargs["body"]
        self.assertEqual(body["input_type"], "passage")
        self.assertEqual(body["model"], "nvidia/nemotron-3-embed-1b")
        self.assertEqual(result.model, "nvidia/nemotron-3-embed-1b")

    def test_openai_body_has_no_input_type(self):
        env = dict(BOTH_KEYS, AI_EMBED_PROVIDERS="openai")
        with patch.dict(os.environ, env, clear=False):
            with patch.object(gateway, "_http_json", return_value=_fake_embed_payload()) as http:
                result = gateway.embed(
                    texts=["Java"], purpose="embed_profile", conn=None, input_type="query"
                )
        self.assertTrue(result.ok, result.error)
        self.assertNotIn("input_type", http.call_args.kwargs["body"])

    def test_bad_input_type_rejected(self):
        with patch.dict(os.environ, BOTH_KEYS, clear=False):
            with patch.object(gateway, "_http_json") as http:
                result = gateway.embed(texts=["x"], purpose="embed_job", conn=None, input_type="doc")
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "ai_bad_input_type")
        http.assert_not_called()

    def test_nvidia_failure_does_not_fall_back_to_openai(self):
        err = gateway.ProviderHTTPError("HTTP 500: boom", 500)
        with patch.dict(os.environ, BOTH_KEYS, clear=False):
            with patch.object(gateway, "_http_json", side_effect=err) as http:
                result = gateway.embed(
                    texts=["Java"], purpose="embed_job", conn=None, input_type="passage"
                )
        self.assertFalse(result.ok)
        self.assertEqual(http.call_count, 1)
        self.assertIn("integrate.api.nvidia.com", http.call_args.args[0])


class ContentHashTests(unittest.TestCase):
    def test_nvidia_hash_is_versioned(self):
        nv = emb.content_hash("nvidia/nemotron-3-embed-1b", "hello")
        self.assertEqual(nv, emb.content_hash("nvidia/nemotron-3-embed-1b", "hello"))
        import hashlib

        legacy = hashlib.sha256(b"nvidia/nemotron-3-embed-1b\nhello").hexdigest()
        self.assertNotEqual(nv, legacy)
        oa = emb.content_hash("text-embedding-3-small", "hello")
        self.assertEqual(oa, hashlib.sha256(b"text-embedding-3-small\nhello").hexdigest())


class EmbedAndStoreTests(unittest.TestCase):
    def _run(self, *, entity_type: str, result_model: str, vector=None):
        from app.ai_gateway.gateway import EmbedResult

        fake = EmbedResult(ok=True, vectors=[vector or [0.1, 0.2]], model=result_model)

        class Conn:
            def commit(self):
                pass

        with patch("app.ai_flags.feature_on", return_value=True), patch.object(
            emb, "pgvector_available", return_value=True
        ), patch.object(emb, "get_embedding", return_value=None), patch.object(
            emb, "embedding_model", return_value="nvidia/nemotron-3-embed-1b"
        ), patch("app.ai_gateway.embed", return_value=fake) as embed_mock, patch.object(
            emb, "upsert_embedding", return_value=True
        ) as upsert:
            ok = emb.embed_and_store(Conn(), entity_type=entity_type, entity_id="7", text="Java")
        return ok, embed_mock, upsert

    def test_profile_uses_query_and_reader_key(self):
        ok, embed_mock, upsert = self._run(
            entity_type=emb.ENTITY_PROFILE, result_model="nvidia/nemotron-3-embed-1b"
        )
        self.assertTrue(ok)
        self.assertEqual(embed_mock.call_args.kwargs["input_type"], "query")
        self.assertEqual(upsert.call_args.kwargs["model"], "nvidia/nemotron-3-embed-1b")

    def test_job_uses_passage(self):
        ok, embed_mock, _ = self._run(
            entity_type=emb.ENTITY_JOB, result_model="nvidia/nemotron-3-embed-1b"
        )
        self.assertTrue(ok)
        self.assertEqual(embed_mock.call_args.kwargs["input_type"], "passage")

    def test_model_mismatch_not_stored(self):
        ok, _, upsert = self._run(entity_type=emb.ENTITY_JOB, result_model="text-embedding-3-small")
        self.assertFalse(ok)
        upsert.assert_not_called()


class DimsGuardTests(unittest.TestCase):
    def test_upsert_skips_wrong_size(self):
        class Conn:
            def execute(self, *a, **k):
                raise AssertionError("must not insert")

        with patch.object(emb, "pgvector_available", return_value=True), patch.object(
            emb, "column_dims", return_value=2048
        ):
            ok = emb.upsert_embedding(
                Conn(), entity_type="job", entity_id="1", text="x", vector=[0.1] * 1536,
                model="nvidia/nemotron-3-embed-1b",
            )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
