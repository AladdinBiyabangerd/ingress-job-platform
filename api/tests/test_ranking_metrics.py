"""Metric math on hand-checked toy rankings (not real labels)."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from app.ranking_metrics import (
    aggregate,
    evaluate_query,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class MetricTests(unittest.TestCase):
    LABELS = {"1": 3, "2": 2, "3": 0, "4": 1}

    def test_ndcg_perfect_is_one(self):
        self.assertAlmostEqual(ndcg_at_k(["1", "2", "4", "3"], self.LABELS, 10), 1.0)

    def test_ndcg_hand_value(self):
        # ranking 2,1: dcg = 3/1 + 7/log2(3); ideal = 7/1 + 3/log2(3) + 1/2
        dcg = 3 + 7 / math.log2(3)
        idcg = 7 + 3 / math.log2(3) + 1 / 2
        self.assertAlmostEqual(ndcg_at_k(["2", "1"], self.LABELS, 10), dcg / idcg)

    def test_ndcg_undefined_without_positive(self):
        self.assertIsNone(ndcg_at_k(["1"], {"1": 0}, 10))

    def test_precision_recall_mrr(self):
        ranking = ["3", "4", "2", "9", "1"]
        self.assertAlmostEqual(precision_at_k(ranking, self.LABELS, 5), 2 / 5)
        self.assertAlmostEqual(recall_at_k(ranking[:3], self.LABELS, 20), 1 / 2)
        self.assertAlmostEqual(reciprocal_rank(ranking, self.LABELS), 1 / 3)
        self.assertEqual(reciprocal_rank(["3"], self.LABELS), 0.0)
        self.assertIsNone(recall_at_k(ranking, {"3": 1}, 20))

    def test_aggregate_skips_undefined(self):
        rows = [evaluate_query(["1"], self.LABELS), evaluate_query(["1"], {"1": 0})]
        agg = aggregate(rows)
        self.assertEqual(agg["queries"], 2)
        self.assertEqual(agg["ndcg@10_n"], 1)
        self.assertEqual(agg["mrr_n"], 2)


class ScriptTests(unittest.TestCase):
    def test_run_file_mode(self):
        import importlib.util

        path = Path(__file__).resolve().parents[1] / "scripts" / "eval_matching.py"
        spec = importlib.util.spec_from_file_location("eval_matching", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            labels = Path(tmp) / "l.jsonl"
            labels.write_text(
                "# toy\n" + json.dumps({"user_id": "u1", "labels": {"10": 3, "11": 0}}) + "\n",
                encoding="utf-8",
            )
            run = Path(tmp) / "r.json"
            run.write_text(json.dumps({"u1|": ["10", "11"]}), encoding="utf-8")
            queries = mod.load_labels(labels)
            report = mod.run_eval(queries, json.loads(run.read_text()), relevant_min=2)
            self.assertEqual(report["summary"]["ndcg@10"], 1.0)
            self.assertEqual(report["summary"]["mrr"], 1.0)
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(mod.main(["--labels", str(labels), "--run", str(run)]), 0)
            self.assertIn('"ndcg@10": 1.0', out.getvalue())
            bad = Path(tmp) / "bad.jsonl"
            bad.write_text(json.dumps({"user_id": "u", "labels": {"1": 7}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                mod.load_labels(bad)


if __name__ == "__main__":
    unittest.main()
