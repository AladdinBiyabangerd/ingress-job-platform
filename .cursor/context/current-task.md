# Current task

## Completed
- SEO / Google indexing (commit 4a577a4)
- Auth refresh soft-logout (commit 8d3e41f)
- Heselo-parity technical SEO (committed this chat)

## SEO parity vs heselo-landing
Implemented technical SEO core (not heselo content/guides marketing layer):
- Rich meta: keywords, geo, authors, robots max-image-preview/snippet
- OG/Twitter `summary_large_image` + generated `/opengraph-image`
- Home JSON-LD `@graph`: Organization, WebSite, CollectionPage
- Job JSON-LD `@graph`: Organization, WebSite, WebPage, BreadcrumbList, JobPosting (+ salary/employment when available)
- `robots.txt` AI crawler allow-list + private path disallow
- `llms.txt`, web manifest, favicon, skip-link
- Apex canonical host (strip www)

## Remaining (optional, new chat)
- Visible job breadcrumb UI (JSON-LD already present)
- Home FAQ section + FAQPage schema (heselo-style content, adapted for jobs)

## Not ported (heselo-specific)
- FAQ/guides/solutions content SEO
- Founder Person schema / social sameAs
- Pricing/OfferCatalog schemas

## Relevant files
- `frontend/lib/seo.js`
- `frontend/app/{layout,robots,manifest,opengraph-image}.js`
- `frontend/app/{page,en/page,ru/page}.js`
- `frontend/components/{job-detail,json-ld,shell}.js`
- `frontend/public/{llms.txt,favicon.svg}`
