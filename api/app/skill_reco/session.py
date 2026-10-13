"""User click session with exponential time-decay session vector.

Math
----
Clicks are ordered oldest → newest as ``v_0, v_1, …, v_{n-1}``.
With decay ``λ ∈ (0, 1]`` (default 0.7), weight for click ``i`` is::

    w_i = λ^{n-1-i}

so the newest click gets ``w = 1``, the previous ``λ``, then ``λ²``, …
The session vector is the weighted mean, then L2-normalized::

    s = normalize( Σ_i w_i · v_i  /  Σ_i w_i )

Only the last ``max_history`` clicks are kept (default 8) so old
context fades both by decay and by eviction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.skill_reco.catalog import Skill
from app.skill_reco.vectors import normalize, weighted_average


@dataclass
class UserSession:
    """Tracks clicked skills and maintains a decaying session embedding."""

    decay: float = 0.7
    max_history: int = 8
    clicked_ids: list[int] = field(default_factory=list)
    _vectors: list[list[float]] = field(default_factory=list)
    _categories: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")
        if self.max_history < 1:
            raise ValueError("max_history must be >= 1")

    @property
    def is_empty(self) -> bool:
        return not self.clicked_ids

    def click(self, skill: Skill) -> None:
        """Record a click and refresh the session vector."""
        self.clicked_ids.append(int(skill.id))
        self._vectors.append(skill.vector())
        self._categories.append(skill.category)
        overflow = len(self.clicked_ids) - self.max_history
        if overflow > 0:
            del self.clicked_ids[:overflow]
            del self._vectors[:overflow]
            del self._categories[:overflow]

    def clicked_id_set(self) -> set[int]:
        return set(self.clicked_ids)

    def dominant_category(self) -> str | None:
        """Most recent click's category (smooth shift anchor)."""
        if not self._categories:
            return None
        return self._categories[-1]

    def session_vector(self) -> list[float] | None:
        """Time-decay weighted average of click embeddings, L2-normalized."""
        if not self._vectors:
            return None
        n = len(self._vectors)
        # Newest index n-1 → weight λ^0 = 1; older → λ^k
        weights = [self.decay ** (n - 1 - i) for i in range(n)]
        blended = weighted_average(self._vectors, weights)
        return normalize(blended)

    def debug_weights(self) -> list[tuple[int, float]]:
        """[(skill_id, decay_weight), ...] oldest → newest."""
        n = len(self.clicked_ids)
        return [
            (self.clicked_ids[i], self.decay ** (n - 1 - i))
            for i in range(n)
        ]
