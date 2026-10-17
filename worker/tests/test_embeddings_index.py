"""HNSW index: table committed first, halfvec expression index above 2,000 dims."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from worker import embeddings as emb


class FakeConn:
    def __init__(self, fail_on: str = ""):
        self.sql: list[str] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_on = fail_on

    def execute(self, sql, params=()):
        self.sql.append(" ".join(str(sql).split()))
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("boom")
        return self

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class IndexSqlTests(unittest.TestCase):
    def test_small_dims_use_vector_ops(self):
        name, sql = emb.vector_index_sql(1536)
        self.assertEqual(name, "embeddings_hnsw")
        self.assertIn("vector_cosine_ops", sql)
        self.assertIn("IF NOT EXISTS", sql)

    def test_2048_uses_halfvec_expression(self):
        name, sql = emb.vector_index_sql(2048)
        self.assertEqual(name, "embeddings_hnsw_halfvec")
        self.assertIn("(embedding::halfvec(2048)) halfvec_cosine_ops", sql)

    def test_too_large_unsupported(self):
        self.assertIsNone(emb.vector_index_sql(4096))


class EnsureTests(unittest.TestCase):
    def setUp(self):
        emb._pgvector_ready = None
        emb._index_checked = False
        self.addCleanup(setattr, emb, "_pgvector_ready", None)
        self.addCleanup(setattr, emb, "_index_checked", False)

    def test_table_committed_even_if_index_fails(self):
        conn = FakeConn(fail_on="USING hnsw")
        with patch.object(emb, "_is_postgres", return_value=True), patch.object(
            emb, "column_dims", return_value=2048
        ):
            self.assertTrue(emb.ensure_embedding_tables(conn))
            self.assertEqual(conn.commits, 1)
            with self.assertLogs("ingress-job.worker.embeddings", level="WARNING") as logs:
                self.assertIsNone(emb.ensure_vector_index(conn))
        self.assertTrue(any("not created" in m for m in logs.output))
        self.assertEqual(conn.rollbacks, 1)
        self.assertFalse(emb._index_checked)

    def test_index_created_once(self):
        conn = FakeConn()
        with patch.object(emb, "_is_postgres", return_value=True), patch.object(
            emb, "column_dims", return_value=2048
        ):
            self.assertEqual(emb.ensure_vector_index(conn), "embeddings_hnsw_halfvec")
            self.assertIsNone(emb.ensure_vector_index(conn))
        self.assertEqual(sum("USING hnsw" in s for s in conn.sql), 1)

    def test_table_failure_not_ready(self):
        conn = FakeConn(fail_on="CREATE TABLE")
        with patch.object(emb, "_is_postgres", return_value=True):
            with self.assertLogs("ingress-job.worker.embeddings", level="WARNING"):
                self.assertFalse(emb.ensure_embedding_tables(conn))
        self.assertFalse(emb._pgvector_ready)


if __name__ == "__main__":
    unittest.main()
