# Current task

## Completed
- Profile related-skills + `app.skill_reco` wired into `/api/v1/skills/related`
- Quality+speed refine: mini-catalog prune, graded pair/role/family boosts, adjacent≠serendipity, token name features

## Current state
- Reco path builds ~100-candidate mini-catalog (family/pair/role/category/adjacent) then runs HybridRecommender
- Pair/role strengths graded; family nudge ~0.85
- Engine drops low-sim adjacent instead of dumping into serendipity
- Legacy mix remains fallback

## Decisions
- Speed via candidate prune (not ANN yet)
- Synthetic embeddings stay (category + bigram/token hashes)

## Remaining work
- Commit/push when asked
- Later: real embeddings / ANN; Redis click session

## Relevant files
- `api/app/skill_related.py`
- `api/app/skill_reco/engine.py`
- `api/app/skill_reco/db_catalog.py`
- `api/tests/test_skill_related.py`
