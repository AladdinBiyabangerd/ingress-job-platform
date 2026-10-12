import unittest

from worker.techstack import is_tech_job

BLOCKED = [
    "Client Strategist", "Legal Ops", "Senior Risk Associate",
    "Director, Global GTM Strategy & Operations",
    "Bilingual Channel Account Manager, Arabic (MEA) - UK",
    "CPS Account Program Manager", "Principal Solutions Consultant",
    "Senior Director, Field Enablement", "VP of Trust & Safety",
    "Mobile Growth & Operations Manager", "Head of Sales", "Marketing Manager",
    "Customer Success Manager", "Senior Recruiter", "Financial Analyst",
    "Head of Crypto",
]
KEPT = [
    "Senior Backend Engineer", "Security Risk Analyst",
    "Senior GTM AI Engineer", "GRC Analyst",
    "Salesforce Developer", "Project Manager", "Game Designer", "Product Manager",
    "Crypto Engineer", "IT Specialist",
]
# Broad source categories that used to let business titles through.
CATS = ["", "Engineering", "Software Development", "Tech"]


class BizTitleTests(unittest.TestCase):
    def test_blocked_under_any_category(self):
        for t in BLOCKED:
            for c in CATS:
                self.assertFalse(is_tech_job(t, c, ["python", "aws"]), (t, c))

    def test_kept(self):
        for t in KEPT:
            self.assertTrue(is_tech_job(t, "Engineering"), t)


if __name__ == "__main__":
    unittest.main()
