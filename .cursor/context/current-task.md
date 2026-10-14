# Current task

## Completed
- Gemini multi-model + multi-key failover (pushed `9bd4f24`)
- NVIDIA Free Endpoint chat model cascade (same for-loop pattern)

## Current state
- NVIDIA expands to: lightning → gpt-oss-20b → gemma-4-31b-it → glm-5.3 → nemotron-3-super
- Per-model cooldown `nvidia:{model}`; embed stays `nemotron-3-embed-1b`
- Override: `NVIDIA_MODELS` > `NVIDIA_CHAT_MODEL` > default list

## Decisions
- Skip vision/omni/TTS; no thinking/reasoning_budget extras on NVIDIA calls
- One `NVIDIA_API_KEY` covers all Free Endpoint models

## Remaining work
- Commit/push when asked
- Deploy: unset legacy `NVIDIA_CHAT_MODEL` if full cascade wanted

## Relevant files
- `api/app/ai_gateway/gateway.py`, `worker/worker/ai_gateway/gateway.py`
- `worker/tests/test_ai_gateway.py`, `worker/tests/test_gateway_cooldown.py`
- `.env.example`, `docs/railway.md`
