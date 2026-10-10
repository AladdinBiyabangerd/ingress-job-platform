# Ingress Job — Business rules

## Market focus
- Primary market: **Azerbaijan** (candidates in AZ / open to AZ-reachable roles).

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
