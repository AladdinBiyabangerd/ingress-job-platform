# Ingress Job — Architecture

Job board (Ingress Job). Companies post jobs; candidates browse/apply. Hourly crawler aggregates remote/IT listings. No payments in this version.

## Stack

- Frontend: Next.js 15, React 19 (`frontend/`, port 3010)
- API: FastAPI / Uvicorn (`api/`, port 8010)
- Worker: Python crawler (`worker/`, hourly schedule)
- Auth: Ingress Academy OIDC (no separate password)
- DB: SQLite locally if `DATABASE_URL` empty; Postgres when set (API + worker share it)
- Locales: az / en / ru
- Deploy: Docker / Railway / Nixpacks per service

## Layout

```text
frontend/          # Next.js public site + cabinets
api/app/           # FastAPI (jobs, auth, companies, applications, admin)
worker/worker/     # Sources catalog, ATS boards, schedule, probe
scripts/           # dev.sh, per-service runners
docs/
compose.yaml
```

## Runtime

- All: `./scripts/dev.sh` → `[api]` `[web]` `[worker]`
- API: `http://127.0.0.1:8010`
- Web: `http://localhost:3010`
- Worker once: `./scripts/dev-worker.sh once`

## Domains

- Public job list / search / detail (guest: no original URL)
- Company jobs (moderation: pending → published)
- Candidate applications + CV upload
- Staff moderation (manual role): approve/reject/edit, crawled job tools
- Aggregation: remote/relocation IT sources (API/RSS/ATS); Jooble/Reed gated by API keys + monthly budgets
- CV parse queue (`parse_cv_queue` → rules `worker.cv_parse` + Tesseract OCR for scans/low-text PDFs → jobs-DB `candidate_profile` stub); accounts.sqlite `candidate_profiles` remains contact-only
- Consents (`consent` in jobs DB; `GET/PUT /api/v1/consents`); copy from `docs/cv-ai/consent-copy-v1.json`; visibility on `candidate_profile`
- CV profile review: `GET/PUT /api/v1/profile` + `/profile/review`; `profile_edit_log`; status draft→confirmed
- Role suggestions: `GET /api/v1/me/roles` (signature skill weights × years_factor; matching consent; BFF `/api/auth/me/roles`)

## Integrations

- Ingress Academy OIDC
- Job source APIs / RSS / ATS boards (`worker/worker/catalog.py`, `ats_boards.py`)
- Object storage for uploads (when configured)
- Optional `JOOBLE_API_KEY`, `REED_API_KEY`, `HH_API_KEY`

## Notes

- Prefer scoped reads: `frontend/app|components`, `api/app`, `worker/worker`
- Locales and guest vs logged-in link rules are product constraints — see README
- `.cursor/context/current-task.md` for active work
