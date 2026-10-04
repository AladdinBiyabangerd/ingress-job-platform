# Current task

## Completed
- SEO / Google indexing (commit 4a577a4)
- Auth refresh soft-logout (commit 8d3e41f)
- Heselo-parity technical SEO (committed prior chat)
- Visible job breadcrumb UI (this chat)
- Home FAQ section + FAQPage schema, az/en/ru (this chat)

## SEO parity vs heselo-landing
Implemented technical SEO core (not heselo content/guides marketing layer):
- Rich meta: keywords, geo, authors, robots max-image-preview/snippet
- OG/Twitter `summary_large_image` + generated `/opengraph-image`
- Home JSON-LD `@graph`: Organization, WebSite, CollectionPage, FAQPage
- Job JSON-LD `@graph`: Organization, WebSite, WebPage, BreadcrumbList, JobPosting (+ salary/employment when available)
- Visible job breadcrumbs + home FAQ UI (heselo-style, jobs-adapted)
- `robots.txt` AI crawler allow-list + private path disallow
- `llms.txt`, web manifest, favicon, skip-link
- Apex canonical host (strip www)

## Remaining (optional)
- Founder Person schema / social sameAs (if desired)
- Pricing/OfferCatalog schemas (N/A unless monetized)
- Guides/solutions content SEO (heselo-specific; not ported)

## Relevant files
- `frontend/lib/{seo,copy}.js`
- `frontend/app/{layout,robots,manifest,opengraph-image,globals}.css|js`
- `frontend/app/{page,en/page,ru/page}.js`
- `frontend/components/{job-detail,home,json-ld,shell}.js`
- `frontend/public/{llms.txt,favicon.svg}`
