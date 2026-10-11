"""Place normalization for location facets."""

from __future__ import annotations

import unittest

from app.place import (
    aggregate_cities,
    aggregate_countries,
    country_label,
    is_remote_place,
    matching_stored_cities,
    place_key,
    place_label,
)


class PlaceTests(unittest.TestCase):
    def test_remote_variants(self):
        for value in (
            "Remote",
            "Remote (Worldwide)",
            "Remote (United States)",
            "Remote (Time zone: CET (+/- 3 hours))",
            "Remote (CET (+/- 3 hours))",
            "Anywhere in the World",
            "Worldwide",
            "Uzaqdan",
            "Work from anywhere",
        ):
            self.assertTrue(is_remote_place(value), value)
            self.assertEqual(place_key(value), "")

    def test_city_merge_key(self):
        self.assertEqual(place_key("Tokyo"), place_key("Tokyo, Japan"))
        self.assertEqual(place_key("Amsterdam"), place_key("Amsterdam, Netherlands"))
        self.assertEqual(place_key("Berlin HQ"), place_key("Berlin, Germany"))
        self.assertEqual(place_key("Berlin Office"), "berlin")
        self.assertEqual(place_key("Düsseldorf"), place_key("Dusseldorf, Germany"))
        self.assertEqual(place_label("Tokyo"), "Tokyo, Japan")
        self.assertEqual(place_label("Bakı"), "Bakı")
        self.assertEqual(place_label("Baku"), "Bakı")

    def test_country_label_known_hubs(self):
        self.assertEqual(country_label("Tokyo"), "Japan")
        self.assertEqual(country_label("Tokyo, Japan"), "Japan")
        self.assertEqual(country_label("Leonberg, Germany"), "Germany")
        self.assertEqual(country_label("Düsseldorf"), "Germany")
        self.assertEqual(country_label("Berlin HQ"), "Germany")
        self.assertEqual(country_label("Berlin Office"), "Germany")
        self.assertEqual(country_label("Herndon, VA"), "United States")
        self.assertEqual(country_label("Amsterdam, Netherlands"), "Netherlands")
        self.assertEqual(country_label("Barcelona"), "Spain")
        self.assertEqual(country_label("Bakı"), "Azerbaijan")

    def test_country_label_never_misgroups_tokyo(self):
        # Curated hub map wins over a garbage/conflicting suffix.
        self.assertEqual(country_label("Tokyo, India"), "Japan")
        self.assertEqual(country_label("Tokyo, Hindistan"), "Japan")
        self.assertNotEqual(country_label("Tokyo"), "India")

    def test_country_label_suffix_for_unknown_city(self):
        self.assertEqual(country_label("Leonbergstadt, Germany"), "Germany")
        self.assertEqual(country_label("Somewhere, VA"), "United States")
        self.assertEqual(country_label("Unknownville"), "")

    def test_expanded_hubs_and_ambiguous_bares(self):
        self.assertEqual(country_label("Stuttgart"), "Germany")
        self.assertEqual(country_label("Köln"), "Germany")
        self.assertEqual(country_label("Wrocław"), "Poland")
        self.assertEqual(country_label("Bangalore"), "India")
        self.assertEqual(country_label("São Paulo"), "Brazil")
        self.assertEqual(country_label("Cambridge, MA"), "United States")
        self.assertEqual(country_label("Cambridge, UK"), "United Kingdom")
        # Ambiguous bare names stay unresolved rather than guessing.
        for bare in ("Cambridge", "Birmingham", "Hamilton", "Victoria", "Leon"):
            self.assertEqual(country_label(bare), "", bare)

    def test_aggregate_drops_remote_and_merges_cities(self):
        items = aggregate_cities(
            [
                ("Remote (Worldwide)", 32),
                ("Remote", 25),
                ("Anywhere in the World", 8),
                ("Worldwide", 7),
                ("Uzaqdan", 3),
                ("Tokyo", 7),
                ("Tokyo, Japan", 6),
                ("Amsterdam, Netherlands", 6),
                ("Leonberg, Germany", 5),
                ("Barcelona", 4),
            ],
            limit=12,
        )
        names = [item["name"] for item in items]
        self.assertNotIn("Remote", names)
        self.assertNotIn("Remote (Worldwide)", names)
        self.assertNotIn("Worldwide", names)
        self.assertNotIn("Uzaqdan", names)
        self.assertIn("Tokyo, Japan", names)
        tokyo = next(item for item in items if item["name"] == "Tokyo, Japan")
        self.assertEqual(tokyo["total"], 13)
        self.assertIn("Barcelona, Spain", names)

    def test_aggregate_countries_groups_cities(self):
        items = aggregate_countries(
            [
                ("Remote (Worldwide)", 32),
                ("Tokyo", 7),
                ("Tokyo, Japan", 6),
                ("Leonberg, Germany", 5),
                ("Munich, Germany", 4),
                ("Berlin HQ", 3),
                ("Düsseldorf", 2),
                ("Hamburg, Germany", 1),
                ("Paris, France", 4),
                ("Barcelona", 3),
                ("Herndon, VA", 2),
                ("Amsterdam, Netherlands", 6),
            ],
            limit=12,
        )
        by_name = {item["name"]: item["total"] for item in items}
        self.assertEqual(by_name["Japan"], 13)
        self.assertEqual(by_name["Germany"], 15)
        self.assertEqual(by_name["France"], 4)
        self.assertEqual(by_name["Spain"], 3)
        self.assertEqual(by_name["United States"], 2)
        self.assertEqual(by_name["Netherlands"], 6)
        self.assertNotIn("Tokyo, Japan", by_name)
        self.assertNotIn("India", by_name)

    def test_matching_stored_cities(self):
        stored = ["Tokyo", "Tokyo, Japan", "Remote", "Berlin, Germany"]
        matched = matching_stored_cities("Tokyo, Japan", stored)
        self.assertEqual(set(matched), {"Tokyo", "Tokyo, Japan"})
        self.assertNotIn("Remote", matched)
        self.assertNotIn("Berlin, Germany", matched)

    def test_matching_stored_by_country(self):
        stored = [
            "Tokyo",
            "Tokyo, Japan",
            "Berlin, Germany",
            "Munich, Germany",
            "Berlin HQ",
            "Düsseldorf",
            "Paris, France",
            "Remote",
        ]
        matched = matching_stored_cities("Germany", stored)
        self.assertEqual(
            set(matched),
            {"Berlin, Germany", "Munich, Germany", "Berlin HQ", "Düsseldorf", "Germany"},
        )
        self.assertNotIn("Tokyo", matched)
        self.assertNotIn("Paris, France", matched)
        japan = matching_stored_cities("Japan", stored)
        self.assertEqual(set(japan), {"Tokyo", "Tokyo, Japan", "Japan"})


if __name__ == "__main__":
    unittest.main()
