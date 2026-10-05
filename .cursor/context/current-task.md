# Current task

## Completed
- Phase 0–2.12 (matches, trends, digests, skill pairs, etc.) — see prior notes
- Profile review UX: CV upload on `/profile/review` + manual fill + redesign
- Profile review **Sıfırla** button: `DELETE /api/v1/profile` + BFF; clears profile + open parse jobs; returns to chooser

## Decisions
- `POST /api/v1/profile/cv` stores CV (same PDF/DOC/DOCX ≤5MB rules) and enqueues `parse_cv_queue` without an application
- Frontend BFF: `POST /api/auth/cv-profile/cv`
- Empty profile shows chooser (upload vs manual); parsed/manual form always editable
- UI polls profile while parse is pending/processing
- Reset confirms, then deletes `candidate_profile` and fails open `parse_cv_queue` rows

## Remaining
- AI #2 re-rank when Postgres + pgvector available
- Academy `academy_course_ids` map
- Ops SPF/DKIM; consolidate worker+API `ai_gateway`

## Relevant files
- `api/app/routers/profile.py`, `api/app/cv_profile.py`, `api/app/applications.py`
- `frontend/components/profile-review.js`, `frontend/lib/copy.js`, `frontend/app/globals.css`
- `frontend/app/api/auth/cv-profile/route.js`, `frontend/app/api/auth/cv-profile/cv/route.js`
- `api/tests/test_cv_profile.py`

## Continue prompt (new chat)
Profile review reset done. Next: Academy skill↔course map or AI #2 blockers. Read `.cursor/context/current-task.md`.
