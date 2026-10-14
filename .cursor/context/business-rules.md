# Ingress Job — Business rules

## Market focus
- Primary market: **Azerbaijan** (candidates in AZ / open to AZ-reachable roles).

## Job-detail AI actions (Analiz / Müraciət mətni / Elana uyğun CV)
- Require **candidate login** (`job:candidate`); guests → OIDC.
- Require matching consent + CV profile with skills + **`status=confirmed`** (draft → confirm gate).
- Save job: login only (no confirmed-profile gate).

## Viewed jobs + original opens
- Opening a job detail while signed in records `viewed_jobs` (per user+job).
- Board list/detail show “Bu elana baxmısınız” when the current user has viewed it; filter `viewed=true` scopes the catalogue to those IDs (auth forwarded by BFF).
- Clicking **Orijinal elanı aç** / external apply (`GET /original` or external `POST /apply`) records `job_original_opens` **once per user+job** (UNIQUE); spam gir/çıx does not inflate the public `original_opens` count.
- On-site cabinet ads still expose `applications`; external/source ads expose `original_opens` when `has_original`.

## Location filter (board facets)
- Facets are **by country**, not by city (Germany / Japan / …).
- Resolve country from curated unambiguous city map first; never invent (Tokyo ≠ India).
- Conflicting scraped suffixes on known hubs are ignored; unknown cities may use `, Country` / US-CA region suffix.
- Ambiguous bare names (Cambridge, Birmingham, …) stay unresolved — omit over wrong country.
- Maps live in `api/app/place_data.py` (~1200 cities / ~100 countries); extend there when new hubs appear.

## Crawl source go/no-go (2026-10-10)
- Prefer ATS slug expansion over fragile HTML boards.
- **No crawl** without PoliteClient robots allow (Reed `/api/1.0/` is the only owner-approved exception).
- Remotive (`Disallow: /api/*`), Landing.jobs (`Disallow: /api/`), Ashby (`api.ashbyhq.com` robots HTTP 401), NoFluff/JustJoin (robots), DevIT/GermanTech JobsLight (signup HTML) → do not enable until robots/API is clean.
- Jobgether + RemoteYeah are enabled; The Muse deferred (US-heavy).
- **Jooble:** no-go for publish — API only returns search snippets; detail HTML blocked by robots. Snippet stubs rejected as `thin_description` (purge + finish_item).

## Crawl / scrape geo gate
- Collect foreign **remote** and **relocation** IT ads.
- **Reject** remote ads geo-locked to a foreign country or region (e.g. “Remote, Canada”, “US only”, “Remote - California”, “US based”, US clearance).
- **Reject** foreign onsite/hybrid office (e.g. Tel Aviv + `#LI-Hybrid`) with no remote/reloc/visa — before AI; mark `crawl_rejects`.
- **Reject** country-scoped remote (e.g. Germany-wide, US-based, Remote + Hamburg/Berlin).
- **Reject** named foreign city + “remote possible” / on-site·customer travel (e.g. Cincinnati hybrid) — not AZ-reachable remote.
- Title `(EMEA)` must **not** unlock `Remote (Germany|UK|…)`.
- `Remote EMEA; Sliema, Malta` (EMEA + concrete city) → reject.
- Title region pins `(AMER)`, `- NA`, Middle East, MENA, APAC, LATAM, `en Brasil` → reject unless place is worldwide/EMEA-open.
- Body geo pins when city empty: `Location: South Korea`, `based in Latin America`, Spanish `deben residir en Chile` / `Nacionalidad Chilena`, Chile labour calendar (`horario/feriados de Chile`), `CET ±Nh` remote band, India `Rs … per month` stipend → reject.
- Do **not** reject marketplace blurbs that only list many hire-from countries (e.g. Lemon.io).
- Geo-locked remote wins over noisy `relocation`/H-1B flags.
- Foreign **office/hybrid** keeps only with clear **international** visa/reloc (not domestic “relocation assistance”).
- Ignore compensation boilerplate (“For US-based employees…”, “401k (US only)”).
- Mojibake/garbage city strings → reject.
- Company blurb “organizations worldwide” does **not** open a US/CA-locked remote.
- ATS boards (`require_remote_or_relocation`): only remote or relocation.
- **Keep** true work-from-anywhere / remote-worldwide / EMEA / CIS / Azerbaijan-open remote.
- DB sweep: `python -m worker purge-market` (also runs at start of each crawl pass).
- **Keep** relocation (including to Canada/US/EU) — moving abroad is intentional.
- Implemented in `worker/worker/techstack.py` (`az_market_relevant`) and applied in `finish_item` (`worker/worker/runner.py`).

## Crawl market-fit AI
- **Default ON** when any AI provider key is set (standing rule; admin can hard-off).
- If keywords / source schema / board default do **not** clearly show remote, relocation, or visa → call AI.
- Provider order: gemini → groq → nvidia → openrouter → **openai last** (not parallel).
- Unsuitable → do not upsert; store URL in `crawl_rejects` so the next pass skips without AI.
- Flag: `market_fit` / `AI_MARKET_FIT_ENABLED=0` to hard-off.
- Module: `worker/worker/market_fit.py`.
- Confidence on accepted ads: clear rule signal → `rule_confidence=100`; AI path → `ai_confidence` 0–100 (+ `market_fit_reason`). Company/manual ads leave both NULL.

## Scraped ad moderation (2026-10-13)
- New scraped/crawled jobs are inserted as **`pending`**, not auto-published.
- They appear in staff **moderation queue** (with company pending ads) until approve/reject.
- Staff may approve one-by-one or bulk-select (`POST /api/v1/admin/jobs/approve-bulk`).
- Queue shows rule % and AI %; staff may threshold-publish **all** matching pending ads (`POST /api/v1/admin/jobs/approve-threshold`, no batch cap). AI recheck selects all matching ids in the UI and walks them in small HTTP batches (`POST /api/v1/admin/jobs/recheck-market-fit` with `ids`, ≤25/request) with a top progress bar (planned / done / left); stops early if AI budget/off returns only failures. Approve always means `published`. Checkbox bulk approve stays capped at 200.
- Legacy pending without scores: `POST /api/v1/admin/jobs/backfill-confidence` (UI: Köhnə faizləri doldur) — rule pass for clear signals, then up to 40 AI/call; click again until `still_unscored=0`.
- Re-scrape of an existing row does **not** force `published` (pending stays pending; already live stays live).
- Already-published scraped ads are left alone (no mass unpublish).
- Public board still only shows `status=published`.
