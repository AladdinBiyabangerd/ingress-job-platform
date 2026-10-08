# Current task

## Completed
- Hybrid 2 seçildi; detallı plan + inventar
- **Faza 0–1:** tokens, frosted Shell + primary-nav, PageChrome, CmdK, mobile nav parity
- **Faza 2 — Home Hybrid 2:** FeaturedJob + chips + full filter drawer + JobRow + pager + TrendAside/MatchAside
- **Faza 3 — Public:** job detail, companies, company page, trends / trend detail / trend jobs
- **Faza 4 — Candidate:** profile, profile-review, recommendations, insights, applications, saved, notifications, email-settings
- **Faza 5 — Employer/Admin:** company form, post/cabinet, talent, admin (5 tab)
- **Faza 6 — Responsive + purge:** breakpoints §8; drawer/CmdK/MobileNav focus-trap; ölü CSS/komponent purge; regression §9 code-verify

## Current state
- Hybrid 2 UI redesign **fazalar 0–6 bitdi**
- Manual smoke (auth flows, admin actions) istifadəçi tərəfindən təsdiq edilə bilər

## Decisions
- Breakpoints: ≥1100 main+320 side; 768–1099 side Featured altında 2-col; ≤767 hamburger + bottom-sheet + stacked JobRow + CmdK fullscreen
- Home layout: CSS grid areas `featured / side / list` (tablet-də side Featured-ın altında)
- `page-header.js` silindi; `job-card.js` yalnız `applicationsLabel`
- Silinən CSS: `.job-card*`, `.home-faq*`, `.hero` (köhnə), `.board`, köhnə `.filters` layout, `applications-page` wrap

## Remaining
- (opsional) Manual regression §9 auth/role flows əl ilə
- (opsional) digər köhnə CSS bloklarının əlavə purge (companies-hero və s. əgər qalıbsa)

## Recent polish
- Trend detail `Əsas məlumatlar`: notebook-style stacked facts → company-page-style metric strip (`.h2-trend-stats`); hər metrika `jobsHref`-ə klikləyə bilir

## Relevant files
- Plan: `/Users/mac/.cursor/plans/hybrid2_ui_redesign_47ec8e8d.plan.md`
- Inventar: `docs/redesign-inventory-checklist.md`
- `frontend/app/globals.css`
- `frontend/components/{home,job-row,shell,command-palette,job-card,featured-job}.js`
