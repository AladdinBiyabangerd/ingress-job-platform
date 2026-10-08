# Ingress Job — redesign planning inventory

Concrete surface checklist from current frontend (`frontend/components`, `frontend/lib`). Use when redesigning shell/tokens so behavior is preserved.

---

## 1. `Home` (`components/home.js`)

### Constants / helpers
| Name | Role |
|------|------|
| `PAGE_SIZE` | `20` |
| `TEXT_DEBOUNCE_MS` | `300` (company + salary text inputs) |
| `EMPTY_FACETS` | `{ languages: [], categories: [], stacks: [] }` |
| `FilterIcon({ name })` | Icons: `filter`, `sort`, `date`, `language`, `company`, `city`, `salary`, `relocation`, `category`, `stack`, `remote` (+ default pin) |
| `GroupLabel({ icon, children })` | Label + icon wrapper |
| `toggle(list, setList, value)` | Multi-select checkbox helper |
| `clear()` | Reset all filters + page → 1 |
| `applyFilters()` | Close drawer; scroll results into view if needed |
| `goToPage(next)` | Clamp page; smooth scroll top |

### Props (SSR from `app/{,en/,ru/}page.js` → `loadHomeJobs()`)
- `locale`, `jobs`, `total`, `pages`, `facets`, `error`

### State variables
| State | Default | Notes |
|-------|---------|--------|
| `company` | `""` | Search input; debounced |
| `languages` | `[]` | Multi checkbox from facets |
| `remote` | `false` | Checkbox |
| `relocation` | `false` | Checkbox |
| `stacks` | `[]` | Multi from facets (tech) |
| `categories` | `[]` | Multi from facets |
| `techQuery` | `""` | Client-only filter of stack facet list (not sent to API) |
| `when` | `"any"` | `any` \| `today` \| `week` |
| `sort` | `"newest"` | `newest` \| `oldest` \| `title` |
| `salaryMin` / `salaryMax` | `""` | Number inputs; debounced |
| `page` | `1` | |
| `items` | SSR `jobs` | |
| `resultTotal` / `resultPages` | SSR | |
| `facetData` | SSR facets | Updated from BFF |
| `loadError` | SSR `error` | |
| `loading` | `false` | Disables pager while fetch |
| `filtersOpen` | `false` | Mobile drawer |
| `compact` | `useMediaQuery("(max-width: 900px)")` | |
| `drawerOpen` | `compact && filtersOpen` | |

### Derived
- `filterKey` — JSON of filter fields (excludes `page`, `techQuery`)
- `languageOptions`, `categoryOptions` (sorted by `CATEGORY_ORDER`), `techOptions` (filtered by `techQuery`)
- `activeFilters` — count badge (langs + cats + stacks + remote + relocation + company + when≠any + salary bounds)
- `currentPage` — `min(page, resultPages)`

### Filter controls (UI)
1. **Mobile toggle** — `.filters-toggle` → opens drawer; badge `filters-badge` + visually-hidden `t.filtersActive`
2. **Sort** `<select>` — `newest` / `oldest` / `title` (`t.newest`, `t.oldest`, `t.byTitle`)
3. **When** `<select>` — `any` / `today` / `week`
4. **Language** fieldset — checkboxes from `facetData.languages[].code` → `languageLabel(locale, code)`
5. **Company** `<input type="search">` — placeholder `t.companyPlaceholder`
6. **Remote** checkbox — `t.remoteFilter`
7. **Relocation** checkbox — `t.relocationFilter`
8. **Category** fieldset (if options) — name + `check-count`; label via `categoryLabel`
9. **Tech stack** — search `techQuery` + checkboxes `stacks` with counts
10. **Salary** — `salaryMin` / `salaryMax` + `t.salaryNote`
11. **Clear** — desktop: `text-btn` in filter head; drawer: `t.filtersClear` in `.filter-actions`
12. **Apply** (drawer only) — `t.filtersApply` + live `(t.count(resultTotal))`

**Not present in UI (but `FilterIcon` has `city`):** no city filter control. FAQ copy still mentions city/source filters — copy vs product mismatch to resolve in redesign.

### API / BFF
| Call | When |
|------|------|
| SSR `loadHomeJobs()` → `getJobs("{}")` → FastAPI jobs | Initial HTML |
| Client `GET /api/jobs?${jobsListParams(...)}` | Filter/page change; also if SSR empty/error |

`jobsListParams` (`lib/jobs-params.js`) query keys: `page`, `per_page`, `company`, `remote`, `relocation`, `when`, `sort`, `language` (repeat), `category` (repeat), `stack` (repeat), `salary_min`, `salary_max`. (`q` supported by helper but Home does not expose title search.)

Response used: `items`, `total`, `pages`, `facets`.

Debounce: only when `company|salaryMin|salaryMax` text key changes. Filter change resets to page 1 before fetch. AbortController on cleanup.

### Pagination
- Shown if `resultTotal > PAGE_SIZE`
- Prev / status `t.pageOf` / Next; disabled when loading or at ends
- `goToPage` → scroll to top

### Mobile filter dialog
- Breakpoint: `max-width: 900px` → panel becomes dialog
- Open: toggle sets `filtersOpen`; `role="dialog"`, `aria-modal`, `aria-labelledby="job-filters-title"`, `aria-controls="job-filters"`
- Close: X (`filter-close`), backdrop click, Escape, leaving compact mode
- Focus: `lockBodyScroll()`, focus close on open, `trapTab` on panel, restore focus to toggle on close
- Drawer footer: Clear + Apply (desktop uses live filter + Clear in head only)

### Results / shell
- Wrapped in `Shell` `mode="browse"`
- `loadError` → `t.loadError`; empty → `t.empty`
- Each row: `JobCard`

### FAQ (`#faq`, `.home-faq`)
From `t.faq` in `lib/copy.js` (az/en/ru). Structure:
- eyebrow, title
- 9 `<details>` items; **first open by default**

Topics (EN): What is Ingress Job; Ingress relation; browsing free; search/filter; account to apply; how to post; remote jobs; where listings from; which languages.

---

## 2. `JobCard` (`components/job-card.js`)

### Exports
- `applicationsLabel(t, job, { short })` — onsite + numeric `applications` only; else `null`
- `JobCard({ locale, job, showCompany = true, showSave = true })`

### Displayed fields
| Field / UI | Source |
|------------|--------|
| Company link or text | `job.company` / `t.noCompany`; link if `job.company_slug` → `hrefFor({ companySlug })` |
| Source pill | `job.source_name` |
| Title link | `job.title` → `hrefFor({ jobId })` (`.job-card-link` covers card intent) |
| Category tag | `job.category` → `categoryLabel` |
| Tech chips | `job.tech_stack` (max 6 + `+N` more) |
| Place | remote → `t.placeRemote` else `job.city` \|\| `t.noCity` |
| Relocation fact | if `job.relocation` → `t.relocationBadge` |
| Posted date | `calendarDate(job.created_at)` in `<time>` |
| Applications fact | `applicationsLabel(..., { short: true })` — `t.applicationsCount` / `t.applicationsFirst` |
| Open hint | `t.openRole` (decorative) |

### Actions
| Action | Component / behavior |
|--------|----------------------|
| Open job | Title `<a>` |
| Open company | Company `<a>` (not nested in title link) |
| Save / unsave | `SaveJobButton` when `showSave` (default true) |

Internal `Icon` names: `date`, `relocation`, `applications`, default city.

---

## 3. `AccountBar` (`components/account-bar.js`)

### State / effects
- `me` from `useInitialMe()` or `fetchMe()` (`GET /api/auth/me?lang=…`)
- `ssoError` if `?sso_error` in URL
- `open` menu; outside pointerdown + Escape close
- `onMe?.(me)` callback

### Display identity
- Role label: staff / employer / candidate (`t.roleStaff` etc.)
- `displayName` = candidate `display_name` → Academy `name` → email → role → `t.accountSignedIn`
- `identityHint` = email or role if different from displayName

### Guest branch (`me` loaded, `!authenticated`)
- Renders `RegisterChoice` only (no bell)

### Loading (`me` null)
- Renders nothing in bar body (no flash of guest)

### Authenticated branch
1. **`NotificationsBell`** — `initialUnread={me.unread_notifications}`
2. **Menu trigger** — avatar SVG + name + optional role/email + chevron
3. **Dropdown head** — name + hint

#### Menu items (role gates)
| Item | Gate | Target |
|------|------|--------|
| `t.profileOpen` | `employer \|\| candidate \|\| staff` | `mode: "profile"` |
| `t.profileReviewOpen` | `candidate \|\| staff` | `mode: "profileReview"` |
| `t.recommendationsOpen` | `candidate \|\| staff` | `mode: "recommendations"` |
| `t.insightsOpen` | `candidate \|\| staff` | `mode: "insights"` |
| `t.emailSettingsOpen` | `candidate \|\| staff` | `mode: "emailSettings"` |
| `t.myApplications` | `candidate \|\| staff` | `mode: "applications"` |
| `t.savedJobs` | any authenticated | `mode: "saved"` |
| `t.talentTitle` | `employer \|\| staff` | `mode: "talent"` |
| `t.admin` | `staff` | `mode: "admin"` |
| Employer upgrade block | `candidate && !employer && !staff` | `loginHref({ intent: "job_employer", returnTo: post })` |
| Register ask block | authenticated but no candidate/employer/staff | employer + candidate login intents |
| Sign out | always when auth | `POST /api/auth/logout?returnTo=…` + `clearMeCache` |

### Related: `RegisterChoice`
- Toggle `t.register` → employer (`job_employer` → post) + candidate (`job_candidate` → `returnTo`)

### Related: `Shell` / `MobileNav` parity
Hybrid 2: MobileNav **unifies** with AccountBar — includes `profileReview` + `admin` (staff). Hamburger ≤767.

---

## 4. Server actions & fetches by major surface

Legend: **SA** = `"use server"` in `lib/server/refresh.js` (calls FastAPI with bearer). **BFF** = same-origin `/api/auth/...` or `/api/jobs`.

### Shared session
| File | Call |
|------|------|
| `lib/me-client.js` `fetchMe` | BFF `GET /api/auth/me?lang=` |
| `account-bar` / `shell` | BFF `POST /api/auth/logout?returnTo=` |

### Profile — `ProfileForm`
| Call | Kind |
|------|------|
| `fetchMe` | BFF |
| `GET /api/auth/consents?lang=` | BFF |
| `saveCompanyProfile` | SA → `POST /api/v1/company-profile` |
| `POST /api/auth/profile` (display_name, phone, email) | BFF |
| `saveConsents` | SA → `PUT /api/v1/consents?lang=` |
| `exportMyData` | SA → `GET /api/v1/me/export` |
| `DELETE /api/auth/me` | BFF (delete my data) |

Branches: company form if `employer\|\|staff`; applicant + privacy if `candidate\|\|staff`; guest → `RegisterChoice`.

### Profile review (CV) — `ProfileReview`
| Call | Kind |
|------|------|
| `loadCvProfile` | SA → `GET /api/v1/profile` |
| `loadRoles` / `loadRolesFromApi` | SA → `GET /api/v1/me/roles?lang=` |
| `saveCvProfile` | SA → `PUT /api/v1/profile` |
| `uploadCvProfile` | SA → `POST /api/v1/profile/cv` (multipart) |
| `cancelCvParse` | SA → `POST /api/v1/profile/cv/cancel` |
| `deleteCvProfile` | SA → `DELETE /api/v1/profile` |

### Recommendations — `Recommendations`
| Call | Kind |
|------|------|
| `GET /api/auth/me/roles?lang=` | BFF |
| `loadSkillGap(lang, role)` | SA → `GET /api/v1/me/skill-gap?…` |
| `GET /api/auth/me/matches?lang=&limit=10&role=` | BFF |
| `POST /api/auth/me/matches/{jobId}/feedback` `{ vote, reason }` | BFF |

UI: role picker, match list (`MatchJob`: score, title, meta, explanation, have/missing skills, up/down, reason select), skill-gap bits, client pager.

### Insights — `Insights`
| Call | Kind |
|------|------|
| `GET /api/auth/me/insights?lang=` | BFF |

Sections: `CoachSection`, `NearMissSection`, `GrowthSection` (coach / near_misses / academy_courses / roadmap); consent hint if `matching_consent === false`.

### Notifications — `NotificationsPage` + `NotificationsBell`
| Call | Kind |
|------|------|
| Bell: `GET /api/auth/notifications` (if unread not seeded) | BFF |
| `refreshNotifications` | SA → `GET /api/v1/notifications` |
| `markNotificationRead` | SA → `POST /api/v1/notifications/{id}/read` |
| `markAllNotificationsRead` | SA → `POST /api/v1/notifications/read` |

### Email settings — `EmailSettings` (+ `lib/web-push.js`)
| Call | Kind |
|------|------|
| `GET /api/auth/email-prefs` | BFF |
| `saveEmailPrefs` | SA → `PUT /api/v1/email-prefs` |
| `enableBrowserPush` / `disableBrowserPush` | BFF `GET /api/auth/me/push-vapid-key`, `POST`/`DELETE /api/auth/me/push-subscription` |

Fields: `frequency`, `digest`, `high_match`, `match_near`, `profile_nudge`, `coach_weekly`, `push_enabled`, `language`, `send_weekday`.

### Post / cabinet — `PostPage` → `Cabinet` (+ `CompanyForm` gate)
| Call | Kind |
|------|------|
| `refreshCabinet` | SA → `GET /api/v1/cabinet/jobs` + applications |
| `cabinetSaveJob` | SA → `POST/PATCH /api/v1/cabinet/jobs[/{id}]` |
| `cabinetCloseJob` | SA → `POST …/close` |
| Owner apps: `ApplicationList` `mode="owner"` → `patchApplicationStatus("owner", …)` | SA → `PATCH /api/v1/cabinet/applications/{id}` |
| CV download link | BFF `GET /api/auth/applications/{id}/cv` |
| `CompanyForm`: `saveCompanyProfile` | SA |

`PostPage` gates: guest → register; candidate-only → deny + upgrade; `needs_company_profile` → redirect company; else `Cabinet`.

### Admin — `AdminPage` → `Admin` / `CollectedAdmin` / `ManualAd` / `AdminAiFlags`
| Call | Kind |
|------|------|
| `refreshAdminQueue` | SA admin jobs + applications |
| `refreshAdminApplications` | SA |
| `fetchAdminJob` | SA |
| `adminPatchJob` / `adminRejectJob` / `adminActJob` (approve\|close) | SA |
| `createManualAd` (`ManualAd`) | SA → `POST /api/v1/admin/jobs` |
| `refreshCrawled` / `fetchCrawledJob` / `crawledPatchJob` / `crawledVisibility` / `crawledMerge` | SA |
| `saveAdminAiFlags` + `GET /api/auth/admin/ai-flags` | SA + BFF |
| Staff apps: `ApplicationList` `mode="staff"` → `patchApplicationStatus("staff", …)` | SA |

### Talent — `TalentSearch`
| Call | Kind |
|------|------|
| `GET /api/auth/talent?page=&per_page=&q=` | BFF |

Gates: `guest` / `role` / `company` (`needs_company_profile`). Card fields: visibility, display_name, headline, seniority, years, city/country, skills.

### Applications — `MyApplications` + job-detail `AccountActions`
| Call | Kind |
|------|------|
| `refreshMyApplications` | SA → `GET /api/v1/applications` |
| `withdrawApplication` | SA → `DELETE /api/v1/applications/{id}` |
| Detail: `GET /api/auth/applications` | BFF |
| Detail: `applyToJob` | SA → `POST /api/v1/jobs/{id}/apply` |
| Detail: `GET /api/auth/jobs/{id}/apply` or `…/original` | BFF (redirect URL) |
| Detail: consents fetch + `saveConsents` after apply | BFF + SA |

### Saved — `MySaved` + `SaveJobButton`
| Call | Kind |
|------|------|
| `GET /api/auth/saved-jobs/ids` | BFF (button cache) |
| `saveJob` / `unsaveJob` | SA → `POST`/`DELETE /api/v1/me/saved-jobs/{id}` |
| `refreshSavedJobs` | SA → `GET /api/v1/me/saved-jobs?page&per_page` |

---

## 5. Guest vs logged-in — must preserve (home + job detail)

### Home (`Home`)
| Behavior | Guest | Logged-in |
|----------|-------|-----------|
| Browse / filters / FAQ | Same (public) | Same |
| `Shell` nav tabs | browse, companies, trends | + `post` if employer/staff; + `admin` if staff (`navTabs`) |
| Account chrome | `RegisterChoice` | Bell + account menu |
| Save on cards (`SaveJobButton`) | Visible; click → `loginHref({ returnTo: job })` | Toggle save/unsave via SA |
| Saved IDs preload | No `/saved-jobs/ids` until authenticated | `ensureIds()` when `me.authenticated` |

Home itself does **not** branch content on auth; differences come from `Shell` / `AccountBar` / `SaveJobButton`.

### Job detail (`JobDetail` + `AccountActions` + `SaveJobButton`)
| Behavior | Guest | Logged-in |
|----------|-------|-----------|
| Public: breadcrumbs, title, company, place, job_type, salary, relocation, description (`Description`/`Linked`), facts aside, tech stack, applications count (onsite), JSON-LD | Yes | Yes |
| Save star | Login redirect | Toggle |
| **Offsite** (`!onsite`) Apply / Original buttons | `openLink` → 401/403 → login (`job_candidate`); else redirect to URL; failure shows `t.locked` | Same but may get URL |
| **Onsite** apply form | Form still rendered; submit → 401/403 → login | Full form + consents if CV enabled; success status; duplicate 409 |
| Existing application status | Loaded only if applications API ok (guest usually empty) | Status note + withdraw list via `ApplicationList` |
| Original button after applied | If `hasOriginal` | Same |
| Locked message | `t.locked` when link open fails without URL | Same |

### Apply form fields (onsite, from `applyFormFromJob(job.form)`)
Conditional: message, phone, email, questions[], CV file, `ConsentFields` (matching / emails / recruiter_visibility) when CV enabled.

### Shell-level (affects both pages)
- Locale switcher always
- Mobile hamburger: guest register links vs full account list
- Brand / browse / companies / trends always; post/admin role-gated

---

## Quick reference — `refresh.js` exported actions

`refreshAdminQueue`, `refreshAdminApplications`, `fetchAdminJob`, `refreshCrawled`, `fetchCrawledJob`, `saveAdminAiFlags`, `refreshCabinet`, `refreshMyApplications`, `refreshSavedJobs`, `refreshSavedJobIds`, `saveJob`, `unsaveJob`, `refreshNotifications`, `adminPatchJob`, `adminRejectJob`, `adminActJob`, `crawledPatchJob`, `crawledVisibility`, `crawledMerge`, `cabinetSaveJob`, `cabinetCloseJob`, `withdrawApplication`, `patchApplicationStatus`, `markNotificationRead`, `markAllNotificationsRead`, `loadSkillGap`, `saveEmailPrefs`, `saveCompanyProfile`, `createManualAd`, `loadCvProfile`, `loadRoles`, `saveCvProfile`, `cancelCvParse`, `deleteCvProfile`, `uploadCvProfile`, `saveConsents`, `applyToJob`, `exportMyData`.

---

## Redesign notes (Hybrid 2 status)
1. Filter drawer a11y (dialog, trap, scroll lock, Apply) — bottom-sheet ≤767, modal ≥768.
2. JobRow: title + company ayrı linklər; ≤767 stacked meta.
3. Save requires auth redirect; do not hide save for guests without replacement CTA.
4. Apply/original auth gate + `t.locked` copy.
5. Role-gated menus and nav tabs (`canPostJobs`, `isStaff`, candidate/employer/staff combinations).
6. FAQ home-dan çıxarıldı (SEO FAQ `lib/seo` qala bilər).
7. FAQ city/source copy — filter əlavə edilmədi (plan scope xaricində).
8. Mobile vs desktop account menu parity — unify edilib.
