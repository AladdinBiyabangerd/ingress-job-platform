# Current task

## Goal
AI #2 re-rank MVP: pgvector embeddings, job/profile embed pipeline, matches 0.7/0.3 blend, top-5 LLM “niyə”, SQLite/off → structured-only.

## Completed
- Prior latency work (list DTO, home search, ISR, middleware `/me`, AccountBar dedupe)
- **A Infra**: `compose.yaml` → `pgvector/pgvector:pg16`; `api/app/embeddings.py` + `worker/worker/embeddings.py`; `ai_gateway.embed()` (API+worker); `_NO_ID_TABLES` includes `embeddings`
- **B Pipeline**: worker hourly `embed_stale_jobs`; profile embed on `save_profile` + CV parse; schema ensure in `cabinet_store`
- **C Blend**: `matching.matches_payload` top-50 pool → cosine blend when Postgres+vectors; `ai_rerank` true/false
- **D Why**: `api/app/match_why.py` top-5 soft-fail LLM sentence via `complete_json`
- **E Privacy/tests**: `DELETE /me` clears profile embeddings; `api/tests/test_embeddings_rerank.py`

## Decisions
- Model: `text-embedding-3-small` (`AI_EMBEDDING_MODEL`); dims 1536
- Flags: `AI_RERANK_ENABLED`, `AI_MATCH_WHY_ENABLED` (default follow gateway; `0` forces off)
- Embed text: PII-free (title/skills/work titles — no contact)
- SQLite / missing extension: no-op, matches unchanged
- Railway needs pgvector-capable Postgres (`CREATE EXTENSION vector`)
- **Deploy: user will do ops themselves** (CLI login blocked in agent)

## Remaining (user ops)
1. Commit + push AI #2 changes (still uncommitted on `main` as of last check)
2. Railway Postgres: `CREATE EXTENSION IF NOT EXISTS vector;` (needs pgvector-capable image)
3. Redeploy API + worker; ensure `OPENAI_API_KEY` set; optional `AI_RERANK_ENABLED` / `AI_MATCH_WHY_ENABLED`
4. Spot-check `GET /api/v1/me/matches` → `ai_rerank: true` (after embeds exist)
5. Backlog: SPF/DKIM; HR talent search (AI #3) later

## Relevant files
- `api/app/embeddings.py`, `api/app/matching.py`, `api/app/match_why.py`, `api/app/ai_gateway/gateway.py`
- `api/app/cv_profile.py`, `api/app/me_data.py`, `api/app/cabinet_store.py`
- `worker/worker/embeddings.py`, `worker/worker/ai_gateway/gateway.py`, `worker/worker/runner.py`, `worker/worker/cv_queue.py`
- `compose.yaml`, `api/tests/test_embeddings_rerank.py`, `docs/railway.md`
