import { CompanyAvatar, Popularity, companyHref } from "./company-bits";
import { PageHeader } from "./page-header";
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
        <span className="pager-btn" aria-disabled="true">{t.pagePrev}</span>
      )}
      <span className="pager-status">{t.pageOf(page, pages)}</span>
      {page < pages ? (
        <a className="pager-btn" href={hrefOf(page + 1)} rel="next">
          {t.pageNext}
        </a>
      ) : (
        <span className="pager-btn" aria-disabled="true">{t.pageNext}</span>
      )}
    </nav>
  );
}

function CompanyCard({ locale, company }) {
  const t = text(locale);
  const category = company.top_categories?.[0];
  const tech = (company.top_tech || []).slice(0, 4);
  const latest = calendarDate(company.latest_posted, locale);
  return (
    <article className="company-card">
      <div className="company-card-head">
        <CompanyAvatar name={company.name} slug={company.slug} />
        <div className="company-card-title">
          <h2>
            <a className="company-card-link" href={companyHref(locale, company.slug)}>
              {company.name}
            </a>
          </h2>
          <p className="company-card-jobs">{t.openJobs(company.open_jobs)}</p>
        </div>
      </div>
      {category || tech.length ? (
        <div className="company-card-chips">
          {category ? <span className="category-tag">{categoryLabel(locale, category.name)}</span> : null}
          {tech.map((item) => (
            <span key={item.name} className="tech-chip">{item.name}</span>
          ))}
        </div>
      ) : null}
      {company.remote_jobs || company.relocation_jobs ? (
        <div className="company-badges">
          {company.remote_jobs ? <span className="company-badge remote">{t.remoteJobs(company.remote_jobs)}</span> : null}
          {company.relocation_jobs ? (
            <span className="company-badge relocation">{t.relocationJobs(company.relocation_jobs)}</span>
          ) : null}
        </div>
      ) : null}
      {company.onsite_jobs ? (
        <div className="company-card-stats">
          <span className="company-card-apps">
            <strong>{t.applicationsCount(company.applications)}</strong>
            <span>
              {t.statPerJob}: {company.applications_per_job}
            </span>
          </span>
          <Popularity locale={locale} share={company.application_share} compact />
        </div>
      ) : null}
      {latest ? (
        <p className="company-card-foot">
          {t.latestPosted}: <time dateTime={company.latest_posted}>{latest}</time>
        </p>
      ) : null}
    </article>
  );
}

export function CompaniesPage({ locale, data, error, q, sort }) {
  const t = text(locale);
  const items = data?.items || [];
  const page = data?.page || 1;
  const pages = data?.pages || 1;
  return (
    <Shell locale={locale} mode="companies">
      <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
        <ol>
          <li>
            <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
          </li>
          <li>
            <span aria-current="page">{t.companiesTitle}</span>
          </li>
        </ol>
      </nav>
      <PageHeader
        className="companies-hero"
        title={t.companiesTitle}
        lede={t.companiesLede}
      >
        <form className="companies-tools" role="search" method="get" action={hrefFor(locale, { mode: "companies" })}>
          <label className="companies-search">
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
          <label className="companies-sort">
            <span className="visually-hidden">{t.sort}</span>
            <SortSelect name="sort" value={sort} options={sortOptions(t)} label={t.sort} id="companies-sort" />
          </label>
          <button type="submit" className="btn primary">{t.companiesSearchButton}</button>
        </form>
      </PageHeader>
      {error ? <p className="note">{t.loadError}</p> : null}
      {!error && items.length === 0 ? (
        <div className="companies-empty">
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
          <div className="company-grid">
            {items.map((company) => (
              <CompanyCard key={company.slug} locale={locale} company={company} />
            ))}
          </div>
          <p className="companies-help">{t.popularityHelp}</p>
        </>
      ) : null}
      <LinkPager locale={locale} page={page} pages={pages} hrefOf={(next) => listHref(locale, { q, sort, page: next })} />
    </Shell>
  );
}

export function CompaniesLoading({ locale }) {
  const t = text(locale);
  return (
    <Shell locale={locale} mode="companies">
      <div className="companies-loading" role="status" aria-live="polite">
        <span className="visually-hidden">{t.companiesLoading}</span>
        <div className="skeleton skeleton-hero" />
        <div className="company-grid">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index} className="company-card skeleton-card" aria-hidden="true">
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
