"""Dynamic balanced skill recommendations (session vector + 60/25/15 mix).

Public API
----------
- ``SkillCatalog`` — skill rows + embeddings
- ``UserSession`` — time-decay session vector
- ``HybridRecommender.get_recommendations`` — exploitation / adjacent / serendipity
- ``catalog_from_conn`` — production dictionary loader (profile-review)

Run the walkthrough::

    cd api && .venv/bin/python -m app.skill_reco
"""

from app.skill_reco.catalog import Skill, SkillCatalog
from app.skill_reco.db_catalog import catalog_from_conn, clear_catalog_memo
from app.skill_reco.engine import HybridRecommender, Recommendation
from app.skill_reco.session import UserSession
from app.skill_reco.vectors import cosine_similarity, normalize

__all__ = [
    "HybridRecommender",
    "Recommendation",
    "Skill",
    "SkillCatalog",
    "UserSession",
    "catalog_from_conn",
    "clear_catalog_memo",
    "cosine_similarity",
    "normalize",
]
