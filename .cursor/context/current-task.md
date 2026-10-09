# Current task

## Completed
- Multi-provider `ai_gateway` (api + worker): chat fallback gemini→groq→nvidia→openrouter→openai; embed nvidia→openai
- `key_configured` accepts any provider key
- Embeddings default to NVIDIA `nemotron-3-embed-1b` (2048) when `NVIDIA_API_KEY` set; `AI_EMBEDDING_DIMS` override
- Docs: `docs/railway.md` variable list; frontend copy for no-key messages
- Tests: patch `_call_chat_json`; failover unit test

## Current state
- Code ready locally; needs deploy + Railway env vars on **api** and **worker**
- Rotate keys previously pasted in chat before setting on Railway

## Remaining
- Set Railway vars (see list below)
- If Postgres already has `embeddings` as `vector(1536)`, drop/recreate once for 2048
- Deploy api + worker; smoke Rol koçu + match embed

## Railway variables (api + worker)
```
GEMINI_API_KEY=
GROQ_API_KEY=
NVIDIA_API_KEY=
OPENROUTER_API_KEY=
AI_EMBEDDING_DIMS=2048
```
Optional: `OPENAI_API_KEY`, `AI_CHAT_PROVIDERS`, `AI_EMBED_PROVIDERS`, `GEMINI_MODEL`, `GROQ_MODEL`, `NVIDIA_CHAT_MODEL`, `NVIDIA_EMBED_MODEL`, `OPENROUTER_MODEL`

## Relevant files
- `api/app/ai_gateway/gateway.py`, `worker/worker/ai_gateway/gateway.py`
- `api/app/ai_flags.py`, `worker/worker/ai_flags.py`
- `api/app/embeddings.py`, `worker/worker/embeddings.py`
- `docs/railway.md`, `frontend/lib/copy.js`
