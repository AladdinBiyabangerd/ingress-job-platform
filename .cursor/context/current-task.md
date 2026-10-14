# Current task

## Completed
- Gemini multi-model + multi-key failover in `ai_gateway` (API + worker)
- Per-slot cooldown (`gemini:k0:model`); 404 long cooldown
- Optional `GEMINI_API_KEY_2` / `GEMINI_API_KEYS`; default model cascade
- Docs + tests updated

## Current state
- Single `GEMINI_API_KEY` alone works (all default text-out models for-loop)
- Second key optional; expands same cascade after key1

## Decisions
- Default models: 3.5-flash-lite → 3.1-flash-lite → 2.5-flash-lite → 2.5-flash → 3.6-flash → 3-flash-preview → 3.8-flash
- Skip 3.7 (routes to 3.8); skip Image/TTS/Live/Pro
- `GEMINI_MODELS` > `GEMINI_MODEL` > default list; key-major × model-minor

## Remaining work
- Deploy: set `GEMINI_API_KEY` (and optional `_2`); unset legacy `GEMINI_MODEL` if you want the full cascade
- Commit when asked

## Relevant files
- `api/app/ai_gateway/gateway.py`, `worker/worker/ai_gateway/gateway.py`
- `api/app/ai_flags.py`, `worker/worker/ai_flags.py`, `api/app/ops_status.py`
- `worker/tests/test_ai_gateway.py`, `worker/tests/test_gateway_cooldown.py`
- `.env.example`, `docs/railway.md`
