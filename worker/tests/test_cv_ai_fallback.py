"""AI #1 CV parse fallback (plan §5.1 / cv-parse-ai1-v2)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import GatewayResult, ensure_ai_tables
from worker.cv_parse import maybe_ai_fallback, parse_text
from worker.cv_parse.ai_fallback import (
    PROMPT_VERSION,
    dictionary_skill_count,
    filter_skills,
)
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
                {"name": "Java", "years": 3, "level": "advanced", "evidence": "Java", "confidence": 0.9},
                {"name": "Haskell", "years": 1, "level": "", "evidence": "Haskell", "confidence": 0.9},
                {
                    "name": "Teleportation",
                    "years": 9,
                    "level": "expert",
                    "evidence": "Teleportation",
                    "confidence": 0.9,
                },
                {"name": "k8s", "years": 2, "level": "", "evidence": "k8s", "confidence": 0.9},
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
        skills = filter_skills(
            [{"name": "k8s", "years": 2, "level": "", "evidence": "k8s", "confidence": 0.9}],
            text,
        )
        self.assertEqual([s["name"] for s in skills], ["Kubernetes"])

    def test_drops_low_confidence_skills(self):
        text = "Built APIs with Java and Python."
        skills = filter_skills(
            [
                {
                    "name": "Java",
                    "years": 3,
                    "level": "advanced",
                    "evidence": "Built APIs with Java",
                    "confidence": 0.9,
                },
                {
                    "name": "Python",
                    "years": 2,
                    "level": "",
                    "evidence": "Familiar with Python",
                    "confidence": 0.3,
                },
            ],
            text,
        )
        names = {s["name"] for s in skills}
        self.assertIn("Java", names)
        self.assertNotIn("Python", names)

    def test_weak_confidence_dampens_years(self):
        text = "Exposed to Spring Boot at Acme."
        skills = filter_skills(
            [
                {
                    "name": "Spring",
                    "years": 4,
                    "level": "",
                    "evidence": "Exposed to Spring Boot",
                    "confidence": 0.4,
                },
            ],
            text,
        )
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["name"], "Spring")
        self.assertEqual(skills[0]["years"], 2.0)  # 4 * 0.5
        self.assertEqual(skills[0]["confidence"], 0.4)
        self.assertIn("Spring", skills[0]["evidence"])

    def test_keeps_evidence_and_confidence_on_output(self):
        text = "Five years of Java."
        skills = filter_skills(
            [
                {
                    "name": "Java",
                    "years": 5,
                    "level": "advanced",
                    "evidence": "Five years of Java",
                    "confidence": 0.95,
                },
            ],
            text,
        )
        self.assertEqual(skills[0]["evidence"], "Five years of Java")
        self.assertEqual(skills[0]["confidence"], 0.95)
        self.assertEqual(skills[0]["years"], 5.0)


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
        self.assertGreaterEqual(dictionary_skill_count(profile), 3)
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
                {
                    "name": "Java",
                    "years": 4,
                    "level": "advanced",
                    "evidence": "Used java",
                    "confidence": 0.9,
                },
                {
                    "name": "Spring",
                    "years": 3,
                    "level": "advanced",
                    "evidence": "spring sometimes",
                    "confidence": 0.85,
                },
                {
                    "name": "InventedSkill",
                    "years": 1,
                    "level": "",
                    "evidence": "nowhere",
                    "confidence": 0.9,
                },
            ],
            "soft_skills": ["communication"],
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
        self.assertEqual(out["parse_meta"]["prompt_version"], PROMPT_VERSION)
        self.assertEqual(out["contact"]["email"], "email@example.com")
        self.assertEqual(out["headline"], "Java Developer")
        names = {s["name"] for s in out["skills"]}
        self.assertIn("Java", names)
        self.assertIn("Spring", names)
        self.assertNotIn("InventedSkill", names)
        self.assertEqual(out.get("soft_skills"), ["communication"])
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

    def test_thin_skills_forces_fallback_despite_high_confidence(self):
        """<3 dictionary skills → AI even when rules confidence is high."""
        profile = {
            "contact": {"email": "a@b.com"},
            "headline": "Manager",
            "summary": "Led teams.",
            "seniority": "senior",
            "total_years": 8,
            "work_history": [],
            "skills": [{"name": "Java", "years": 2, "level": "", "source": "cv"}],
            "languages": [],
            "education": [],
            "parse_meta": {"method": "rules", "confidence": 0.9},
        }
        self.assertEqual(dictionary_skill_count(profile), 1)
        llm = {
            "headline": "Java Manager",
            "summary": "Managed Java delivery.",
            "seniority": "senior",
            "total_years": 8,
            "work_history": [],
            "skills": [
                {
                    "name": "Java",
                    "years": 5,
                    "level": "advanced",
                    "evidence": "Java delivery",
                    "confidence": 0.9,
                },
                {
                    "name": "Spring",
                    "years": 3,
                    "level": "",
                    "evidence": "Spring services",
                    "confidence": 0.85,
                },
                {
                    "name": "Kafka",
                    "years": 2,
                    "level": "",
                    "evidence": "Kafka events",
                    "confidence": 0.8,
                },
            ],
            "soft_skills": ["leadership"],
            "languages": [],
            "education": [],
        }
        text = "Managed Java delivery with Spring services and Kafka events."
        env = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with patch(
                "worker.cv_parse.ai_fallback.complete_json",
                return_value=GatewayResult(ok=True, data=llm, cached=False),
            ) as api:
                out = maybe_ai_fallback(profile, text, conn=self.store.conn)
        api.assert_called_once()
        self.assertEqual(api.call_args.kwargs["prompt_version"], PROMPT_VERSION)
        self.assertEqual(out["parse_meta"]["ai_fallback"], "applied")
        self.assertEqual(out["parse_meta"]["ai_force_reason"], "thin_skills")
        names = {s["name"] for s in out["skills"]}
        self.assertIn("Java", names)
        self.assertIn("Spring", names)
        self.assertIn("Kafka", names)
        self.assertEqual(out.get("soft_skills"), ["leadership"])


if __name__ == "__main__":
    unittest.main()
