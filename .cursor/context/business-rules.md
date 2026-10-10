# Ingress Job — Business rules

## Market focus
- Primary market: **Azerbaijan** (candidates in AZ / open to AZ-reachable roles).

## Crawl / scrape geo gate
- Collect foreign **remote** and **relocation** IT ads.
- **Reject** remote ads geo-locked to a foreign country or region (e.g. “Remote, Canada”, “US only”, “Remote - California”, “US based”, US clearance).
- **Reject** foreign onsite/hybrid office (e.g. Tel Aviv + `#LI-Hybrid`) with no remote/reloc/visa — before AI; mark `crawl_rejects`.
- **Reject** country-scoped remote (e.g. Germany-wide, US-based, Remote + Hamburg/Berlin).
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
