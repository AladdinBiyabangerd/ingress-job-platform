import unittest

from app.sqlite_jobs import public_text, strip_leaked_html

ARBEITNOW_MIXED = (
    "&lt;h2 class=&quot;s-pb-2 s-pt-4&quot;&gt;&lt;strong&gt;Your Impact&lt;/strong&gt;&lt;/h2&gt;\n"
    "&lt;div&gt;We are looking for a &lt;strong&gt;Senior SRE&lt;/strong&gt;.&lt;/div&gt;\n"
    "&lt;ul&gt;&lt;li&gt;Lead observability&lt;/li&gt;&lt;/ul&gt;"
    '<p>Find more <a href="https://www.arbeitnow.com/english-speaking-jobs">'
    "English Speaking Jobs</a> on Arbeitnow</a>"
)


class PublicTextHtmlTest(unittest.TestCase):
    def test_strip_leaked_arbeitnow_html(self):
        text = strip_leaked_html(ARBEITNOW_MIXED)
        self.assertIn("Your Impact", text)
        self.assertIn("Senior SRE", text)
        self.assertNotIn("s-pb-2", text)
        self.assertNotIn("&lt;", text)

    def test_public_text_strips_markup_and_source_urls(self):
        text = public_text(ARBEITNOW_MIXED)
        self.assertIn("Senior SRE", text)
        self.assertNotIn("s-pb-2", text)
        self.assertNotIn("arbeitnow.com", text.lower())

    def test_plain_text_unchanged(self):
        raw = "We need Python and Kubernetes experience.\n\n• On-call\n• Mentoring"
        self.assertEqual(strip_leaked_html(raw), raw)
        self.assertEqual(public_text(raw), raw)


if __name__ == "__main__":
    unittest.main()
