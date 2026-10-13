"""Hybrid recommender: 60% exploit / 25% adjacent / 15% serendipity.

Algorithm
---------
1. Cold start → global popularity (no session vector).
2. Otherwise score every non-clicked skill by cosine(session, skill).
3. Partition candidates:
   - **exploit**: same category as dominant click, or sim ≥ ``exploit_floor``
     within adjacent categories (tight neighborhood).
   - **adjacent**: category ∈ adjacency(dominant), moderate similarity band.
   - **serendipity**: other categories; rank by popularity × mild similarity
     so we do not inject pure noise.
4. Allocate slots with the 60/25/15 rule (rounded, remainder → exploit),
   then interleave buckets so the UI list is mixed, not three blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.skill_reco.catalog import Skill, SkillCatalog
from app.skill_reco.session import UserSession
from app.skill_reco.vectors import cosine_similarity

Bucket = Literal["exploit", "adjacent", "serendipity", "cold_start"]

# Soft floors — keep exploration related, not random.
EXPLOIT_SIM_FLOOR = 0.35
ADJACENT_SIM_FLOOR = 0.12
ADJACENT_SIM_CEIL = 0.92


@dataclass(frozen=True, slots=True)
class Recommendation:
    skill: Skill
    bucket: Bucket
    similarity: float
    score: float

    @property
    def name(self) -> str:
        return self.skill.name

    @property
    def category(self) -> str:
        return self.skill.category


@dataclass
class HybridRecommender:
    catalog: SkillCatalog
    exploit_ratio: float = 0.60
    adjacent_ratio: float = 0.25
    serendipity_ratio: float = 0.15

    def __post_init__(self) -> None:
        total = self.exploit_ratio + self.adjacent_ratio + self.serendipity_ratio
        if abs(total - 1.0) > 1e-6:
            raise ValueError("bucket ratios must sum to 1.0")

    def _slot_counts(self, top_n: int) -> tuple[int, int, int]:
        n = max(1, int(top_n))
        exploit = max(1, round(n * self.exploit_ratio))
        adjacent = max(0, round(n * self.adjacent_ratio))
        serendipity = max(0, n - exploit - adjacent)
        # Prefer giving remainder to exploit for stable UX.
        while exploit + adjacent + serendipity < n:
            exploit += 1
        while exploit + adjacent + serendipity > n:
            if exploit > 1:
                exploit -= 1
            elif adjacent > 0:
                adjacent -= 1
            else:
                serendipity = max(0, serendipity - 1)
        return exploit, adjacent, serendipity

    def get_recommendations(
        self,
        user_session: UserSession,
        top_n: int = 10,
    ) -> list[Recommendation]:
        """Return a balanced recommendation list for the current session."""
        n = max(1, int(top_n))
        if user_session.is_empty:
            return [
                Recommendation(
                    skill=skill,
                    bucket="cold_start",
                    similarity=0.0,
                    score=skill.popularity_score,
                )
                for skill in self.catalog.cold_start(n)
            ]

        session_vec = user_session.session_vector()
        if session_vec is None:
            return self.get_recommendations(UserSession(), top_n=n)

        exclude = user_session.clicked_id_set()
        dominant = user_session.dominant_category() or ""
        adjacent_cats = self.catalog.adjacent_categories(dominant)

        scored: list[tuple[Skill, float]] = []
        for skill in self.catalog.all():
            if skill.id in exclude:
                continue
            sim = cosine_similarity(session_vec, skill.embedding)
            scored.append((skill, sim))

        exploit_pool: list[tuple[Skill, float, float]] = []
        adjacent_pool: list[tuple[Skill, float, float]] = []
        serendipity_pool: list[tuple[Skill, float, float]] = []

        for skill, sim in scored:
            pop = skill.popularity_score
            same = skill.category == dominant
            is_adj = skill.category in adjacent_cats

            if same:
                # 60% exploitation — stay in the active category.
                exploit_pool.append((skill, sim, sim * 0.85 + pop * 0.15))
            elif is_adj and sim >= ADJACENT_SIM_FLOOR:
                # 25% related exploration — neighboring categories only.
                adjacent_pool.append((skill, sim, sim * 0.70 + pop * 0.30))
            else:
                # 15% serendipity — distant categories; popularity-led, mild sim.
                serendipity_pool.append(
                    (skill, sim, pop * 0.75 + max(sim, 0.0) * 0.25)
                )

        exploit_pool.sort(key=lambda row: (-row[2], -row[1], row[0].name))
        adjacent_pool.sort(key=lambda row: (-row[2], -row[1], row[0].name))
        serendipity_pool.sort(key=lambda row: (-row[2], -row[1], row[0].name))

        n_ex, n_ad, n_se = self._slot_counts(n)
        picked_ids: set[int] = set()
        buckets: dict[Bucket, list[Recommendation]] = {
            "exploit": [],
            "adjacent": [],
            "serendipity": [],
        }

        def _take(
            pool: list[tuple[Skill, float, float]],
            bucket: Bucket,
            need: int,
        ) -> None:
            for skill, sim, score in pool:
                if len(buckets[bucket]) >= need:
                    break
                if skill.id in picked_ids:
                    continue
                picked_ids.add(skill.id)
                buckets[bucket].append(
                    Recommendation(
                        skill=skill,
                        bucket=bucket,
                        similarity=round(sim, 4),
                        score=round(score, 4),
                    )
                )

        _take(exploit_pool, "exploit", n_ex)
        _take(adjacent_pool, "adjacent", n_ad)
        _take(serendipity_pool, "serendipity", n_se)

        # Backfill empty slots from remaining pools (exploit → adjacent → serendipity).
        leftovers = (
            [("exploit", exploit_pool), ("adjacent", adjacent_pool), ("serendipity", serendipity_pool)]
        )
        while sum(len(v) for v in buckets.values()) < n:
            progressed = False
            for bucket_name, pool in leftovers:
                if sum(len(v) for v in buckets.values()) >= n:
                    break
                before = len(buckets[bucket_name])  # type: ignore[index]
                _take(pool, bucket_name, before + 1)  # type: ignore[arg-type]
                if len(buckets[bucket_name]) > before:  # type: ignore[index]
                    progressed = True
            if not progressed:
                break

        # Interleave for a mixed UI strip (not three monochrome blocks).
        return self._interleave(buckets, n)

    @staticmethod
    def _interleave(
        buckets: dict[Bucket, list[Recommendation]],
        top_n: int,
    ) -> list[Recommendation]:
        order: list[Bucket] = ["exploit", "adjacent", "serendipity"]
        cursors = {key: 0 for key in order}
        out: list[Recommendation] = []
        while len(out) < top_n:
            progressed = False
            for key in order:
                idx = cursors[key]
                rows = buckets.get(key) or []
                if idx >= len(rows):
                    continue
                out.append(rows[idx])
                cursors[key] = idx + 1
                progressed = True
                if len(out) >= top_n:
                    break
            if not progressed:
                break
        return out[:top_n]
