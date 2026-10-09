# Current task

## Completed
- Multi-provider `ai_gateway` chat fallback + NVIDIA embed defaults
- Chat model refresh (Gemini / NVIDIA / OpenRouter)
- Request-path AI async (cache-only + `ai_warm` + UI poll)
- Role coach `role-coach-v4`: per-role + share/growth in prompt; same-day refresh = cache hit

## Current state
- Cache hit → instant coach; miss → warm once; sticky fail cooldown ~90s
- Daily trend update may regenerate once; page refresh does not

## Remaining
- Deploy api + frontend
- Optional: drop Groq from `AI_CHAT_PROVIDERS` if 1010 persists; fix OpenAI key
- Smoke: recommendations loads instantly; coach fills after warm (or soft-fails without freeze)

## Relevant files
- `api/app/ai_gateway/gateway.py`, `api/app/ai_warm.py`
- `api/app/skill_gap.py`, `api/app/matching.py`, `api/app/role_coach.py`
- `api/app/match_why.py`, `api/app/match_llm_rerank.py`
- `frontend/components/recommendations.js`, `frontend/lib/server/recommendations.js`
