# Current task

## Completed
- Diagnosed recheck fail as `ai_budget_exceeded`; cascade confirmed working
- Removed retired `gemini-2.5-flash` / `gemini-2.5-flash-lite` from default cascade (404)

## Current state
- Gemini often 503 high demand → cooldown → Groq succeeds until TPM 429
- Default GEMINI_MODELS: 3.5-lite → 3.1-lite → 3.6 → 3-preview → 3.8

## Remaining work
- Commit/push when asked
- Ensure NVIDIA key on api so after Groq 429 cascade continues

## Relevant files
- `api/app/ai_gateway/gateway.py`, `worker/worker/ai_gateway/gateway.py`
