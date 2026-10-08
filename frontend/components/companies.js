import { CompanyAvatar, Popularity, companyHref } from "./company-bits";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";
import { SortSelect } from "./sort-select";
import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";

export const COMPANY_SORTS = ["jobs", "newest", "name", "applications"];

export function sortOptions(t) {
  return [
    { value: "jobs", label: t.sortMostJobs },
    { value: "newest", label: t.newest },
    { value: "name", label: t.sortAZ },
    { value: "applications", label: t.sortMostApplications },
  ];
}

function listHref(locale, { q, sort, page }) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (sort && sort !== "jobs") params.set("sort", sort);
  if (page && page > 1) params.set("page", String(page));
  const query = params.toString();
  return `${hrefFor(locale, { mode: "companies" })}${query ? `?${query}` : ""}`;
}

export function LinkPager({ locale, page, pages, hrefOf }) {
  const t = text(locale);
  if (pages <= 1) return null;
  return (
    <nav className="pager" aria-label={t.pageOf(page, pages)}>
      {page > 1 ? (
        <a className="pager-btn" href={hrefOf(page - 1)} rel="prev">
          {t.pagePrev}
        </a>
      ) : (
        <span className="pager-btn" aria-disabled="true">
          {t.pagePrev}
        </span>
      )}
      <span className="pager-status">{t.pageOf(page, pages)}</span>
      {page < pages ? (
        <a className="pager-btn" href={hrefOf(page + 1)} rel="next">
          {t.pageNext}
        </a>
      ) : (
        <span className="pager-btn" aria-disabled="true">
          {t.pageNext}
        </span>
      )}
    </nav>
  );
}

function CompanyRow({ locale, company }) {
  const t = text(locale);
  const category = company.top_categories?.[0];
  const tech = (company.top_tech || []).slice(0, 3);
  const latest = calendarDate(company.latest_posted, locale);
  const href = companyHref(locale, company.slug);

  return (
    <article className="company-row">
      <div className="company-row-main">
        <CompanyAvatar name={company.name} slug={company.slug} />
        <div className="company-row-title">
          <a className="company-row-link" href={href}>
            {company.name}
          </a>
          <p className="company-row-jobs">{t.openJobs(company.open_jobs)}</p>
        </div>
      </div>
      <div className="company-row-tags">
        {category ? <span className="category-tag">{categoryLabel(locale, category.name)}</span> : null}
        {tech.map((item) => (
          <span key={item.name} className="tech-chip">
            {item.name}
          </span>
        ))}
        {company.remote_jobs ? (
          <span className="company-badge remote">{t.remoteJobs(company.remote_jobs)}</span>
        ) : null}
        {company.relocation_jobs ? (
          <span className="company-badge relocation">{t.relocationJobs(company.relocation_jobs)}</span>
        ) : null}
      </div>
      <div className="company-row-stats">
        {company.onsite_jobs ? (
          <>
            <span className="company-row-apps" title={t.applicationsNote}>
              {t.applicationsCount(company.applications)}
              <span className="company-row-apps-sub">
                {t.statPerJob}: {company.applications_per_job}
              </span>
            </span>
            <Popularity locale={locale} share={company.application_share} compact />
          </>
        ) : null}
        {latest ? (
          <time className="company-row-latest" dateTime={company.latest_posted}>
            {latest}
          </time>
        ) : null}
      </div>
      <a className="company-row-open" href={href} aria-label={company.name}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
          <path
            d="M6 3.5 10.5 8 6 12.5"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </a>
    </article>
  );
}

export function CompaniesPage({ locale, data, error, q, sort }) {
  const t = text(locale);
  const items = data?.items || [];
  const page = data?.page || 1;
  const pages = data?.pages || 1;
  const total = data?.total;

  return (
    <Shell locale={locale} mode="companies">
      <div className="h2-public">
        <PageChrome
          backHref={hrefFor(locale)}
          backLabel={t.breadcrumbHome}
          title={t.companiesTitle}
          count={total != null ? String(total) : null}
        />

        <form
          className="h2-tools"
          role="search"
          method="get"
          action={hrefFor(locale, { mode: "companies" })}
        >
          <label className="h2-tools-search">
            <span className="visually-hidden">{t.companiesSearch}</span>
            <input
              type="search"
              name="q"
              defaultValue={q}
              maxLength={100}
              placeholder={t.companiesSearch}
              autoComplete="off"
            />
          </label>
          <label className="h2-tools-sort">
            <span className="visually-hidden">{t.sort}</span>
            <SortSelect name="sort" value={sort} options={sortOptions(t)} label={t.sort} id="companies-sort" />
          </label>
          <button type="submit" className="btn ink">
            {t.companiesSearchButton}
          </button>
        </form>

        {error ? <p className="note">{t.loadError}</p> : null}
        {!error && items.length === 0 ? (
          <div className="h2-empty">
            <p>{q ? t.companiesEmpty : t.companiesEmptyAll}</p>
            {q ? (
              <a className="back" href={hrefFor(locale, { mode: "companies" })}>
                {t.companiesReset}
              </a>
            ) : null}
          </div>
        ) : null}

        {items.length ? (
          <>
            <div className="company-row-list">
              {items.map((company) => (
                <CompanyRow key={company.slug} locale={locale} company={company} />
              ))}
            </div>
            <p className="h2-help">{t.popularityHelp}</p>
          </>
        ) : null}

        <LinkPager locale={locale} page={page} pages={pages} hrefOf={(next) => listHref(locale, { q, sort, page: next })} />
      </div>
    </Shell>
  );
}

export function CompaniesLoading({ locale }) {
  const t = text(locale);
  return (
    <Shell locale={locale} mode="companies">
      <div className="h2-public companies-loading" role="status" aria-live="polite">
        <span className="visually-hidden">{t.companiesLoading}</span>
        <div className="skeleton skeleton-hero" />
        <div className="company-row-list">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="company-row skeleton-card" aria-hidden="true">
              <span className="skeleton skeleton-avatar" />
              <span className="skeleton skeleton-line" />
              <span className="skeleton skeleton-line short" />
            </div>
          ))}
        </div>
      </div>
    </Shell>
  );
}
