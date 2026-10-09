# Current task

## Completed
- Multi-provider `ai_gateway` chat fallback + NVIDIA embed defaults
- Chat model refresh #1: Gemini `gemini-3.8-flash`, OpenRouter gemma free
- Chat model refresh #2 (post-deploy logs):
  - NVIDIA → `nvidia/nemotron-3-super-120b-a12b` (`llama-3.3-70b-instruct` also EOL)
  - OpenRouter → `openrouter/free` (gemma `:free` upstream 429)

## Current state
- Code updated locally; needs commit/deploy
- Gemini 503 = capacity (model id OK); Groq 403/1010 = Cloudflare vs Railway IP; OpenAI 401 = bad key (remove or rotate)

## Remaining
- Deploy api + worker
- Clear Railway `NVIDIA_CHAT_MODEL` / `OPENROUTER_MODEL` overrides if set to old IDs
- Remove invalid `OPENAI_API_KEY` or replace; optional drop Groq from `AI_CHAT_PROVIDERS` if 1010 persists
- Smoke Rol koçu + matches

## Relevant files
- `api/app/ai_gateway/gateway.py`, `worker/worker/ai_gateway/gateway.py`
- `docs/railway.md`
