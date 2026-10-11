"""Remote locked to any single country/region (Greece, Cyprus, ...) is not worldwide remote."""

from __future__ import annotations

import unittest

from worker.techstack import az_market_relevant, foreign_locked_remote


class CountryRemoteLockTest(unittest.TestCase):
    def test_remote_country_pins_are_locked(self):
        for place in ("Remote, Greece", "Remote - Greece", "Greece (Remote)",
                      "Remote (Bulgaria only)", "Remote - Romania", "Remote, Ukraine",
                      "Remote - Turkey", "Athens"):
            self.assertTrue(foreign_locked_remote("Backend Engineer", place, "Build APIs."), place)

    def test_body_pins(self):
        self.assertTrue(foreign_locked_remote(
            "Backend Engineer", "", "Remote role. Candidates must be based in Greece."))
        self.assertTrue(foreign_locked_remote(
            "Go Engineer", "",
            "LOCATIONS Here are the locations we engage contractors from. Please note, we are "
            "not looking to engage with contractors outside of these locations. Austria "
            "Bulgaria Cyprus Greece Hungary Malta"))

    def test_worldwide_remote_stays_open(self):
        for place in ("Remote", "Worldwide", "Remote - Worldwide", "Anywhere", "Remote EMEA"):
            self.assertFalse(foreign_locked_remote("Backend Engineer", place, "Join us."), place)
        self.assertFalse(foreign_locked_remote(
            "Backend Engineer", "Remote",
            "We hire globally. Our customers include companies in Greece and Spain."))

    def test_market_gate_drops_greece_remote(self):
        self.assertFalse(az_market_relevant(
            "Backend Engineer", "Remote, Greece", "Build APIs.", remote=True, relocation=False))
        self.assertTrue(az_market_relevant(
            "Backend Engineer", "Remote", "Build APIs. Work from anywhere.",
            remote=True, relocation=False))


if __name__ == "__main__":
    unittest.main()
