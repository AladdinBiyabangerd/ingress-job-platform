import unittest

from worker.parsing import (
    html_to_text,
    is_aggregator_snippet,
    needs_html_unescape,
    text_from_html,
)

DJINNI = (
    '<div class="job-post__description"><p>We are strengthening our team and looking for a '
    "<strong>Junior</strong> <strong>Product Manager</strong> who will drive valuable features."
    "<br/><br/><strong>About the product:</strong> We develop social apps."
    "<br/><br/><strong>In this role, you will</strong></p>"
    "<ul><li>Conduct market research</li><li>Define product requirements<br/> </li></ul>"
    "<p><strong>Care and support: </strong></p><ul><li>100% medical insurance</li></ul>"
    "<p>Read more at <a href=\"https://example.com\">our site</a>.</p></div>"
)

# Arbeitnow: body fully entity-escaped, credit footer is real HTML (has raw <).
ARBEITNOW_MIXED = (
    "&lt;h2 class=&quot;s-pb-2 s-pt-4&quot;&gt;&lt;strong&gt;Your Impact&lt;/strong&gt;&lt;/h2&gt;\n"
    "&lt;div class=&quot;s-whitespace-pre-wrap&quot;&gt;We are looking for a "
    "&lt;strong&gt;Senior Site Reliability Engineer&lt;/strong&gt; "
    "to join Platform Engineering.&lt;/div&gt;\n"
    "&lt;ul&gt;&lt;li&gt;Lead the observability strategy&lt;/li&gt;"
    "&lt;li&gt;Take part in on-call&lt;/li&gt;&lt;/ul&gt;"
    '<p>Find more <a href="https://www.arbeitnow.com/english-speaking-jobs">'
    "English Speaking Jobs in Germany</a> on Arbeitnow</a>"
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


class TextFromHtmlTest(unittest.TestCase):
    def test_fully_escaped_html(self):
        raw = "&lt;p&gt;Hello &lt;strong&gt;world&lt;/strong&gt;&lt;/p&gt;"
        self.assertTrue(needs_html_unescape(raw))
        self.assertEqual(text_from_html(raw), "Hello world")

    def test_arbeitnow_escaped_body_with_real_html_footer(self):
        self.assertTrue(needs_html_unescape(ARBEITNOW_MIXED))
        text = text_from_html(ARBEITNOW_MIXED)
        self.assertIn("Your Impact:", text)
        self.assertIn("Senior Site Reliability Engineer", text)
        self.assertIn("• Lead the observability strategy", text)
        self.assertNotIn("s-pb-2", text)
        self.assertNotIn("&lt;", text)
        self.assertNotIn("<h2", text)

    def test_real_html_with_code_entities_not_force_unescaped(self):
        # Normal HTML that mentions &lt; briefly should still strip as HTML.
        raw = "<p>Use thresholds when value &lt; 10.</p><ul><li>One</li><li>Two</li></ul>"
        self.assertFalse(needs_html_unescape(raw))
        text = text_from_html(raw)
        self.assertIn("Use thresholds when value < 10.", text)
        self.assertIn("• One", text)


class AggregatorSnippetTest(unittest.TestCase):
    def test_jooble_twilio_stub(self):
        text = (
            "...craft personalized customer experiences.\n"
            "Our dedication to remote-first work , and strong culture of connection "
            "and global... ...See yourself at Twilio\n"
            "Join the team as our next Software Engineer on Twilio’s platform "
            "engineering observability team.\nAbout...\n\nFull-time"
        )
        self.assertTrue(is_aggregator_snippet(text))

    def test_full_jd_not_snippet(self):
        text = (
            "Who we are:\n\nAt Twilio, we’re shaping the future of communications.\n\n"
            "Responsibilities:\n\n• Lead observability platform components\n"
            "• Drive OpenTelemetry adoption\n\n"
            "Qualifications:\n\n• Experience with Prometheus and Kubernetes\n"
        )
        self.assertFalse(is_aggregator_snippet(text))


if __name__ == "__main__":
    unittest.main()
