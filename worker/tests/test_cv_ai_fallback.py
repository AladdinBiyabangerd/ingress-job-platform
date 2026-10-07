"""AI #1 CV parse fallback (plan §5.1)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import GatewayResult, ensure_ai_tables
from worker.cv_parse import maybe_ai_fallback, parse_text
from worker.cv_parse.ai_fallback import filter_skills
from worker.db import Store

LOW_TEXT = """
Someone
email@example.com

Did stuff at companies for a while.
Used java and spring sometimes.
"""


class SkillFilterTest(unittest.TestCase):
    def test_keeps_dictionary_skills_present_in_text(self):
        text = "Built APIs with Java, Spring and Kafka on AWS."
        skills = filter_skills(
            [
                {"name": "Java", "years": 3, "level": "advanced"},
                {"name": "Haskell", "years": 1, "level": ""},
                {"name": "Teleportation", "years": 9, "level": "expert"},
                {"name": "k8s", "years": 2, "level": ""},
            ],
            text,
        )
        names = {s["name"] for s in skills}
        self.assertIn("Java", names)
        self.assertNotIn("Haskell", names)
        self.assertNotIn("Teleportation", names)
        # k8s → Kubernetes only if Kubernetes/k8s appears in text
        self.assertNotIn("Kubernetes", names)

    def test_synonym_maps_to_canonical_when_in_text(self):
        text = "Deployed to kubernetes clusters daily."
        skills = filter_skills([{"name": "k8s", "years": 2, "level": ""}], text)
        self.assertEqual([s["name"] for s in skills], ["Kubernetes"])


class AiFallbackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        ensure_ai_tables(self.store.conn)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_skips_when_confidence_high(self):
        profile = parse_text(
            (Path(__file__).parent / "fixtures" / "cv" / "sample_backend.txt").read_text(
                encoding="utf-8"
            )
        )
        with patch("worker.cv_parse.ai_fallback.complete_json") as api:
            out = maybe_ai_fallback(profile, "unused", conn=self.store.conn)
        api.assert_not_called()
        self.assertEqual(out["parse_meta"]["method"], "rules")
        self.assertGreaterEqual(out["parse_meta"]["confidence"], 0.55)

    def test_applies_llm_and_keeps_rules_contact(self):
        rules = parse_text(LOW_TEXT)
        self.assertLess(rules["parse_meta"]["confidence"], 0.55)
        llm = {
            "headline": "Java Developer",
            "summary": "Java developer with Spring experience.",
            "seniority": "middle",
            "total_years": 4,
            "work_history": [
                {
                    "title": "Java Developer",
                    "company": "Acme",
                    "location": "",
                    "start": "2020-01",
                    "end": None,
                    "summary": "Built services",
                    "skills": ["Java", "Spring"],
                }
            ],
            "skills": [
                {"name": "Java", "years": 4, "level": "advanced"},
                {"name": "Spring", "years": 3, "level": "advanced"},
                {"name": "InventedSkill", "years": 1, "level": ""},
            ],
            "languages": [{"code": "en", "level": "B2"}],
            "education": [
                {"degree": "BSc", "field": "CS", "school": "BSU", "year": 2018}
            ],
        }
        env = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with patch(
                "worker.cv_parse.ai_fallback.complete_json",
                return_value=GatewayResult(
                    ok=True,
                    data=llm,
                    prompt_tokens=100,
                    completion_tokens=50,
                    cached=False,
                ),
            ):
                out = maybe_ai_fallback(rules, LOW_TEXT + "\nJava Spring\n", conn=self.store.conn)
        self.assertEqual(out["parse_meta"]["method"], "llm")
        self.assertEqual(out["parse_meta"]["ai_fallback"], "applied")
        self.assertEqual(out["contact"]["email"], "email@example.com")
        self.assertEqual(out["headline"], "Java Developer")
        names = {s["name"] for s in out["skills"]}
        self.assertIn("Java", names)
        self.assertIn("Spring", names)
        self.assertNotIn("InventedSkill", names)
        self.assertGreaterEqual(out["parse_meta"]["confidence"], 0.55)

    def test_soft_fail_keeps_rules(self):
        rules = parse_text(LOW_TEXT)
        env = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with patch(
                "worker.cv_parse.ai_fallback.complete_json",
                return_value=GatewayResult(ok=False, error="ai_provider_error:Timeout"),
            ):
                out = maybe_ai_fallback(rules, LOW_TEXT, conn=self.store.conn)
        self.assertEqual(out["parse_meta"]["method"], "rules")
        self.assertEqual(out["parse_meta"]["ai_fallback"], "failed")
        self.assertEqual(out["contact"]["email"], rules["contact"]["email"])

    def test_db_flag_off_skips_llm(self):
        from worker.ai_flags import set_flags

        rules = parse_text(LOW_TEXT)
        set_flags(self.store.conn, {"cv_fallback": False}, updated_by="test")
        env = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with patch("worker.cv_parse.ai_fallback.complete_json") as api:
                out = maybe_ai_fallback(rules, LOW_TEXT, conn=self.store.conn)
        api.assert_not_called()
        self.assertEqual(out["parse_meta"]["ai_fallback"], "skipped")


if __name__ == "__main__":
    unittest.main()
