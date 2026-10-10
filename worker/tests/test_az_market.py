import unittest

from worker.techstack import az_market_relevant, foreign_locked_remote


class AzMarketRemoteTest(unittest.TestCase):
    def test_canada_remote_place_is_locked(self):
        self.assertTrue(foreign_locked_remote("Backend Engineer", "Remote, Canada", ""))
        self.assertFalse(
            az_market_relevant(
                "Backend Engineer",
                "Remote, Canada",
                "Fully remote role.",
                remote=True,
                relocation=False,
            )
        )

    def test_us_only_and_residency_lock(self):
        self.assertTrue(
            foreign_locked_remote(
                "Staff Engineer",
                "Remote",
                "Candidates must be located in the United States.",
            )
        )
        self.assertTrue(foreign_locked_remote("Designer", "US Remote", ""))
        self.assertTrue(foreign_locked_remote("SRE", "Remote (UK)", "UK-only remote."))

    def test_toronto_office_as_remote_place_is_locked(self):
        self.assertTrue(foreign_locked_remote("Python Developer", "Toronto, Canada", ""))

    def test_worldwide_and_emea_stay(self):
        self.assertFalse(
            foreign_locked_remote("Backend", "Remote, Worldwide", "Work from anywhere.")
        )
        self.assertFalse(foreign_locked_remote("Backend", "Remote EMEA", ""))
        self.assertTrue(
            az_market_relevant(
                "Backend",
                "Remote",
                "This is a fully remote role. Work from anywhere.",
                remote=True,
                relocation=False,
            )
        )

    def test_plain_remote_without_geo_stays(self):
        self.assertFalse(foreign_locked_remote("Go Engineer", "Remote", "Fully remote role."))
        self.assertTrue(
            az_market_relevant(
                "Go Engineer",
                "Remote",
                "Fully remote role.",
                remote=True,
                relocation=False,
            )
        )

    def test_azerbaijan_signal_keeps_ad(self):
        self.assertTrue(
            az_market_relevant(
                "Frontend",
                "Remote, Baku",
                "Remote across Azerbaijan.",
                remote=True,
                relocation=False,
            )
        )

    def test_relocation_to_canada_stays(self):
        self.assertTrue(
            az_market_relevant(
                "Backend Engineer",
                "Toronto, Canada",
                "Visa sponsorship and relocation package.",
                remote=False,
                relocation=True,
            )
        )
        self.assertTrue(
            az_market_relevant(
                "Backend Engineer",
                "Remote, Canada",
                "Relocation support available.",
                remote=True,
                relocation=True,
            )
        )

    def test_california_remote_not_opened_by_company_worldwide(self):
        text = (
            "Candidates in other locations (US based) will be considered. "
            "More than 20,000 organizations worldwide rely on Databricks. "
            "Must have an active or current US GOV Secret clearance eligibility."
        )
        self.assertTrue(
            foreign_locked_remote(
                "Staff Security Engineer, Incident Response",
                "Remote - California",
                text,
            )
        )
        self.assertFalse(
            az_market_relevant(
                "Staff Security Engineer, Incident Response",
                "Remote - California",
                text,
                remote=True,
                relocation=False,
            )
        )

    def test_us_based_locks_plain_remote_place(self):
        self.assertTrue(
            foreign_locked_remote(
                "Security Engineer",
                "Remote",
                "Candidates in other locations (US based) will be considered.",
            )
        )

    def test_tel_aviv_hybrid_is_not_kept(self):
        from worker.techstack import foreign_office_without_offer

        text = "Software Engineer in our product team.\n#LI-Hybrid\n"
        self.assertTrue(foreign_office_without_offer("Software Engineer", "Tel Aviv", text))
        self.assertFalse(
            az_market_relevant(
                "Software Engineer",
                "Tel Aviv",
                text,
                remote=False,
                relocation=False,
            )
        )

    def test_germany_wide_remote_is_locked(self):
        text = (
            "You work remotely (Germany-wide), with offices in Hamburg, Berlin or Munich. "
            "German is a big plus."
        )
        self.assertTrue(
            foreign_locked_remote(
                "Senior Product Designer",
                "Remote",
                text,
            )
        )
        self.assertFalse(
            az_market_relevant(
                "Senior Product Designer",
                "Remote; Hamburg; Berlin; München",
                text,
                remote=True,
                relocation=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
