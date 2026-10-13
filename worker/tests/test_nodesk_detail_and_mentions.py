"""NoDesk reads the full listing page; customer/partner brand mentions are not skills."""
import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("AI_GATEWAY_ENABLED", "0")
os.environ.setdefault("AI_MARKET_FIT_ENABLED", "0")

from worker.connectors.rssboards import NoDeskConnector
from worker.techstack import extract_stack

PAGE = (Path(__file__).parent / "fixtures" / "nodesk_ably.html").read_text()
URL = "https://nodesk.co/remote-jobs/ably-technical-lead-developer-experience/"
FEED = f"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Technical Lead, Developer Experience at Ably</title><description>Our everyday digital experiences
are in the midst of a realtime revolution. At Ably we provide a suite of products, supporting organizations
like Harness, EA, Panasonic and HubSpot.</description><guid>{URL}</guid></item></channel></rss>"""


class Client:
    def __init__(self):
        self.got = []

    def allowed(self, url):
        return True

    def get_text(self, url, accept=None):
        self.got.append(url)
        return FEED if url == NoDeskConnector.entry_url else PAGE


class Store:
    conn = None

    def has_source_url(self, url):
        return False


class NoDeskDetailTests(unittest.TestCase):
    def test_full_text_from_page_and_stack(self):
        client = Client()
        c = NoDeskConnector(client, Store())
        self.assertEqual(c.discover(), [URL])
        item = c.normalize(c.fetch(URL), URL)
        self.assertIn(URL, client.got)
        self.assertTrue(item["text"].startswith("Technical Lead, Developer Experience at Ably"))
        self.assertIn("London hub", item["text"])
        self.assertNotIn("_head", item)
        stack = extract_stack(item["text"], title=item["title"])
        for s in ("React", "TypeScript", "JavaScript", "Ruby on Rails", "Node.js"):
            self.assertIn(s, stack)
        self.assertNotIn("HubSpot", stack)


class MentionTests(unittest.TestCase):
    def test_customer_lists_are_not_skills(self):
        for text in (
            "Ably supports organizations like Harness, EA, Panasonic and HubSpot.",
            "Our customers include Salesforce, Slack and Shopify.",
            "Trusted by HubSpot and Salesforce teams worldwide.",
        ):
            got = extract_stack(text + "\nYou will write Python.")
            self.assertEqual(got, ["Python"], text)

    def test_real_use_still_counts(self):
        self.assertIn("HubSpot", extract_stack("You will build HubSpot integrations in Python."))
        self.assertIn("Salesforce", extract_stack("Experience with Salesforce Apex development."))


if __name__ == "__main__":
    unittest.main()
