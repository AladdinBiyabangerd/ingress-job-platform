"""Job tidy heuristics and structured → plain-text formatting."""

from __future__ import annotations

import unittest

from worker.tidy import format_structured, messy


class MessyTest(unittest.TestCase):
    def test_wall_of_text_is_messy(self):
        body = (
            "We are looking for a senior engineer to join our team. "
            "You will build APIs, work with SQL, and own delivery end to end. "
            "Experience with Python and Docker is required. "
            "We offer flexible work and growth opportunities for the right person. "
        ) * 3
        self.assertTrue(messy(body))

    def test_structured_bullets_skip(self):
        body = (
            "What you'll do:\n"
            "• Build APIs\n"
            "• Own delivery\n"
            "• Review code\n"
            "• Ship weekly\n"
            "\n"
            "Requirements:\n"
            "• Python\n"
            "• SQL\n"
        )
        self.assertFalse(messy(body))

    def test_short_ad_skip(self):
        self.assertFalse(messy("Short role note."))


class FormatStructuredTest(unittest.TestCase):
    def test_en_sections(self):
        text = format_structured(
            {
                "why_interesting": ["Shape a global product."],
                "about": "Backend role on travel tech.",
                "what_youll_do": ["Deliver Python services.", "Optimise performance."],
                "requirements": ["Python backend ownership", "SQL knowledge"],
                "nice_to_have": ["Docker"],
                "benefits": ["Flexible work", "Growth"],
                "extra_sections": [],
            },
            lang="en",
        )
        self.assertIn("Why this role is interesting:", text)
        self.assertIn("What you'll do:", text)
        self.assertIn("• Deliver Python services.", text)
        self.assertIn("Requirements:", text)
        self.assertIn("Benefits:", text)

    def test_omits_empty_sections(self):
        text = format_structured(
            {
                "why_interesting": [],
                "about": "",
                "what_youll_do": ["Ship features"],
                "requirements": [],
                "nice_to_have": [],
                "benefits": [],
                "extra_sections": [],
            },
            lang="en",
        )
        self.assertEqual(text.count(":"), 1)
        self.assertIn("What you'll do:", text)


if __name__ == "__main__":
    unittest.main()
