"""Regional ATS groups: catalog rows match connectors, large groups rotate."""

from __future__ import annotations

import unittest

from worker.ats_boards import ATS_MAX_BOARDS, GROUPS
from worker.catalog import SOURCES
from worker.connectors.ats import ATS_GROUP_CONNECTORS, round_robin
from worker.runner import BUILDERS


class AtsGroupsTest(unittest.TestCase):
    def test_every_group_has_row_and_builder(self):
        enabled = {row["name"] for row in SOURCES if row["enabled"]}
        for name, _ats, _region, boards in GROUPS:
            self.assertIn(name, enabled)
            self.assertIn(name, BUILDERS)
            self.assertGreaterEqual(len(boards), 3, name)
            self.assertEqual(len(set(boards)), len(boards), name)
        names = {row["name"] for row in SOURCES}
        self.assertTrue(enabled <= set(BUILDERS))
        self.assertTrue(set(BUILDERS) <= names)

    def test_rotation_covers_all_boards(self):
        cls = ATS_GROUP_CONNECTORS["Greenhouse boards (US West)"]
        conn = cls(None, None)
        self.assertGreater(len(cls.boards), ATS_MAX_BOARDS)
        seen: set[str] = set()
        for slot in range(4):
            picked = conn.boards_this_pass(now=slot * 3 * 3600 + 1)
            self.assertEqual(len(picked), ATS_MAX_BOARDS)
            seen.update(picked)
        self.assertEqual(seen, set(cls.boards))

    def test_small_group_reads_all(self):
        cls = ATS_GROUP_CONNECTORS["Greenhouse boards (Canada)"]
        self.assertEqual(cls(None, None).boards_this_pass(now=0), cls.boards)

    def test_round_robin(self):
        self.assertEqual(round_robin([[1, 2, 3], [4], [5, 6]]), [1, 4, 5, 2, 6, 3])


if __name__ == "__main__":
    unittest.main()
