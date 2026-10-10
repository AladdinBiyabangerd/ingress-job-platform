# Current task

## Completed (this / prior chats)
- Design skill + Home checkup / smell
- `/design interaction` (Home)
- `/design tokenize` (Home-touched + outside Home brand hex)
- `/design deslop` (featured / filters)
- `/design smell` re-score: **10/10 · CLEAN**
- `/design finish` Home primary flow (browse → filter → open job)
- `/design review` Home — **7/10 · STRONG** (audit only; `.design/review-report.{md,html}`)
- Reference ingest → `.design/reference.md` (Stripe DESIGN.md + Primer/GitHub + relocate.me / relocue live + review P0–P2). No frontend changes. Keep `#001fff`.
- `/design relayout` Home against P0 + reference — **done**
- `/design typeset` Home open-roles head (P1) + job-row open track (P2) — **done**

## Current state
P1: `.open-roles-head h2` **18px** / count **13px** → ratio **1.385** (≥1.3). Semibold + heading LH; count `tabular-nums`.
P2: `.job-row` / mobile / `.job-row-no-company` open column track **44px** (was 28px); control still 44×44.
Measured (CDP): 390 / 700 / 1280 — ratio 1.385; last track 44; open 44×44.
Committed: design skill + rule + Home frontend + `.gitignore` (`.design/` ignored). README parked-surfaces note left unstaged.

## Plan (do in separate chats — one major step each)

| # | Chat prompt | Mode | Changes source? |
|---|---|---|---|
| 1 | `/design tokenize` outside Home | tokenize | yes — **done** |
| 2 | `/design finish` Home primary flow | finish | yes — **done** |
| 3 | `/design review` Home (after finish) | review | no — **done** |
| 4 | `/design relayout` Home (P0 + `.design/reference.md`) | relayout | yes — **done** |
| 5 | Optional: `/design typeset` Home open-roles head (P1 ≥1.3) | typeset | yes — **done** |
| 6 | Optional: job-row open track ≥44px (P2) | finish/craft | yes — **done** |
| 7 | Commit when asked (skill + rule + frontend; exclude `.design/`) | git | — | **done** |

## Decisions (keep)
- Brand hue `#001fff` / deep / soft stay
- Featured: flat `--brand-soft` + company initial
- Filters chip icon stays; drawer noun icons out
- Home = surface / catalogue + featured lead
- Empty filter results: show `t.clear` when `activeFilters > 0`
- Filter chip row: `overflow: hidden` on toolbar (not one-axis clip)
- Review: primary flow browse → filter → open job
- Relayout: stacked order `featured` → `list` → `side`; sticky side only ≥1100px
- Reference: Stripe craft (not purple); Primer focus-over-features; relocate filter-above-list; Relocue glance-before-essay
- Typeset: open-roles section title 18px / count 13px (ratio ~1.385); no new font family
- Craft: job-row open grid track = 44px to match control

## Relevant files
- `frontend/app/globals.css` — `.open-roles-head h2` / `.open-roles-count`; `.job-row` tracks
- `frontend/components/home.js` — open-roles head markup (unchanged)
- `.design/reference.md`, `.design/review-report.md` — backlog (P0–P2 cleared in UI)
- Dev server often on `:3010`
