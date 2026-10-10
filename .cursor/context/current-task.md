# Current task

## Completed
- Production crawl market rules tightened from real DB samples
- Bugs fixed: EMEA-in-title unlock; reloc flag bypassing geo-lock; weak domestic reloc assistance
- `finish_item` + `purge-market` share the same rules

## Rule summary (crawl-time)
1. Geo-locked remote → drop (US/UK/DE/CA/India/city pins, Germany-wide, US-based, onsite-heavy)
2. Title EMEA does not unlock country-scoped remote place
3. Office abroad → keep only with international visa/reloc offer
4. Unclear → AI market_fit; reject URLs remembered

## Relevant files
- `worker/worker/techstack.py`
- `worker/worker/market_fit.py`, `market_purge.py`, `runner.py`
- `worker/tests/test_az_market.py`
