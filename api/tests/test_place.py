"""Place normalization for location facets."""

from __future__ import annotations

import unittest

from app.place import (
    aggregate_cities,
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
        self.assertEqual(place_label("Tokyo"), "Tokyo, Japan")
        self.assertEqual(place_label("Bakı"), "Bakı")
        self.assertEqual(place_label("Baku"), "Bakı")

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

    def test_matching_stored_cities(self):
        stored = ["Tokyo", "Tokyo, Japan", "Remote", "Berlin, Germany"]
        matched = matching_stored_cities("Tokyo, Japan", stored)
        self.assertEqual(set(matched), {"Tokyo", "Tokyo, Japan"})
        self.assertNotIn("Remote", matched)
        self.assertNotIn("Berlin, Germany", matched)


if __name__ == "__main__":
    unittest.main()
