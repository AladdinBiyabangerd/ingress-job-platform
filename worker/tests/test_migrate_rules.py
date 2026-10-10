import importlib.util
import unittest
from pathlib import Path

_p = Path(__file__).resolve().parents[1] / "scripts" / "migrate_rules_2026_10.py"
_s = importlib.util.spec_from_file_location("migrate_rules", _p)
m = importlib.util.module_from_spec(_s)
_s.loader.exec_module(m)


def row(**kw):
    base = dict(id=1, title="Engineer", city="", text="", tech_stack="[]",
                category="Backend", relocation=0, remote=0)
    base.update(kw)
    return base


class MigrateRulesTest(unittest.TestCase):
    def test_city_hybrid(self):
        self.assertEqual(m.compute(row(city="Hybrid")), {"city": ""})
        self.assertEqual(m.compute(row(city="Cambridge / Hybrid")), {"city": "Cambridge"})

    def test_remote_relocation_default_dropped(self):
        self.assertEqual(m.compute(row(remote=1, relocation=1, text="<p>Build APIs</p>")), {"relocation": 0})

    def test_skip_262(self):
        self.assertNotIn("relocation", m.compute(row(id=262, remote=1, relocation=1)))

    def test_never_touches_other_fields(self):
        self.assertTrue(set(m.compute(row(city="Hybrid", remote=1, relocation=1))) <= {"city", "category", "relocation"})


if __name__ == "__main__":
    unittest.main()
