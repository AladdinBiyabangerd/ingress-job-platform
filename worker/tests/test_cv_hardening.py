"""Glued title+company, absurd years, placeholder text and optional OCR bookkeeping."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway import GatewayResult, ensure_ai_tables
from worker.cv_parse import assess_quality, maybe_ai_fallback, parse_bytes, parse_text
from worker.cv_parse.jobs import split_glued
from worker.cv_parse.quality import is_placeholder_text
from worker.cv_parse.text import extract
from worker.db import Store

FIX = Path(__file__).parent / "fixtures" / "cv_templates"
ENV = {"CV_AI_FALLBACK_ENABLED": "1", "OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
GARBLED = "\u0b85\u0b86\u0b87\u0b88 " * 40 + "mail@example.com"


class GluedTitleCompanyTest(unittest.TestCase):
    def test_split_glued_variants(self):
        self.assertEqual(
            split_glued("IT Consultant for IBM XPages and Notes Domino We4IT GmbH Bremen"),
            ("IT Consultant for IBM XPages and Notes Domino", "We4IT GmbH"),
        )
        self.assertEqual(
            split_glued("Scientific Employee / Software Development University of Bremen"),
            ("Scientific Employee / Software Development", "University of Bremen"),
        )
        self.assertEqual(
            split_glued("Student Assistant / Programmer otulea.uni-bremen.de"),
            ("Student Assistant / Programmer", "otulea.uni-bremen.de"),
        )

    def test_plain_titles_are_not_cut(self):
        for title in ("Senior Software Engineer", "Head of Data Platform Engineering", "Lead Backend Developer Python"):
            self.assertIsNone(split_glued(title))

    def test_latexcv_modern_fixture_splits_company(self):
        prof = parse_text((FIX / "latexcv_modern.txt").read_text(encoding="utf-8"))
        first = prof["work_history"][0]
        self.assertEqual(first["company"], "We4IT GmbH")
        self.assertEqual(first["title"], "IT Consultant for IBM XPages and Notes Domino")
        self.assertTrue(all(j["company"] for j in prof["work_history"]))


class AbsurdYearTest(unittest.TestCase):
    def test_absurd_years_flagged_and_force_ai(self):
        text = (FIX / "minimal_cv.txt").read_text(encoding="utf-8")
        q = assess_quality(parse_text(text), text)
        self.assertIn("work_absurd_date", q["issues"])
        self.assertTrue(q["needs_ai"])

    def test_absurd_start_year_in_profile(self):
        prof = parse_text("Jane Doe\njane@example.com\n")
        prof["work_history"] = [{"title": "Engineer", "company": "Acme", "start": "1818-04", "end": "1826-08"}]
        self.assertIn("work_absurd_date", assess_quality(prof, "x" * 300)["issues"])
        prof["work_history"] = [{"title": "Engineer", "company": "Acme", "start": "2019-04", "end": "2022-08"}]
        self.assertNotIn("work_absurd_date", assess_quality(prof, "x" * 300)["issues"])


class PlaceholderTest(unittest.TestCase):
    def test_detection(self):
        self.assertTrue(is_placeholder_text((FIX / "chicv.txt").read_text(encoding="utf-8")))
        self.assertTrue(is_placeholder_text((FIX / "rover_base.txt").read_text(encoding="utf-8")))
        self.assertTrue(
            is_placeholder_text("Job Title Month Year\nCompany Name City, State\nMonth Year - Month Year\nJob Title\n")
        )
        for real in ("rendercv_classic", "vantage_typst", "arthur_latex", "jobhire_modern"):
            self.assertFalse(is_placeholder_text((FIX / f"{real}.txt").read_text(encoding="utf-8")), real)

    def test_one_lorem_bullet_in_a_real_cv_is_fine(self):
        text = (FIX / "simple_resume_cv.txt").read_text(encoding="utf-8")
        self.assertFalse(is_placeholder_text(text))

    def test_placeholder_is_low_quality_and_needs_ai(self):
        text = (FIX / "chicv.txt").read_text(encoding="utf-8")
        q = assess_quality(parse_text(text), text)
        self.assertIn("placeholder_text", q["issues"])
        self.assertLessEqual(q["score"], 0.45)
        self.assertTrue(q["needs_ai"])
        self.assertEqual(set(q["weak"]), {"contact", "headline", "work_history", "education", "skills"})


class PlaceholderAiFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")
        ensure_ai_tables(self.store.conn)

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def test_placeholder_cv_goes_to_ai(self):
        text = (FIX / "rover_base.txt").read_text(encoding="utf-8")
        with patch.dict(os.environ, ENV, clear=False), patch(
            "worker.cv_parse.ai_fallback.complete_json", return_value=GatewayResult(ok=False, error="down")
        ) as api:
            out = maybe_ai_fallback(parse_text(text), text, conn=self.store.conn)
        api.assert_called_once()
        self.assertEqual(out["parse_meta"]["ai_fallback"], "failed")  # rules result kept
        self.assertIn("placeholder_text", out["parse_meta"]["quality"]["issues"])

    def test_empty_or_short_text_never_calls_ai(self):
        for text in ("", "Job Title Month Year\nCompany Name"):
            with patch.dict(os.environ, ENV, clear=False), patch("worker.cv_parse.ai_fallback.complete_json") as api:
                maybe_ai_fallback(parse_text(text), text, conn=self.store.conn)
            api.assert_not_called()


class OcrMetaTest(unittest.TestCase):
    def _pdf(self, digital: str, **patches):
        with patch("worker.cv_parse.text._from_pdf", return_value=digital):
            return extract(b"%PDF-1.4 fake", filename="cv.pdf")

    def test_garbled_without_ocr_is_kept_and_marked_unavailable(self):
        with patch("worker.cv_parse.text.ocr_env_enabled", return_value=True), patch(
            "worker.cv_parse.text.ocr_enabled", return_value=False
        ):
            res = self._pdf(GARBLED)
        self.assertEqual((res.error, res.ocr), ("text_garbled", "unavailable"))
        self.assertTrue(res.text)

    def test_ocr_disabled_by_env(self):
        with patch("worker.cv_parse.text.ocr_env_enabled", return_value=False):
            res = self._pdf("")
        self.assertEqual((res.ocr, res.error), ("disabled", "ocr_disabled"))

    def test_ocr_used_replaces_garbled_layer(self):
        good = "Jane Doe\njane@example.com\nExperience\nEngineer at Acme 2020 - 2022\n" * 3
        with patch("worker.cv_parse.text.ocr_env_enabled", return_value=True), patch(
            "worker.cv_parse.text.ocr_enabled", return_value=True
        ), patch("worker.cv_parse.text.ocr_pdf_bytes", return_value=good):
            res = self._pdf(GARBLED)
        self.assertEqual((res.ocr, res.source, res.error), ("used", "ocr", None))
        self.assertIn("Jane Doe", res.text)

    def test_ocr_crash_or_empty_never_breaks_parsing(self):
        for effect in ({"side_effect": RuntimeError("boom")}, {"return_value": ""}):
            with patch("worker.cv_parse.text.ocr_env_enabled", return_value=True), patch(
                "worker.cv_parse.text.ocr_enabled", return_value=True
            ), patch("worker.cv_parse.text.ocr_pdf_bytes", **effect):
                res = self._pdf(GARBLED)
            self.assertEqual((res.ocr, res.error), ("empty", "text_garbled"))

    def test_digital_pdf_does_not_touch_ocr(self):
        good = "Jane Doe\njane@example.com\nExperience\nEngineer at Acme 2020 - 2022\n"
        with patch("worker.cv_parse.text.ocr_pdf_bytes") as ocr:
            res = self._pdf(good)
        ocr.assert_not_called()
        self.assertIsNone(res.ocr)

    def test_parse_meta_records_ocr(self):
        with patch("worker.cv_parse.text._from_pdf", return_value=GARBLED), patch(
            "worker.cv_parse.text.ocr_env_enabled", return_value=True
        ), patch("worker.cv_parse.text.ocr_enabled", return_value=False):
            prof = parse_bytes(b"%PDF-1.4 fake", filename="cv.pdf", ai_fallback=False)
        self.assertEqual(prof["parse_meta"]["ocr"]["status"], "unavailable")
        self.assertEqual(prof["parse_meta"]["extract_warning"], "text_garbled")


if __name__ == "__main__":
    unittest.main()
