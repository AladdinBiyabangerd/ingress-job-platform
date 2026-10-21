"""Regression tests from earlier live-eval errors, on the real fixture ads.

The AI answers below are the exact (trimmed to true flags) answers the live passes returned;
each test pins how the current code scores them.
- 1072 N-iX: title country list incl. Azerbaijan (v9 live FN: model omitted the flag).
- 1200: model copied our "Location field (…):" label into the quote (v9.1 live FN).
- 72 Ashby: bare "EMEA" quote + work_location_unspecified (v9.1 live FP).
- 1146 Onlyplay: role benefit mentioning an office is not a company statement (v9 live FN).
- 514: Ukrainian allowed / excluded country lists (safe 84 with a conflict; see report).
"""

from __future__ import annotations

import json
import unittest

from worker.fit_mapping import FLAGS
from worker.market_fit_eval import load_fixtures, replay_score

ANSWERS = json.loads(r'''{
 "1072": {
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Senior DataOps Engineer (Europe, Georgia, Turkey, Azerbaijan, Ukraine)"
   ]
  },
  "reason": "Vakansiya başlığında Azərbaycan açıq şəkildə göstərilmişdir və remote format dəstəklənir."
 },
 "1200": {
  "remote_worldwide": {
   "value": true,
   "quotes": [
    "Full Remote: The team is scattered worldwide, so we all work comfortably from home."
   ]
  },
  "remote_region_includes_az": {
   "value": true,
   "quotes": [
    "Location field (as listed by the source): Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan"
   ]
  },
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Location field (as listed by the source): Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan"
   ]
  },
  "reason": "Azərbaycanda remote iş mümkündür; bütün ölkələrdən remote işə icazə verilir; relocation və viza sponsorluğu yoxdur."
 },
 "72": {
  "remote_region_includes_az": {
   "value": true,
   "quotes": [
    "We staff across regions rather than relying on on-call rotations",
    "EMEA"
   ]
  },
  "work_location_unspecified": {
   "value": true,
   "quotes": [
    "Location field (as listed by the source): (empty)"
   ]
  },
  "reason": "EMEA region includes Azerbaijan for remote work; no explicit Azerbaijan eligibility, relocation, or visa sponsorship stated. Work location unspecified."
 },
 "514": {
  "remote_region_includes_az": {
   "value": true,
   "quotes": [
    "Дозволені країни: Киргизстан, Азербайджан, Грузія, Вірменія, Узбекистан, Молдова, Україна."
   ]
  },
  "remote_az_explicit": {
   "value": true,
   "quotes": [
    "Дозволені країни: Киргизстан, Азербайджан, Грузія, Вірменія, Узбекистан, Молдова, Україна."
   ]
  },
  "remote_country_restricted": {
   "value": true,
   "quotes": [
    "Країни, з яких кандидати не розглядаються: Казахстан, Росія, Білорусь, країни Європи (крім зазначених у дозволеному списку), США, Канада, Ізраїль."
   ]
  },
  "reason": "Азербайджан дозволений у remote; країни ЄС/США/Канада виключені; relocation або viza sponsorluğu не вказано."
 },
 "1146": {
  "remote_worldwide": {
   "value": true,
   "quotes": [
    "Opportunity to work anywhere in the world (remote work or Lisbon office)"
   ]
  },
  "reason": "Remote work explicitly offered worldwide; no relocation or visa sponsorship mentioned."
 }
}''')


def _raw(key):
    data = {name: {"value": False, "quotes": []} for name in FLAGS}
    data.update(ANSWERS[key])
    return data


class LiveRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ads = {ad["key"]: ad for ad in load_fixtures()}

    def _score(self, key):
        return replay_score(self.ads[key], _raw(key))

    def test_1072_title_country_list(self):
        r = self._score("1072")
        self.assertEqual((r["route"], r["score"]), ("remote_az_explicit", 95))

    def test_1200_prompt_label_stripped(self):
        r = self._score("1200")
        self.assertEqual((r["route"], r["score"]), ("remote_az_explicit", 95))
        self.assertEqual(r["quotes"]["remote_az_explicit"], ["Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan"])

    def test_72_bare_emea_stays_below_band(self):
        r = self._score("72")
        self.assertLess(r["score"], 85)
        self.assertTrue(r["flags"]["work_location_unspecified"])

    def test_1146_role_benefit_with_office(self):
        r = self._score("1146")
        self.assertEqual((r["route"], r["score"]), ("remote_worldwide", 90))

    def test_514_conflict_goes_to_moderator(self):
        r = self._score("514")
        self.assertEqual((r["route"], r["score"]), ("remote_az_explicit", 84))
        self.assertIn("remote_vs_restriction", r["conflicts"])


if __name__ == "__main__":
    unittest.main()
