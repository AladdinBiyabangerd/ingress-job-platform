"""AI #2 helpers: cosine blend, embed gateway, SQLite stays ai_rerank=false."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.embeddings import (
    content_hash,
    cosine_similarity,
    job_embed_text,
    parse_vector,
    profile_embed_text,
    vector_literal,
)
from app.matching import W_SEMANTIC, W_STRUCT, _apply_semantic_rerank, rerank_enabled


class CosineBlendTests(unittest.TestCase):
    def test_cosine_identical(self):
        v = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0)

    def test_cosine_orthogonal(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_parse_and_literal_roundtrip(self):
        vals = [0.1, -0.25, 1.5]
        lit = vector_literal(vals)
        parsed = parse_vector(lit)
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed), 3)
        for a, b in zip(parsed, vals):
            self.assertAlmostEqual(a, b, places=5)

    def test_content_hash_stable(self):
        a = content_hash("m", "hello")
        b = content_hash("m", "hello")
        c = content_hash("m", "hello!")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_job_and_profile_text_skip_pii(self):
        job = job_embed_text(
            title="Java Developer",
            category="Backend",
            skills=["Java", "Spring"],
            text="Build APIs",
        )
        self.assertIn("Java", job)
        self.assertIn("Backend", job)
        profile = profile_embed_text(
            {
                "headline": "Backend",
                "seniority": "senior",
                "contact": {"email": "secret@example.com", "full_name": "Aysel"},
                "skills": [{"name": "Java"}],
                "work_history": [{"title": "Engineer", "company": "HiddenCo", "skills": ["Kafka"]}],
            }
        )
        self.assertIn("Java", profile)
        self.assertIn("Engineer", profile)
        self.assertNotIn("secret@example.com", profile)
        self.assertNotIn("Aysel", profile)

    def test_blend_weights(self):
        struct = 0.8
        semantic = 0.5
        blended = round(W_STRUCT * struct + W_SEMANTIC * semantic, 4)
        self.assertEqual(blended, 0.71)


class RerankFlagTests(unittest.TestCase):
    def test_flag_off(self):
        with patch.dict(os.environ, {"AI_RERANK_ENABLED": "0"}, clear=False):
            self.assertFalse(rerank_enabled())

    def test_apply_noop_without_postgres(self):
        class FakeConn:
            def execute(self, *a, **k):
                raise AssertionError("should not query")

        with patch.dict(os.environ, {"AI_RERANK_ENABLED": "1", "DATABASE_URL": ""}, clear=False):
            with patch("app.jobs_db.postgres_enabled", return_value=False):
                ok = _apply_semantic_rerank(
                    FakeConn(),
                    user_id="u1",
                    pool=[{"job_id": 1, "score": 0.9, "components": {}}],
                )
        self.assertFalse(ok)

    def test_apply_blends_when_vectors_present(self):
        profile_vec = [1.0, 0.0]
        job_a = [1.0, 0.0]  # cosine 1.0
        job_b = [0.0, 1.0]  # cosine 0.0
        pool = [
            {"job_id": 1, "score": 0.5, "components": {"skills": 0.5}},
            {"job_id": 2, "score": 0.9, "components": {"skills": 0.9}},
        ]

        with patch.dict(os.environ, {"AI_RERANK_ENABLED": "1"}, clear=False):
            with patch("app.jobs_db.postgres_enabled", return_value=True):
                with patch("app.embeddings.pgvector_available", return_value=True):
                    with patch("app.embeddings.embedding_model", return_value="text-embedding-3-small"):
                        with patch(
                            "app.embeddings.get_embedding",
                            return_value=(profile_vec, "hash"),
                        ):
                            with patch(
                                "app.embeddings.load_embeddings",
                                return_value={"1": job_a, "2": job_b},
                            ):
                                ok = _apply_semantic_rerank(
                                    object(),
                                    user_id="u1",
                                    pool=pool,
                                )
        self.assertTrue(ok)
        # job1: 0.7*0.5 + 0.3*1.0 = 0.65; job2: 0.7*0.9 + 0.3*0.0 = 0.63
        self.assertEqual(pool[0]["score"], 0.65)
        self.assertEqual(pool[1]["score"], 0.63)
        self.assertTrue(pool[0]["ai_rerank"])
        self.assertEqual(pool[0]["components"]["semantic"], 1.0)


class EmbedGatewayTests(unittest.TestCase):
    def test_embed_disabled_without_key(self):
        from app.ai_gateway import embed

        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "AI_GATEWAY_ENABLED": "0"},
            clear=False,
        ):
            result = embed(texts=["Java Spring"], purpose="embed_job", conn=None)
        self.assertFalse(result.ok)
        self.assertIn(result.error, {"ai_disabled", "ai_no_key"})

    def test_embed_calls_provider(self):
        from app.ai_gateway import embed

        fake = {
            "vectors": [[0.1, 0.2, 0.3]],
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }
        env = {
            "OPENAI_API_KEY": "sk-test",
            "AI_GATEWAY_ENABLED": "1",
            "AI_GATEWAY_DAILY_CALL_LIMIT": "100",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("app.ai_gateway.gateway._openai_embed", return_value=fake) as api:
                result = embed(texts=["Java Spring"], purpose="embed_job", conn=None)
        self.assertTrue(result.ok)
        self.assertEqual(result.vectors[0], [0.1, 0.2, 0.3])
        api.assert_called_once()


class MatchWhyTests(unittest.TestCase):
    def test_append_why_soft_fail(self):
        from app.match_why import append_why_sentences

        matches = [
            {
                "job_id": 1,
                "title": "Java Dev",
                "company": "Acme",
                "explanation": "2/3 skills match: Java, Spring",
                "have": ["Java", "Spring"],
                "missing": ["Kafka"],
                "components": {"skills": 0.8},
            }
        ]
        with patch.dict(os.environ, {"AI_MATCH_WHY_ENABLED": "0"}, clear=False):
            append_why_sentences(
                None,
                matches=matches,
                lang="en",
                profile_version="t1",
            )
        self.assertEqual(matches[0]["explanation"], "2/3 skills match: Java, Spring")
        self.assertNotIn("ai_why", matches[0])

    def test_append_why_applies(self):
        from app.ai_gateway.gateway import GatewayResult
        from app.match_why import append_why_sentences

        matches = [
            {
                "job_id": 9,
                "title": "Java Dev",
                "company": "Acme",
                "explanation": "2/3 skills match: Java, Spring",
                "have": ["Java", "Spring"],
                "missing": ["Kafka"],
                "remote": True,
                "relocation": False,
                "job_seniority": "senior",
                "components": {"skills": 0.8, "semantic": 0.6},
            }
        ]
        fake = GatewayResult(ok=True, data={"why": "Strong overlap on Java and Spring for a senior backend role."})
        with patch.dict(os.environ, {"AI_MATCH_WHY_ENABLED": "1"}, clear=False):
            with patch("app.match_why.complete_json", return_value=fake):
                append_why_sentences(
                    None,
                    matches=matches,
                    lang="en",
                    profile_version="2026-10-05",
                )
        self.assertTrue(matches[0].get("ai_why"))
        self.assertIn("Strong overlap", matches[0]["explanation"])


if __name__ == "__main__":
    unittest.main()
