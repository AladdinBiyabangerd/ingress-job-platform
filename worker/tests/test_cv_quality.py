"""Layout-agnostic quality score + automatic rules -> AI fallback flow."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import GatewayResult, ensure_ai_tables
from worker.cv_parse import assess_quality, maybe_ai_fallback, parse_text
from worker.db import Store

GOOD = """Jane Doe
Backend Engineer
jane.doe@example.com | +1 415 555 0134 | Berlin, Germany

Experience
Senior Backend Engineer
Acme GmbH | Jan 2020 - Present
- Built Python and Kafka services on AWS with Docker and PostgreSQL

Software Engineer
Beta Corp | Mar 2016 - Dec 2019
- Java and Spring Boot APIs, Redis caching

Education
BSc Computer Science, TU Berlin 2015

Skills
Python, Java, Kafka, Docker, AWS, PostgreSQL, Redis, Spring
"""

POOR = """Someone
email@example.com

Did stuff at companies for a while.
Used java and spring sometimes.
Worked with several teams on delivery of internal tools and customer projects.
"""

ENV = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}


def _llm() -> dict:
    return {
        "headline": "Java Developer",
        "summary": "Java developer.",
        "seniority": "middle",
        "total_years": 4,
        "work_history": [
            {"title": "Java Developer", "company": "Acme", "location": "", "start": "2020-01",
             "end": None, "summary": "Built services", "skills": ["Java"]},
        ],
        "skills": [
            {"name": "Java", "years": 4, "level": "", "evidence": "Used java", "confidence": 0.9},
            {"name": "Spring", "years": 3, "level": "", "evidence": "spring sometimes", "confidence": 0.9},
        ],
        "soft_skills": [],
        "languages": [],
        "education": [{"degree": "BSc", "field": "CS", "school": "BSU", "year": 2018}],
    }


class QualityScoreTest(unittest.TestCase):
    def test_good_cv_scores_high_without_issues_on_work(self):
        q = assess_quality(parse_text(GOOD), GOOD)
        self.assertGreaterEqual(q["score"], q["threshold"])
        self.assertFalse(q["needs_ai"])
        self.assertNotIn("work_missing", q["issues"])

    def test_poor_cv_needs_ai(self):
        q = assess_quality(parse_text(POOR), POOR)
        self.assertLess(q["score"], q["threshold"])
        self.assertTrue(q["needs_ai"])

    def test_sanity_checks_flag_garbage(self):
        prof = parse_text(GOOD)
        prof["work_history"] = [
            {"title": "Berlin, Germany", "company": "Acme", "start": "2020-05", "end": "2019-01"},
            {"title": "BSc Computer Science", "company": "", "start": "", "end": ""},
        ]
        prof["contact"]["city"] = "BSc Computer Science, TU Berlin"
        issues = assess_quality(prof, GOOD)["issues"]
        for code in ("work_garbage_title", "work_date_order", "work_undated", "city_is_education"):
            self.assertIn(code, issues)
        self.assertTrue(assess_quality(prof, GOOD)["needs_ai"])  # critical issue forces AI


class AutoFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")
        ensure_ai_tables(self.store.conn)

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def test_good_cv_does_not_call_ai(self):
        rules = parse_text(GOOD)
        with patch.dict(os.environ, ENV, clear=False), patch("worker.cv_parse.ai_fallback.complete_json") as api:
            out = maybe_ai_fallback(rules, GOOD, conn=self.store.conn)
        api.assert_not_called()
        self.assertEqual(out["parse_meta"]["parse_source"], "rules")
        self.assertIn("score", out["parse_meta"]["quality"])

    def test_poor_cv_calls_ai_and_records_source(self):
        rules = parse_text(POOR)
        with patch.dict(os.environ, ENV, clear=False), patch(
            "worker.cv_parse.ai_fallback.complete_json", return_value=GatewayResult(ok=True, data=_llm())
        ) as api:
            out = maybe_ai_fallback(rules, POOR + "\nJava Spring\n", conn=self.store.conn)
        api.assert_called_once()
        meta = out["parse_meta"]
        self.assertIn(meta["parse_source"], {"ai", "mixed"})
        self.assertEqual(meta["ai_fallback"], "applied")
        self.assertIn("quality", meta["ai_reasons"])
        self.assertGreater(meta["quality"]["score"], meta["quality"]["score_before"])
        self.assertEqual(out["contact"]["email"], "email@example.com")

    def test_too_short_text_never_calls_ai(self):
        short = "Someone\nemail@example.com\nDid stuff."
        rules = parse_text(short)
        with patch.dict(os.environ, ENV, clear=False), patch("worker.cv_parse.ai_fallback.complete_json") as api:
            out = maybe_ai_fallback(rules, short, conn=self.store.conn)
        api.assert_not_called()
        meta = out["parse_meta"]
        self.assertEqual(meta["ai_fallback"], "skipped")
        self.assertEqual(meta["ai_error"], "text_too_short")
        self.assertIn("text_too_short", meta["quality"]["issues"])
        self.assertFalse(assess_quality(rules, short)["needs_ai"])

    def test_empty_text_never_calls_ai(self):
        with patch.dict(os.environ, ENV, clear=False), patch("worker.cv_parse.ai_fallback.complete_json") as api:
            out = maybe_ai_fallback(parse_text(""), "", conn=self.store.conn)
        api.assert_not_called()
        self.assertEqual(out["parse_meta"].get("ai_fallback"), "skipped")

    def test_garbled_text_never_calls_ai(self):
        noise = "\u0b85\u0b86\u0b87" * 60 + " email@example.com"
        with patch.dict(os.environ, ENV, clear=False), patch("worker.cv_parse.ai_fallback.complete_json") as api:
            out = maybe_ai_fallback(parse_text(noise), noise, conn=self.store.conn)
        api.assert_not_called()
        self.assertEqual(out["parse_meta"]["ai_error"], "text_garbled")

    def test_ai_failure_keeps_rules(self):
        rules = parse_text(POOR)
        before = rules["headline"]
        with patch.dict(os.environ, ENV, clear=False), patch(
            "worker.cv_parse.ai_fallback.complete_json", return_value=GatewayResult(ok=False, error="timeout")
        ):
            out = maybe_ai_fallback(rules, POOR, conn=self.store.conn)
        self.assertEqual(out["parse_meta"]["parse_source"], "rules")
        self.assertEqual(out["parse_meta"]["ai_fallback"], "failed")
        self.assertEqual(out["headline"], before)

    def test_ai_exception_keeps_rules(self):
        rules = parse_text(POOR)
        with patch.dict(os.environ, ENV, clear=False), patch(
            "worker.cv_parse.ai_fallback.complete_json", side_effect=RuntimeError("boom")
        ):
            out = maybe_ai_fallback(rules, POOR, conn=self.store.conn)
        self.assertEqual(out["parse_meta"]["parse_source"], "rules")
        self.assertEqual(out["parse_meta"]["ai_fallback"], "failed")

    def test_only_weak_parts_replaced(self):
        """Good rule work history survives; AI fills the missing education only."""
        rules = parse_text(GOOD)
        rules["education"] = []
        rules["parse_meta"]["confidence"] = 0.9
        keep = [dict(j) for j in rules["work_history"]]
        rules["skills"] = rules["skills"][:2]  # thin -> AI runs
        with patch.dict(os.environ, ENV, clear=False), patch(
            "worker.cv_parse.ai_fallback.complete_json", return_value=GatewayResult(ok=True, data=_llm())
        ):
            out = maybe_ai_fallback(rules, GOOD, conn=self.store.conn)
        self.assertEqual([j["company"] for j in out["work_history"]], [j["company"] for j in keep])
        self.assertTrue(out["education"])
        self.assertEqual(out["parse_meta"]["parse_source"], "mixed")


if __name__ == "__main__":
    unittest.main()
