"""In-memory skill catalog with hand-crafted 5-D embeddings.

Embedding axes (interpretable toy space — replace with real model later)
----------------------------------------------------------------------
0  visual_design
1  code_implementation
2  product_strategy
3  data_analytics
4  growth_marketing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.skill_reco.vectors import Vector, normalize

# Closely related category groups for the 25% adjacent bucket.
CATEGORY_ADJACENCY: dict[str, frozenset[str]] = {
    "UI/UX Design": frozenset({"Web Development", "Product Management"}),
    "Web Development": frozenset({"UI/UX Design", "Programming", "Data Science"}),
    "Programming": frozenset({"Web Development", "Data Science", "DevOps"}),
    "Data Science": frozenset({"Programming", "Product Management", "Marketing"}),
    "Product Management": frozenset({"UI/UX Design", "Marketing", "Data Science"}),
    "Marketing": frozenset({"Product Management", "Data Science", "UI/UX Design"}),
    "DevOps": frozenset({"Programming", "Web Development"}),
}


@dataclass(frozen=True, slots=True)
class Skill:
    id: int
    name: str
    category: str
    tags: tuple[str, ...]
    popularity_score: float
    embedding: tuple[float, ...]

    def vector(self) -> list[float]:
        return list(self.embedding)


def _skill(
    skill_id: int,
    name: str,
    category: str,
    tags: Iterable[str],
    popularity: float,
    embedding: Vector,
) -> Skill:
    pop = max(0.0, min(1.0, float(popularity)))
    emb = tuple(normalize(embedding))
    return Skill(
        id=skill_id,
        name=name,
        category=category,
        tags=tuple(tags),
        popularity_score=pop,
        embedding=emb,
    )


def build_mock_catalog() -> list[Skill]:
    """~20 diverse skills spanning design → code → product → data → growth."""
    # Dims: design, code, product, data, marketing
    return [
        _skill(1, "Figma", "UI/UX Design", ["design", "ui", "prototype"], 0.92, [0.95, 0.15, 0.35, 0.05, 0.20]),
        _skill(2, "User Research", "UI/UX Design", ["ux", "research", "interviews"], 0.78, [0.88, 0.05, 0.55, 0.25, 0.15]),
        _skill(3, "Design Systems", "UI/UX Design", ["ui", "tokens", "components"], 0.74, [0.90, 0.35, 0.40, 0.10, 0.10]),
        _skill(4, "HTML/CSS", "Web Development", ["frontend", "markup", "styling"], 0.95, [0.55, 0.75, 0.20, 0.05, 0.15]),
        _skill(5, "JavaScript", "Web Development", ["frontend", "language"], 0.97, [0.25, 0.90, 0.20, 0.15, 0.10]),
        _skill(6, "React", "Web Development", ["frontend", "framework", "ui"], 0.94, [0.40, 0.88, 0.25, 0.10, 0.10]),
        _skill(7, "Web Design", "Web Development", ["design", "frontend", "layout"], 0.80, [0.75, 0.55, 0.30, 0.05, 0.25]),
        _skill(8, "TypeScript", "Programming", ["language", "types"], 0.88, [0.15, 0.92, 0.20, 0.20, 0.05]),
        _skill(9, "Python", "Programming", ["language", "scripting"], 0.96, [0.05, 0.85, 0.25, 0.55, 0.10]),
        _skill(10, "SQL", "Data Science", ["data", "database", "query"], 0.91, [0.05, 0.55, 0.30, 0.90, 0.15]),
        _skill(11, "Pandas", "Data Science", ["data", "python", "etl"], 0.82, [0.05, 0.60, 0.25, 0.92, 0.10]),
        _skill(12, "Machine Learning", "Data Science", ["ml", "models", "ai"], 0.89, [0.05, 0.50, 0.35, 0.95, 0.20]),
        _skill(13, "A/B Testing", "Product Management", ["experiment", "metrics"], 0.77, [0.20, 0.25, 0.80, 0.65, 0.55]),
        _skill(14, "Roadmapping", "Product Management", ["strategy", "planning"], 0.76, [0.25, 0.10, 0.95, 0.30, 0.40]),
        _skill(15, "User Stories", "Product Management", ["agile", "requirements"], 0.72, [0.30, 0.15, 0.90, 0.20, 0.25]),
        _skill(16, "SEO", "Marketing", ["growth", "content", "search"], 0.85, [0.20, 0.20, 0.45, 0.35, 0.92]),
        _skill(17, "Content Marketing", "Marketing", ["content", "brand"], 0.79, [0.25, 0.10, 0.50, 0.25, 0.90]),
        _skill(18, "Google Analytics", "Marketing", ["analytics", "growth"], 0.83, [0.15, 0.25, 0.45, 0.70, 0.85]),
        _skill(19, "Docker", "DevOps", ["containers", "deploy"], 0.87, [0.05, 0.80, 0.25, 0.30, 0.05]),
        _skill(20, "CI/CD", "DevOps", ["pipelines", "automation"], 0.84, [0.05, 0.75, 0.30, 0.25, 0.05]),
        _skill(21, "Accessibility (a11y)", "UI/UX Design", ["a11y", "inclusive"], 0.70, [0.85, 0.40, 0.35, 0.10, 0.15]),
        _skill(22, "UI Frameworks", "Web Development", ["frontend", "components"], 0.81, [0.60, 0.80, 0.25, 0.05, 0.10]),
    ]


@dataclass
class SkillCatalog:
    """In-memory / DataFrame-ready skill store."""

    skills: list[Skill] = field(default_factory=build_mock_catalog)
    adjacency: dict[str, frozenset[str]] | None = None

    def __post_init__(self) -> None:
        self._by_id = {s.id: s for s in self.skills}
        self._by_name = {s.name.lower(): s for s in self.skills}
        if self.adjacency is None:
            self.adjacency = dict(CATEGORY_ADJACENCY)

    def get(self, skill_id: int) -> Skill | None:
        return self._by_id.get(skill_id)

    def get_by_name(self, name: str) -> Skill | None:
        return self._by_name.get(str(name or "").strip().lower())

    def all(self) -> list[Skill]:
        return list(self.skills)

    def adjacent_categories(self, category: str) -> frozenset[str]:
        assert self.adjacency is not None
        return self.adjacency.get(category, frozenset())

    def cold_start(self, top_n: int = 10) -> list[Skill]:
        """Global popularity ranking for empty sessions."""
        ranked = sorted(
            self.skills,
            key=lambda s: (-s.popularity_score, s.name),
        )
        return ranked[: max(1, top_n)]
