# Current task

## Completed
- Multi-provider `ai_gateway` (api + worker): chat fallback gemini→groq→nvidia→openrouter→openai; embed nvidia→openai
- Default chat models refreshed after provider EOL/404s (2026-10):
  - Gemini `gemini-3.8-flash` (was `gemini-2.5-flash`)
  - NVIDIA chat `meta/llama-3.3-70b-instruct` (was `llama-3.1-8b-instruct` EOL)
  - OpenRouter `google/gemma-4-26b-a4b-it:free` (was `llama-3.3-70b-instruct:free`)
- Embeddings default NVIDIA `nemotron-3-embed-1b` (2048); docs + tests

## Current state
- Code defaults fixed locally; **redeploy api + worker**
- If Railway sets `GEMINI_MODEL` / `NVIDIA_CHAT_MODEL` / `OPENROUTER_MODEL` to old IDs, clear or update those vars
- Still need valid keys: OpenAI 401 = bad key; Groq 403/1010 = Cloudflare often blocks datacenter IPs (not a model id fix)

## Remaining
- Deploy api + worker with new defaults
- Clear stale model env overrides on Railway if any
- Fix/rotate `OPENAI_API_KEY` if used; treat Groq as optional if Railway IP stays blocked
- Smoke Rol koçu + matches after deploy

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
- `docs/railway.md`
