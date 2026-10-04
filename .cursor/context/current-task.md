# Current task

## Completed
- SEO / Google indexing, Heselo technical parity
- Visible job breadcrumbs + home FAQ/FAQPage
- Brand display name → Ingress Job
- Local `OPENAI_API_KEY=` clears shell export (tidy off)
- Google Jobs schema gaps #1–5 in `frontend/lib/seo.js`:
  1. `hiringOrganization.sameAs` removed (no company site in public payload)
  2. `TELECOMMUTE` only for fully remote; hybrid never gets it
  3. `employmentType` omitted (ofis/hibrid/uzaqdan ≠ employment type)
  4. Missing city/remote → country-level `jobLocation` (AZ)
  5. `validThrough` = `datePosted` + 30 days

## Remaining (medium / low)
6. Job description JSON-LD plain text → prefer HTML
7. Salary always `AZN` + `MONTH`
8. RU UI font: Plus Jakarta Sans without `cyrillic` subset
9. Shared home OG image only — no per-job OG
10. No `WebSite.potentialAction` SearchAction
11. Organization has no `sameAs` (social) — only if real profiles exist
12–14. City/category landings, GSC/Bing, footer `#faq` (out of scope / nice-to-have)

## Decisions
- TELECOMMUTE: `remote` or `job_type === "uzaqdan"`, never when `job_type === "hibrid"`
- Location fallback: `PostalAddress` with `addressCountry: "AZ"` when no city
- Job validity window: 30 days (`JOB_VALID_DAYS`)

## Relevant files
- `frontend/lib/seo.js` — JobPosting fixes (done #1–5)
- `frontend/app/layout.js` — font subsets (#8)
- `frontend/components/{job-detail,home}.js`
