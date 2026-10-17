"""Cosine in SQL (pgvector <=>) with Python fallback; stale profile vectors are not used."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import embeddings as emb
from app.matching import _apply_semantic_rerank


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakePgConn:
    def __init__(self, rows=None, fail=False):
        self.sql: list[str] = []
        self.params: list[tuple] = []
        self.rows = rows or []
        self.fail = fail
        self.rolled_back = False

    def execute(self, sql, params=()):
        self.sql.append(sql)
        self.params.append(tuple(params))
        if self.fail:
            raise RuntimeError("operator does not exist")
        return _Rows(self.rows)

    def rollback(self):
        self.rolled_back = True


class SemanticScoresSqlTests(unittest.TestCase):
    def _patches(self):
        return (
            patch("app.embeddings._is_postgres", return_value=True),
            patch("app.embeddings.pgvector_available", return_value=True),
        )

    def test_uses_cosine_distance_operator(self):
        conn = FakePgConn(rows=[("1", 0.8), ("2", -0.2), ("3", None)])
        a, b = self._patches()
        with a, b:
            out = emb.semantic_scores(conn, profile_id="u1", job_ids=["1", "2", "3"], model="m")
        self.assertEqual(out, {"1": 0.8, "2": 0.0})
        self.assertIn("<=>", conn.sql[0])
        self.assertIn("1 - (j.embedding <=> p.embedding)", conn.sql[0])
        self.assertEqual(conn.params[0][:4], ("profile", "u1", "job", "m"))

    def test_sql_failure_returns_none_and_rolls_back(self):
        conn = FakePgConn(fail=True)
        a, b = self._patches()
        with a, b:
            out = emb.semantic_scores(conn, profile_id="u1", job_ids=["1"], model="m")
        self.assertIsNone(out)
        self.assertTrue(conn.rolled_back)

    def test_not_postgres_returns_none(self):
        with patch("app.embeddings._is_postgres", return_value=False):
            self.assertIsNone(emb.semantic_scores(object(), profile_id="u", job_ids=["1"]))


class StaleProfileTests(unittest.TestCase):
    PROFILE = {"headline": "Backend", "skills": [{"name": "Java"}]}

    def _run(self, *, stored_hash, allow_provider, embed_ok=True, after_hash=None):
        model = "text-embedding-3-small"
        fresh = emb.content_hash(model, emb.profile_embed_text(self.PROFILE))
        rows = [([1.0, 0.0], stored_hash), ([1.0, 0.0], after_hash or fresh)]
        pool = [{"job_id": 1, "score": 0.6, "components": {}}]
        with patch.dict(os.environ, {"AI_RERANK_ENABLED": "1"}, clear=False), patch(
            "app.jobs_db.postgres_enabled", return_value=True
        ), patch("app.embeddings.pgvector_available", return_value=True), patch(
            "app.embeddings.ensure_embedding_tables", return_value=True
        ), patch("app.embeddings.embedding_model", return_value=model), patch(
            "app.embeddings.get_embedding", side_effect=rows
        ), patch(
            "app.embeddings.semantic_scores", return_value={"1": 0.9}
        ), patch(
            "app.embeddings.embed_and_store", return_value=embed_ok
        ) as store, patch(
            "app.embeddings.schedule_profile_reembed", return_value=True
        ) as sched:
            ok = _apply_semantic_rerank(
                object(), user_id="u1", pool=pool, profile=self.PROFILE, allow_provider=allow_provider
            )
        return ok, pool, store, sched, fresh

    def test_fresh_vector_used(self):
        model = "text-embedding-3-small"
        fresh = emb.content_hash(model, emb.profile_embed_text(self.PROFILE))
        ok, pool, store, sched, _ = self._run(stored_hash=fresh, allow_provider=False)
        self.assertTrue(ok)
        self.assertEqual(pool[0]["components"]["semantic"], 0.9)
        self.assertEqual(pool[0]["score"], 0.6)
        store.assert_not_called()
        sched.assert_not_called()

    def test_stale_in_request_path_skips_and_schedules(self):
        ok, pool, store, sched, _ = self._run(stored_hash="old", allow_provider=False)
        self.assertFalse(ok)
        self.assertNotIn("semantic", pool[0]["components"])
        store.assert_not_called()
        sched.assert_called_once_with("u1")

    def test_stale_in_warm_path_reembeds_inline(self):
        ok, pool, store, sched, _ = self._run(stored_hash="old", allow_provider=True)
        self.assertTrue(ok)
        store.assert_called_once()
        sched.assert_not_called()
        self.assertEqual(pool[0]["components"]["semantic"], 0.9)

    def test_stale_warm_embed_failure_falls_back(self):
        ok, pool, _store, _sched, _ = self._run(stored_hash="old", allow_provider=True, embed_ok=False)
        self.assertFalse(ok)
        self.assertNotIn("semantic", pool[0]["components"])


class ReembedScheduleTests(unittest.TestCase):
    def test_dedupe_cooldown(self):
        emb._reembed_last.clear()
        self.addCleanup(emb._reembed_last.clear)
        with patch("app.embeddings.threading.Thread") as thread:
            self.assertTrue(emb.schedule_profile_reembed("u9"))
            self.assertFalse(emb.schedule_profile_reembed("u9"))
        thread.assert_called_once()


if __name__ == "__main__":
    unittest.main()
