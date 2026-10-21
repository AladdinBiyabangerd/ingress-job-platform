"""market-fit-v10 live-pass regressions (exact AI answers from the fresh v10 live run).

Two general quote-validation bugs found by that run, fixed after it:
1. A restriction quote that itself names Azerbaijan as allowed ("Allowed countries: Azerbaijan,
   Georgia", "Дозволені країни: … Азербайджан …") was accepted as remote_country_restricted
   (514, synthetic-list-allowed-en/-ru: 84 -> 95). Such a quote cannot back "limited to places
   that exclude Azerbaijan"; it is now rejected ("alternativ"), so the flag drops when it is the
   only evidence. "Central Asia" alone is debatable and does not count (915 stays restricted).
2. "Candidates from Azerbaijan and Russia are not considered." failed the relevance check for
   candidate_location_restricted and the flag was dropped (synthetic-list-both-en): the conflict
   was lost (84 only via the pre-check). "candidates from" is now relevant; the conflict is kept.
"""

from __future__ import annotations

import json
import unittest

from worker.fit_mapping import FLAGS
from worker.market_fit import check_quote
from worker.market_fit_eval import load_fixtures, replay_score

ANSWERS = json.loads(r'''{
 "514": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Armenia, Georgia, Azerbaijan, Uzbekistan, Ukraine",
    "Дозволені країни: Киргизстан, Азербайджан, Грузія, Вірменія, Узбекистан, Молдова, Україна."
   ]
  },
  "remote_country_restricted": {
   "value": true,
   "quotes": [
    "Дозволені країни: Киргизстан, Азербайджан, Грузія, Вірменія, Узбекистан, Молдова, Україна."
   ]
  },
  "reason": "Vakansiya Azərbaycandan remote işləməyə açıqdır (icazə verilən ölkələr siyahısında qeyd olunub), lakin iş məhdud coğrafi region üzrə tənzimlənir."
 },
 "synthetic-list-allowed-en": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Allowed countries: Azerbaijan, Georgia, Armenia, Moldova."
   ]
  },
  "remote_country_restricted": {
   "value": true,
   "quotes": [
    "Allowed countries: Azerbaijan, Georgia, Armenia, Moldova."
   ]
  },
  "reason": "Vakansiya Azərbaycandan remote işləməyə icazə verir (icazə verilən ölkələr siyahısında göstərilib)."
 },
 "synthetic-list-allowed-ru": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Разрешённые страны: Азербайджан, Грузия, Армения, Молдова."
   ]
  },
  "remote_country_restricted": {
   "value": true,
   "quotes": [
    "Разрешённые страны: Азербайджан, Грузия, Армения, Молдова."
   ]
  },
  "reason": "Vakansiya Azərbaycandan remote işləməyə icazə verir, çünki ölkə icazə verilən ölkələr siyahısında açıq şəkildə göstərilib."
 },
 "synthetic-list-both-en": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Allowed countries: Azerbaijan, Georgia, Armenia."
   ]
  },
  "candidate_location_restricted": {
   "value": true,
   "quotes": [
    "Candidates from Azerbaijan and Russia are not considered."
   ]
  },
  "reason": "Elanda Azərbaycan icazə verilən ölkələr siyahısındadır, lakin eyni zamanda namizədlər bölməsində Azərbaycanın namizədlərinin nəzərə alınmadığı qeyd olunaraq ziddiyyət yaradılıb."
 },
 "synthetic-list-both-uk": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Дозволені країни: Азербайджан, Грузія, Вірменія."
   ]
  },
  "reason": "Elanda həm Azərbaycan icazə verilən ölkələr siyahısındadır, həm də istisna olunanlar siyahısında qeyd olunub, buna görə ziddiyyət mövcuddur."
 },
 "915": {
  "remote_region_includes_az": {
   "value": true,
   "quotes": [
    "We’re especially interested in candidates located in Eastern European or Central Asian regions.",
    "100% distributed team!",
    "Remote First Culture"
   ]
  },
  "candidate_location_restricted": {
   "value": true,
   "quotes": [
    "We’re especially interested in candidates located in Eastern European or Central Asian regions."
   ]
  },
  "reason": "Azərbaycan Cənubi Qərb və Orta Asiyanın ərazisindən sayılmayan adaylar bloklanır; remote worldwide yoxdur."
 }
}''')


def _raw(key):
    data = {name: {"value": False, "quotes": []} for name in FLAGS}
    data.update(ANSWERS[key])
    return data


class V10LiveRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ads = {ad["key"]: ad for ad in load_fixtures()}

    def _score(self, key):
        return replay_score(self.ads[key], _raw(key))

    def test_allowed_list_quoted_as_restriction_is_dropped(self):
        for key in ("514", "synthetic-list-allowed-en", "synthetic-list-allowed-ru"):
            with self.subTest(key=key):
                r = self._score(key)
                self.assertEqual((r["route"], r["score"]), ("remote_az_explicit", 95))
                self.assertFalse(r["flags"]["remote_country_restricted"])
                self.assertTrue(any("icazəli yerlər arasındadır" in n for n in r["notes"]))

    def test_both_lists_keep_conflict(self):
        r = self._score("synthetic-list-both-en")
        self.assertEqual(r["score"], 84)
        self.assertIn("remote_vs_restriction", r["conflicts"])
        self.assertTrue(r["flags"]["candidate_location_restricted"])

    def test_both_lists_model_missed_exclusion_precheck_caps(self):
        r = self._score("synthetic-list-both-uk")
        self.assertEqual((r["score"], r["cap"]), (84, 84))  # eligibility pre-check conflict cap

    def test_central_asia_alone_does_not_drop_restriction(self):
        r = self._score("915")
        self.assertTrue(r["flags"]["candidate_location_restricted"])
        self.assertLess(r["score"], 85)

    def test_quote_checks(self):
        drop = "alternativ: sitatda Azərbaycan icazəli yerlər arasındadır, məhdudiyyət deyil"
        self.assertEqual(check_quote("remote_country_restricted", "Allowed countries: Azerbaijan, Georgia."), drop)
        self.assertEqual(check_quote("remote_country_restricted", "Remote within the EU and Azerbaijan only"), drop)
        self.assertEqual(check_quote("remote_country_restricted", "Remote within Germany only"), "")
        self.assertEqual(check_quote("remote_country_restricted", "Remote worldwide, excluding Azerbaijan."), "")
        self.assertEqual(
            check_quote("candidate_location_restricted", "Candidates from Azerbaijan and Russia are not considered."), ""
        )


if __name__ == "__main__":
    unittest.main()
