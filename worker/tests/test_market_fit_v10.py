"""market-fit-v10: explicit allowed-country / excluded-country lists.

The AI interprets list semantics (prompt section "Explicit country eligibility and exclusion
lists"); the code only verifies quotes, conflicts and caps. Answers are simulated so the
code's reading and the final % (AI % capped by the eligibility pre-check) are asserted.
Synthetic ads below are clearly marked; 514 is the real Ukrainian case.
"""

from __future__ import annotations

import unittest

from worker.eligibility import assess
from worker.fit_mapping import FLAGS
from worker.market_fit import PROMPT_VERSION, _SYSTEM, _FLAG_DEFINITIONS, verdict_from_ai

# (a) Azerbaijan allowed, other countries excluded
A_EN = ("Remote position.\nAllowed countries: Azerbaijan, Georgia, Armenia.\n"
        "Candidates from Russia and Belarus are not considered.")
A_UK = ("Віддалений формат роботи.\n🟢 Дозволені країни: Азербайджан, Грузія, Вірменія.\n"
        "🔴 Країни, з яких кандидати не розглядаються: Росія, Білорусь, США.")
A_RU = ("Удалённая работа.\nРазрешённые страны: Азербайджан, Грузия, Армения.\n"
        "Не рассматриваем кандидатов из России и Беларуси.")
# (b) Azerbaijan in both lists
B_EN = ("Remote position.\nAllowed countries: Azerbaijan, Georgia, Armenia.\n"
        "Candidates from Azerbaijan and Russia are not considered.")
B_UK = ("Віддалений формат роботи.\n🟢 Дозволені країни: Азербайджан, Грузія.\n"
        "🔴 Країни, з яких кандидати не розглядаються: Азербайджан, Росія.")
B_RU = ("Удалённая работа.\nРазрешённые страны: Азербайджан, Грузия.\n"
        "Не рассматриваем кандидатов из: Азербайджан, Россия.")
# (c) Azerbaijan in neither list
C_EN = ("Remote position.\nAllowed countries: Georgia, Armenia, Moldova.\n"
        "Candidates from Russia and Belarus are not considered.")
# (d) worldwide remote, Azerbaijan explicitly excluded
D_EN = "Work from anywhere in the world.\nCandidates from Azerbaijan are not considered."


def _line(text, start):
    return next(l for l in text.splitlines() if l.lstrip("🟢🔴 ").startswith(start)).lstrip("🟢🔴 ")


def _answer(**flags):
    data = {name: {"value": False, "quotes": []} for name in FLAGS}
    for name, quotes in flags.items():
        data[name] = {"value": True, "quotes": list(quotes)}
    data["reason"] = "test"
    return data


def _final(text, **flags):
    v = verdict_from_ai(_answer(**flags), ad_text=f"Engineer\n\n{text}", truncated=False)
    cap = assess("Engineer", "", text)["cap"]
    return v, min(v["ai_score"], cap), cap


class PromptTest(unittest.TestCase):
    def test_version_and_section(self):
        self.assertEqual(PROMPT_VERSION, "market-fit-v10")
        self.assertIn("Explicit country eligibility and exclusion lists\n1. Interpret allowed-country", _SYSTEM)
        self.assertIn("Do not infer that Azerbaijan is excluded merely because it is absent", _SYSTEM)
        self.assertIn("regardless of the language of the ad", _SYSTEM)
        self.assertIn("An exclusion list that names only other countries", _FLAG_DEFINITIONS["remote_country_restricted"])


class AllowedListTest(unittest.TestCase):
    """(a) AZ allowed, other countries excluded -> no restriction against AZ, 95."""

    def test_ai_follows_rule(self):
        for text, start in ((A_EN, "Allowed"), (A_UK, "Дозволені"), (A_RU, "Разрешённые")):
            with self.subTest(text=text[:30]):
                v, final, cap = _final(text, remote_az_explicit=[_line(text, start)])
                self.assertEqual(cap, 100)
                self.assertEqual((v["route"], final), ("remote_az_explicit", 95))
                self.assertEqual(v["conflicts"], [])

    def test_ai_still_flags_other_country_exclusion(self):
        # code does not drop the restriction itself: 84 + conflict + moderator note
        for text, start, excl in ((A_EN, "Allowed", "Candidates"), (A_UK, "Дозволені", "Країни"),
                                  (A_RU, "Разрешённые", "Не рассматриваем")):
            with self.subTest(text=text[:30]):
                v, final, _cap = _final(text, remote_az_explicit=[_line(text, start)],
                                        remote_country_restricted=[_line(text, excl)])
                self.assertEqual(final, 84)
                self.assertIn("remote_vs_restriction", v["conflicts"])
                self.assertTrue(any("Azərbaycan çəkilmir" in n for n in v["validation_notes"]))


class BothListsTest(unittest.TestCase):
    """(b) AZ allowed and excluded -> 84 + conflict for the moderator (AI and pre-check agree)."""

    def test_conflict_84(self):
        for text, start, excl in ((B_EN, "Allowed", "Candidates"), (B_UK, "Дозволені", "Країни"),
                                  (B_RU, "Разрешённые", "Не рассматриваем")):
            with self.subTest(text=text[:30]):
                v, final, cap = _final(text, remote_az_explicit=[_line(text, start)],
                                       remote_country_restricted=[_line(text, excl)])
                self.assertEqual(cap, 84)
                self.assertEqual(final, 84)
                self.assertIn("remote_vs_restriction", v["conflicts"])
                self.assertFalse(any("Azərbaycan çəkilmir" in n for n in v["validation_notes"]))

    def test_excluded_line_never_backs_az(self):
        for text, excl in ((B_EN, "Candidates"), (B_UK, "Країни"), (B_RU, "Не рассматриваем")):
            v, final, _ = _final(text, remote_az_explicit=[_line(text, excl)])
            self.assertFalse(v["flags"]["remote_az_explicit"])
            self.assertLess(final, 85)


class NeitherListTest(unittest.TestCase):
    """(c) AZ in neither list -> not eligible by itself."""

    def test_below_band(self):
        for flags in ({}, {"remote_country_restricted": [_line(C_EN, "Allowed")]}):
            v, final, cap = _final(C_EN, **flags)
            self.assertLess(final, 85)
            self.assertFalse(v["flags"]["remote_az_explicit"])
        self.assertLess(assess("Engineer", "", C_EN)["cap"], 85)


class WorldwideButExcludedTest(unittest.TestCase):
    """(d) worldwide remote but AZ explicitly excluded -> conflict recorded, < 85."""

    def test_conflict_and_low(self):
        v, final, cap = _final(D_EN, remote_worldwide=["Work from anywhere in the world."],
                               remote_country_restricted=["Candidates from Azerbaijan are not considered."])
        self.assertIn("remote_vs_restriction", v["conflicts"])
        self.assertEqual(v["route"], "restricted")
        self.assertEqual(cap, 15)
        self.assertLess(final, 85)

    def test_even_if_ai_misses_the_exclusion(self):
        v, final, cap = _final(D_EN, remote_worldwide=["Work from anywhere in the world."])
        self.assertEqual(v["ai_score"], 90)
        self.assertEqual(final, 15)  # pre-check: AZ negated -> cap 15


if __name__ == "__main__":
    unittest.main()
