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
from app.match_llm_rerank import W_BLENDED, W_RELEVANCE, apply_llm_rerank
from app.matching import (
    FEEDBACK_DOWN_FACTOR,
    W_SEMANTIC,
    W_STRUCT,
    _apply_feedback_demotion,
    _apply_semantic_rerank,
    rerank_enabled,
)


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
            remote=True,
            relocation=False,
        )
        self.assertIn("Java", job)
        self.assertIn("Backend", job)
        self.assertIn("Remote", job)
        self.assertNotIn("Relocation", job)
        profile = profile_embed_text(
            {
                "headline": "Backend",
                "seniority": "senior",
                "contact": {"email": "secret@example.com", "full_name": "Aysel"},
                "skills": [{"name": "Java"}],
                "soft_skills": ["communication", "teamwork"],
                "work_history": [
                    {
                        "title": "Engineer",
                        "company": "HiddenCo",
                        "summary": "Built Kafka pipelines for payments.",
                        "skills": ["Kafka"],
                    }
                ],
                "languages": [{"code": "en", "level": "C1"}],
                "preferences": {"remote": True, "relocation": False},
            }
        )
        self.assertIn("Java", profile)
        self.assertIn("Engineer", profile)
        self.assertIn("Built Kafka pipelines", profile)
        self.assertIn("Languages: en:C1", profile)
        self.assertIn("Preferences: remote, no relocation", profile)
        self.assertNotIn("secret@example.com", profile)
        self.assertNotIn("Aysel", profile)
        self.assertNotIn("communication", profile)
        self.assertNotIn("HiddenCo", profile)

    def test_job_embed_snippet_up_to_800(self):
        body = "x" * 900
        job = job_embed_text(title="T", text=body)
        # title + newline + 800-char snippet
        self.assertIn("x" * 800, job)
        self.assertNotIn("x" * 801, job)

    def test_profile_work_capped_at_three_with_summary(self):
        profile = profile_embed_text(
            {
                "skills": [{"name": "Java"}],
                "work_history": [
                    {"title": f"Role{i}", "summary": f"Did work {i} " + ("y" * 200)}
                    for i in range(5)
                ],
            }
        )
        self.assertIn("Role0:", profile)
        self.assertIn("Role2:", profile)
        self.assertNotIn("Role3:", profile)
        # summary truncated to 120 chars per role
        self.assertNotIn("y" * 121, profile)

    def test_blend_weights(self):
        struct = 0.8
        semantic = 0.5
        blended = round(W_STRUCT * struct + W_SEMANTIC * semantic, 4)
        self.assertEqual(blended, 0.71)


class RerankFlagTests(unittest.TestCase):
    def test_flag_off(self):
        with patch.dict(os.environ, {"AI_RERANK_ENABLED": "0"}, clear=False):
            self.assertFalse(rerank_enabled())

    def test_db_flag_off_with_env_on(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        from app.ai_flags import set_flags

        tmp = tempfile.TemporaryDirectory()
        try:
            conn = sqlite3.connect(Path(tmp.name) / "t.sqlite")
            set_flags(conn, {"rerank": False}, updated_by="test")
            with patch.dict(os.environ, {"AI_RERANK_ENABLED": "1"}, clear=False):
                self.assertFalse(rerank_enabled(conn))
            conn.close()
        finally:
            tmp.cleanup()

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


class LlmRerankTests(unittest.TestCase):
    def test_flag_off_noop(self):
        pool = [{"job_id": 1, "score": 0.8, "components": {}, "have": ["Java"], "missing": []}]
        with patch.dict(os.environ, {"AI_LLM_RERANK_ENABLED": "0"}, clear=False):
            ok = apply_llm_rerank(
                None,
                matches=pool,
                profile={"seniority": "senior", "skills": [{"name": "Java"}]},
                profile_version="v1",
            )
        self.assertFalse(ok)
        self.assertEqual(pool[0]["score"], 0.8)
        self.assertNotIn("ai_llm_rerank", pool[0])

    def test_blend_formula(self):
        from app.ai_gateway.gateway import GatewayResult

        pool = [
            {
                "job_id": 1,
                "score": 0.8,
                "title": "Java Dev",
                "company": "Acme",
                "have": ["Java"],
                "missing": ["Kafka"],
                "components": {},
            },
            {
                "job_id": 2,
                "score": 0.6,
                "title": "PM",
                "company": "Beta",
                "have": [],
                "missing": ["Jira"],
                "components": {},
            },
        ]
        fake = GatewayResult(
            ok=True,
            data={
                "scores": [
                    {"job_id": 1, "relevance": 5, "note": "Strong Java overlap"},
                    {"job_id": 2, "relevance": 1, "note": "No skill overlap"},
                ]
            },
        )
        with patch.dict(os.environ, {"AI_LLM_RERANK_ENABLED": "1"}, clear=False):
            with patch("app.match_llm_rerank.complete_json", return_value=fake):
                ok = apply_llm_rerank(
                    None,
                    matches=pool,
                    profile={"seniority": "senior", "skills": [{"name": "Java"}], "total_years": 5},
                    profile_version="v1",
                )
        self.assertTrue(ok)
        # 0.55*0.8 + 0.45*(5/5) = 0.44 + 0.45 = 0.89
        self.assertEqual(pool[0]["score"], round(W_BLENDED * 0.8 + W_RELEVANCE * 1.0, 4))
        self.assertEqual(pool[0]["components"]["llm_relevance"], 5)
        self.assertTrue(pool[0]["ai_llm_rerank"])
        # 0.55*0.6 + 0.45*(1/5) = 0.33 + 0.09 = 0.42
        self.assertEqual(pool[1]["score"], round(W_BLENDED * 0.6 + W_RELEVANCE * 0.2, 4))

    def test_soft_fail_keeps_scores(self):
        from app.ai_gateway.gateway import GatewayResult

        pool = [{"job_id": 1, "score": 0.77, "have": ["Java"], "missing": [], "components": {}}]
        with patch.dict(os.environ, {"AI_LLM_RERANK_ENABLED": "1"}, clear=False):
            with patch(
                "app.match_llm_rerank.complete_json",
                return_value=GatewayResult(ok=False, error="ai_provider_error"),
            ):
                ok = apply_llm_rerank(
                    None,
                    matches=pool,
                    profile={"skills": [{"name": "Java"}]},
                    profile_version="v1",
                )
        self.assertFalse(ok)
        self.assertEqual(pool[0]["score"], 0.77)

    def test_feedback_demotion(self):
        pool = [
            {"job_id": 1, "score": 1.0, "feedback": {"vote": "down", "reason": "technology"}, "components": {}},
            {"job_id": 2, "score": 0.8, "feedback": {"vote": "up", "reason": ""}, "components": {}},
            {"job_id": 3, "score": 0.5, "feedback": None, "components": {}},
        ]
        _apply_feedback_demotion(pool)
        self.assertEqual(pool[0]["score"], round(1.0 * FEEDBACK_DOWN_FACTOR, 4))
        self.assertEqual(pool[0]["components"]["feedback_demotion"], FEEDBACK_DOWN_FACTOR)
        self.assertEqual(pool[1]["score"], 0.8)
        self.assertEqual(pool[2]["score"], 0.5)


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
        from app.match_why import PROMPT_VERSION, append_why_sentences, _build_user

        matches = [
            {
                "job_id": 9,
                "title": "Java Dev",
                "company": "Acme",
                "explanation": "2/3 skills match: Java, Spring",
                "have": ["Java", "Spring"],
                "missing": ["Kafka", "Redis", "Kubernetes"],
                "remote": True,
                "relocation": False,
                "job_seniority": "senior",
                "components": {
                    "skills": 0.8,
                    "semantic": 0.6,
                    "llm_relevance": 4,
                    "llm_note": "Java Spring overlap",
                },
            }
        ]
        candidate = {
            "seniority": "senior",
            "total_years": 6,
            "preferences": {"remote": True, "relocation": False},
        }
        user = _build_user(
            lang="en",
            profile_version="2026-10-05",
            match=matches[0],
            candidate=candidate,
        )
        self.assertEqual(PROMPT_VERSION, "match-why-v2")
        self.assertIn("CandidateSeniority: senior", user)
        self.assertIn("CandidateYears: 6", user)
        self.assertIn("MissingSkillsTop3: Kafka, Redis, Kubernetes", user)
        self.assertIn("LlmNote: Java Spring overlap", user)

        fake = GatewayResult(ok=True, data={"why": "Strong overlap on Java and Spring for a senior backend role."})
        with patch.dict(os.environ, {"AI_MATCH_WHY_ENABLED": "1"}, clear=False):
            with patch("app.match_why.complete_json", return_value=fake) as api:
                append_why_sentences(
                    None,
                    matches=matches,
                    lang="en",
                    profile_version="2026-10-05",
                    candidate=candidate,
                )
        self.assertTrue(matches[0].get("ai_why"))
        self.assertIn("Strong overlap", matches[0]["explanation"])
        self.assertEqual(api.call_args.kwargs["prompt_version"], "match-why-v2")


if __name__ == "__main__":
    unittest.main()
