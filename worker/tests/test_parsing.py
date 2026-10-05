import unittest

from worker.parsing import html_to_text

DJINNI = (
    '<div class="job-post__description"><p>We are strengthening our team and looking for a '
    "<strong>Junior</strong> <strong>Product Manager</strong> who will drive valuable features."
    "<br/><br/><strong>About the product:</strong> We develop social apps."
    "<br/><br/><strong>In this role, you will</strong></p>"
    "<ul><li>Conduct market research</li><li>Define product requirements<br/> </li></ul>"
    "<p><strong>Care and support: </strong></p><ul><li>100% medical insurance</li></ul>"
    "<p>Read more at <a href=\"https://example.com\">our site</a>.</p></div>"
)


class HtmlToTextTest(unittest.TestCase):
    def test_inline_tags_stay_in_the_sentence(self):
        text = html_to_text(DJINNI)
        self.assertTrue(
            text.startswith(
                "We are strengthening our team and looking for a Junior Product Manager who will drive valuable features.\n\n"
            ),
            text,
        )
        self.assertIn("About the product: We develop social apps.", text)
        self.assertIn("Read more at our site.", text)

    def test_lists_and_bold_headings(self):
        text = html_to_text(DJINNI)
        self.assertIn("In this role, you will:\n\n• Conduct market research\n• Define product requirements", text)
        self.assertIn("Care and support:\n\n• 100% medical insurance", text)

    def test_ordered_lists_and_html_headings(self):
        text = html_to_text("<h3>Hiring process</h3><ol><li>Intro call</li><li><p>Offer</p></li></ol>")
        self.assertEqual(text, "Hiring process:\n\n1. Intro call\n2. Offer")

    def test_plain_text_keeps_its_line_breaks(self):
        self.assertEqual(html_to_text("Line one\nline two\n\nSecond paragraph"), "Line one\nline two\n\nSecond paragraph")

    def test_br_runs_and_rules(self):
        self.assertEqual(html_to_text("a<br>b<br><br><br>c<hr>d<p>-----</p><p>.</p><p>e</p>"), "a\nb\n\nc\n\nd\n\ne")

    def test_scripts_dropped_and_limit(self):
        self.assertEqual(html_to_text("<p>Hi<script>x()</script></p><style>p{}</style>"), "Hi")
        self.assertEqual(len(html_to_text("<p>" + "x" * 50 + "</p>", limit=10)), 10)


if __name__ == "__main__":
    unittest.main()
