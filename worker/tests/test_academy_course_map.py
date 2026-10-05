"""Academy skill ↔ course map merges into skill_dictionary seed."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from export_skill_dictionary import (  # noqa: E402
    apply_academy_course_map,
    load_academy_course_map,
)
from worker.skills import load_seed, seed_skill_dictionary  # noqa: E402


class AcademyCourseMapTest(unittest.TestCase):
    def test_map_covers_real_dictionary_skills(self):
        mapping = load_academy_course_map()
        self.assertGreater(len(mapping), 20)
        names = {s["canonical_name"] for s in load_seed()}
        missing = sorted(k for k in mapping if k not in names)
        self.assertEqual(missing, [])

    def test_packaged_seed_includes_courses(self):
        skills = load_seed()
        filled = [s for s in skills if s.get("academy_course_ids")]
        self.assertGreaterEqual(len(filled), 20)
        aws = next(s for s in skills if s["canonical_name"] == "AWS")
        self.assertIn(
            "cloud-computing-with-aws-and-terraform-az",
            aws["academy_course_ids"],
        )

    def test_seed_upsert_writes_courses(self):
        import sqlite3
        import tempfile

        mapping = load_academy_course_map()
        skills = [
            {
                "canonical_name": "AWS",
                "synonyms": ["amazon web services"],
                "category_hint": "cloud",
                "academy_course_ids": [],
            }
        ]
        apply_academy_course_map(skills, mapping)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seed.json"
            path.write_text(
                json.dumps({"skills": skills}, ensure_ascii=False),
                encoding="utf-8",
            )
            conn = sqlite3.connect(":memory:")
            n = seed_skill_dictionary(conn, path)
            self.assertEqual(n, 1)
            row = conn.execute(
                "SELECT academy_course_ids FROM skill_dictionary WHERE canonical_name = 'AWS'"
            ).fetchone()
            self.assertIsNotNone(row)
            courses = json.loads(row[0])
            self.assertEqual(courses, mapping["AWS"])


if __name__ == "__main__":
    unittest.main()
