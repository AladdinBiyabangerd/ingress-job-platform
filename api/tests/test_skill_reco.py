"""Session-vector hybrid skill recommender (60/25/15)."""

from __future__ import annotations

import unittest

from app.skill_reco import HybridRecommender, SkillCatalog, UserSession
from app.skill_reco.vectors import cosine_similarity, normalize


class SkillRecoTests(unittest.TestCase):
    def setUp(self):
        self.catalog = SkillCatalog()
        self.engine = HybridRecommender(self.catalog)

    def test_normalize_and_cosine(self):
        a = normalize([3.0, 0.0, 4.0])
        self.assertAlmostEqual(sum(x * x for x in a), 1.0, places=6)
        self.assertAlmostEqual(cosine_similarity(a, a), 1.0, places=6)

    def test_cold_start_popular(self):
        rows = self.engine.get_recommendations(UserSession(), top_n=5)
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(r.bucket == "cold_start" for r in rows))
        pops = [r.skill.popularity_score for r in rows]
        self.assertEqual(pops, sorted(pops, reverse=True))

    def test_excludes_clicked(self):
        session = UserSession()
        figma = self.catalog.get_by_name("Figma")
        assert figma is not None
        session.click(figma)
        names = {r.name for r in self.engine.get_recommendations(session, top_n=10)}
        self.assertNotIn("Figma", names)

    def test_decay_prefers_recent(self):
        session = UserSession(decay=0.7)
        figma = self.catalog.get_by_name("Figma")
        html = self.catalog.get_by_name("HTML/CSS")
        assert figma and html
        session.click(figma)
        session.click(html)
        weights = session.debug_weights()
        self.assertEqual(weights[-1][0], html.id)
        self.assertAlmostEqual(weights[-1][1], 1.0)
        self.assertAlmostEqual(weights[0][1], 0.7)
        vec = session.session_vector()
        assert vec is not None
        # Closer to HTML/CSS than to Figma alone after the shift.
        sim_html = cosine_similarity(vec, html.embedding)
        sim_figma = cosine_similarity(vec, figma.embedding)
        self.assertGreater(sim_html, sim_figma)

    def test_bucket_mix_after_figma(self):
        session = UserSession()
        figma = self.catalog.get_by_name("Figma")
        assert figma is not None
        session.click(figma)
        rows = self.engine.get_recommendations(session, top_n=10)
        buckets = {r.bucket for r in rows}
        self.assertIn("exploit", buckets)
        # Should surface web/product adjacency or serendipity, not only UI clones.
        self.assertTrue(buckets - {"exploit"})


if __name__ == "__main__":
    unittest.main()
