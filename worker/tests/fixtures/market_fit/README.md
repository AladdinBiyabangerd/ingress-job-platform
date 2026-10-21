# market_fit fixtures (real public text, not edited)

- `emerchantpay_senior_java.txt` — job text of ingress-job job 2530 as staff saw it
  (https://web-production-dba98.up.railway.app/jobs/2530, fetched 2026-10-21). Original:
  https://apply.workable.com/j/60A74216FB — Workable, location Sofia, Bulgaria, workplace=remote.
- `ij_2530_page.json` — same text with title/company/city as stored ("Remote").
- `jetbrains_qa_build_tools.txt` — JetBrains QA Automation Engineer (IntelliJ IDEA Java Build
  Tools) text as pasted by staff from the queue (no location in the text). Source posting:
  https://job-boards.eu.greenhouse.io/jetbrains/jobs/4777935101
- `greenhouse_jetbrains_4777935101.json` — same posting from the public Greenhouse board API
  (offices: Serbia, Germany, Cyprus, Spain, Czech Republic, Poland, Armenia).
- `workable_country_locked.json`, `workable_anywhere_locked.json`, `workable_worldwide_open.json`
  — unmodified rows from the public jobs.workable.com /api/v1/jobs search (robots.txt allows it).
- `eval_real_ads.json` — 62 real scraped ads (v9: + Typeform 1, Anthropic 1729) from the local ingress-job DB (2026-10-21 snapshot; text as
  stored), hand-labelled from the ad text only for `python -m worker eval-market-fit`. `expected`: eligible (85+),
  manual (relocation + visa route, 60–84), not_eligible / unclear / truncated (< 85). `flags` lists only the flags
  the label is sure about; `evidence` quotes the deciding sentence. Two entries re-use an ad with `prompt_limit`
  to force truncation. Two more entries (keys `synthetic-*`, company `SYNTHETIC EXAMPLE`) are hand-written,
  clearly marked, to cover conflicts the DB has no real example of (worldwide vs residents-only, visa vs
  no-sponsorship). `332#limit800` is a third cut variant. `scenario` marks the 8 review scenarios
  (see `worker/tests/test_market_fit_scenarios.py`).
