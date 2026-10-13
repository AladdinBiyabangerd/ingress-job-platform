# Current task

## Completed
- Profile related-skills (hybrid + mix quotas)
- `app.skill_reco`: session vector (λ=0.7) + 60/25/15 hybrid recommender + demo
- Wired `skill_reco` into `/api/v1/skills/related` (profile-review BFF unchanged)

## Current state
- Primary path: DB catalog (`skill_reco.db_catalog`) → `UserSession` from profile excludes + focus → `HybridRecommender`
- Pair/role peers get popularity boosts so market edges beat name-hash noise
- Category compatibility still drops hub→frontend noise
- Legacy family/pair/role/category mix kept as fallback
- Sources in API items are now `exploit` / `adjacent` / `serendipity` (or legacy names on fallback)

## Decisions
- Synthetic embeddings: category one-hot + hashed name bigrams (no numpy / no pgvector skill rows yet)
- Adjacency from `_CATEGORY_COMPAT` (self excluded)
- BFF `/api/skills/related` stays a thin proxy — no frontend change needed

## Remaining work
- Commit when asked
- Later: real skill embeddings / ANN; persist click session in Redis if multi-step browse is productized

## Relevant files
- `api/app/skill_related.py` (reco wire + mix fallback)
- `api/app/skill_reco/db_catalog.py` (dictionary → SkillCatalog)
- `api/app/skill_reco/` (`catalog`, `session`, `engine`, `vectors`)
- `api/tests/test_skill_related.py`, `api/tests/test_skill_reco.py`
- `frontend/app/api/skills/related/route.js`, `frontend/components/profile-review.js`
