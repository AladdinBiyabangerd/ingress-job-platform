"""Template layer (optional) + generic parser on 15 public CV templates.

Fixtures in tests/fixtures/cv_templates/*.txt are text extracts (see its README for
sources / licences). Detection is optional: every fixture must also parse acceptably
with templates switched off.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from worker.cv_parse import assess_quality, parse_text
from worker.cv_parse.templates import TEMPLATES, detect_template
from worker.cv_parse.text import _repair_glyphs, looks_garbled

FIX = Path(__file__).parent / "fixtures" / "cv_templates"

# id -> (min quality score, min jobs, expected first job title or None for "partial" templates)
EXPECT = {
    "vantage_typst": (0.94, 6, "Lead Software Developer"),
    "alta_typst": (0.41, 2, "Junior Software Engineer"),
    "arthur_latex": (0.94, 3, "Freelance Data Scientist"),
    "latexcv_classic": (0.82, 4, "Scientific Employee / PhD Student"),
    "personal_data_docx": (0.94, 2, "Web Developer"),
    "simple_resume_cv": (0.83, 2, "Undergraduate Research Student"),
    "rover_fancy": (0.41, 1, None),
    "academic_xovee": (0.58, 2, "Postdoctoral Researcher"),
    "resumekit_docx": (0.56, 1, "Software Engineer Intern"),
    # Partial: placeholder content or layouts the generic parser only half reads (AI fallback territory).
    "latexcv_modern": (0.90, 3, "IT Consultant for IBM XPages and Notes Domino"),
    "latexcv_infographics": (0.56, 1, None),
    "minimal_cv": (0.41, 1, None),
    "rover_base": (0.41, 1, None),
    "chicv": (0.41, 1, None),
    "resume_ng_cn": (0.27, 1, None),
}

# Extra real-CV fixtures from the earlier /tmp/cvs batch: parsed by the generic parser only
# (the worker has no detector for them). id -> (min score, min jobs, expected first title)
EXTRA = {
    "rendercv_classic": (0.95, 4, "Co-Founder & CTO"),
    "rendercv_ember": (0.95, 4, "Co-Founder & CTO"),
    "rendercv_engres": (0.95, 4, "Co-Founder & CTO"),
    "rendercv_moderncv": (0.95, 4, "Co-Founder & CTO"),
    "deedy_twocol": (0.95, 3, "SOFTWARE ENGINEER"),
    "awesome_cv": (0.85, 3, None),
    "sb2nov_ats": (0.80, 3, "Software Engineer"),
    "jobhire_chronological": (0.80, 2, "Senior Accountant"),
    "jobhire_modern": (0.90, 2, "UI/UX Designer"),
    "jobhire_twocolumn": (0.78, 2, "Senior Project Manager"),
}


def _text(tid: str) -> str:
    return (FIX / f"{tid}.txt").read_text(encoding="utf-8")


class TemplateFixturesTest(unittest.TestCase):
    def test_every_template_has_a_fixture_and_an_expectation(self):
        ids = {t.id for t in TEMPLATES}
        self.assertEqual(ids, set(EXPECT))
        self.assertEqual({p.stem for p in FIX.glob("*.txt")}, ids | set(EXTRA))

    def test_detection_and_parse_per_template(self):
        for tid, (min_score, min_jobs, title) in EXPECT.items():
            with self.subTest(template=tid):
                text = _text(tid)
                found = detect_template(text)
                self.assertIsNotNone(found)
                self.assertEqual(found["id"], tid)
                prof = parse_text(text)
                self.assertEqual(prof["parse_meta"]["template"]["id"], tid)
                self.assertGreaterEqual(assess_quality(prof, text)["score"], min_score)
                self.assertGreaterEqual(len(prof["work_history"]), min_jobs)
                if title:
                    self.assertEqual(prof["work_history"][0]["title"], title)

    def test_extra_real_cv_fixtures_parse_generically(self):
        for tid, (min_score, min_jobs, title) in EXTRA.items():
            with self.subTest(template=tid):
                text = _text(tid)
                prof = parse_text(text)
                self.assertGreaterEqual(assess_quality(prof, text)["score"], min_score)
                self.assertGreaterEqual(len(prof["work_history"]), min_jobs)
                if title:
                    self.assertEqual(prof["work_history"][0]["title"], title)
                self.assertNotIn("@gmail", text)  # fixtures are anonymised

    def test_extra_fixtures_do_not_trigger_template_detection(self):
        for tid in EXTRA:
            with self.subTest(template=tid):
                self.assertIsNone(detect_template(_text(tid)))

    def test_generic_parser_alone_is_enough(self):
        """Templates off: the generic parser must reach the same floor (never template-dependent)."""
        for tid, (min_score, min_jobs, title) in EXPECT.items():
            with self.subTest(template=tid):
                text = _text(tid)
                prof = parse_text(text, use_templates=False)
                self.assertEqual(prof["parse_meta"]["template"], {"id": None})
                self.assertGreaterEqual(assess_quality(prof, text)["score"], min_score)
                self.assertGreaterEqual(len(prof["work_history"]), min_jobs)
                if title:
                    self.assertEqual(prof["work_history"][0]["title"], title)

    def test_unknown_layout_records_no_template(self):
        text = (
            "Jane Doe\nBackend Engineer\njane@example.com\n\nExperience\nBackend Engineer\n"
            "Acme GmbH | Jan 2020 - Present\n- Built Python services on AWS with Docker\n\n"
            "Education\nBSc Computer Science, TU Berlin 2015\n\nSkills\nPython, Docker, AWS, Kafka\n"
        )
        prof = parse_text(text)
        self.assertEqual(prof["parse_meta"]["template"], {"id": None})
        self.assertEqual(prof["work_history"][0]["company"], "Acme GmbH")

    def test_no_false_positive_on_existing_layout_fixtures(self):
        from tests import test_cv_layouts as layouts  # noqa: PLC0415

        for name in ("RENDERCV_CLASSIC", "RENDERCV_EMBER", "RENDERCV_ENGRES"):
            with self.subTest(name=name):
                self.assertIsNone(detect_template(getattr(layouts, name)))


class TemplateSafetyTest(unittest.TestCase):
    def test_detector_crash_never_breaks_generic_parse(self):
        text = _text("vantage_typst")
        with patch("worker.cv_parse.pipeline.detect_template", side_effect=RuntimeError("boom")):
            prof = parse_text(text)
        self.assertEqual(prof["parse_meta"]["template"], {"id": None})
        self.assertEqual(len(prof["work_history"]), 6)

    def test_hinted_parse_used_only_when_better(self):
        text = "Jane Doe\njane@example.com\n\nMY STUFF\nPython, Docker, Kafka, AWS, PostgreSQL, Redis, Java\n"
        fake = {"id": "fake", "name": "Fake", "confidence": 1.0, "hints": {"headings": {"my stuff": "skills"}}}
        with patch("worker.cv_parse.pipeline.detect_template", return_value=fake):
            prof = parse_text(text)
        meta = prof["parse_meta"]["template"]
        self.assertEqual(meta["id"], "fake")
        self.assertTrue(meta["applied"])
        self.assertIn("skills", prof["parse_meta"]["sections_found"])

        worse = {**fake, "hints": {"strip": [r".*"]}}  # drops every line: strictly worse
        with patch("worker.cv_parse.pipeline.detect_template", return_value=worse):
            prof2 = parse_text(text)
        self.assertFalse(prof2["parse_meta"]["template"]["applied"])
        self.assertEqual(prof2["contact"]["email"], "jane@example.com")


class GenericFixesTest(unittest.TestCase):
    def test_glyph_name_repair(self):
        self.assertEqual(_repair_glyphs("/two.lnum/zero.lnum/one.lnum/six.lnum - present"), "2016 - present")
        self.assertEqual(_repair_glyphs("J/A.sc/N.sc"), "JAN")
        self.assertEqual(_repair_glyphs("Scienti/f_ic De/f_ine O/f_f_ice"), "Scientific Define Office")
        self.assertEqual(_repair_glyphs("T echs and T opics"), "Techs and Topics")

    def test_garbled_detection(self):
        self.assertTrue(looks_garbled("\u0f40\u10a0\u0d85" * 40))
        self.assertFalse(looks_garbled("Привет мир, это обычное резюме инженера " * 4))
        self.assertFalse(looks_garbled("这是一个正常的简历文本" * 10))
        self.assertTrue(looks_garbled(_text("resume_ng_cn")))

    def test_year_first_month_dates(self):
        prof = parse_text(
            "Jane Doe\njane@example.com\nExperience\nBackend Developer\nAcme - Product\n"
            " 2023 Mar. — 2024 Jul.\n Remote\n• Built APIs with Python and Docker for the platform team\n"
        )
        job = prof["work_history"][0]
        self.assertEqual((job["start"], job["end"]), ("2023-03", "2024-07"))
        self.assertEqual(job["title"], "Backend Developer")

    def test_date_column_above_title(self):
        prof = parse_text(
            "Jane Doe\njane@example.com\nExperiences\nDec. 2022 –\nPresent\nFreelance Data Scientist at LLM Solutions\n"
            "Built things with Python.\nMar. 2020 –\nSep. 2021\nData Scientist at Coperneec, Paris\nMore work.\n"
        )
        titles = [j["title"] for j in prof["work_history"]]
        self.assertEqual(titles, ["Freelance Data Scientist", "Data Scientist"])
        self.assertEqual(prof["work_history"][0]["company"], "LLM Solutions")

    def test_section_heading_variants(self):
        from worker.cv_parse.sections import split_sections

        parts = split_sections(
            "x\nWORK EXPERICENCE\nfoo\nRESEARCH\nEXPERIENCE\nbar\nEDUCATION First American University, MA\nSKILLS Python, Java, Docker"
        )
        self.assertIn("foo", parts["experience"])
        self.assertIn("bar", parts["experience"])
        self.assertIn("First American University", parts["education"])
        self.assertIn("Python", parts["skills"])

    def test_heading_is_never_the_name(self):
        prof = parse_text("SUMMARY\nSenior engineer with ten years of Python experience.\nExperience\nEngineer\nAcme | 2019 - 2022\n")
        self.assertNotEqual(prof["contact"]["full_name"].lower(), "summary")


if __name__ == "__main__":
    unittest.main()
