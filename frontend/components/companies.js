import { BoardAcademyPromo, BoardSideNav } from "./board-side-nav";
import { CompanyBoardCard } from "./company-board-card";
import { Shell } from "./shell";
import { SortSelect } from "./sort-select";
import { hrefFor, text } from "../lib/copy";

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
    <nav className="home-board-pager pager" aria-label={t.pageOf(page, pages)}>
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

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  );
}

export function CompaniesPage({ locale, data, error, q, sort }) {
  const t = text(locale);
  const items = data?.items || [];
  const page = data?.page || 1;
  const pages = data?.pages || 1;
  const total = data?.total ?? 0;

  return (
    <Shell locale={locale} mode="companies">
      <div className="home home-board companies-board">
        <div className="home-board-shell companies-board-shell">
          <BoardSideNav locale={locale} />

          <div className="home-board-main">
            <div className="home-board-front">
              <section className="home-board-hero-copy" aria-labelledby="companies-front-title">
                <p className="home-board-eyebrow">{t.companiesEyebrow}</p>
                <p className="home-board-brand">{t.homeBrand}</p>
                <h1 id="companies-front-title" className="home-board-title">
                  {t.companiesTitle}
                </h1>
                <p className="home-board-lede">{t.companiesLede}</p>
              </section>

              <BoardAcademyPromo locale={locale} />

              <form
                className="home-board-search companies-board-search"
                role="search"
                method="get"
                action={hrefFor(locale, { mode: "companies" })}
              >
                <label className="home-board-search-field home-board-search-q">
                  <SearchIcon />
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
                <label className="home-board-search-field companies-board-sort-field">
                  <span className="visually-hidden">{t.sort}</span>
                  <SortSelect name="sort" value={sort} options={sortOptions(t)} label={t.sort} id="companies-sort" />
                </label>
                <button type="submit" className="btn primary home-board-search-submit">
                  {t.companiesSearchButton}
                </button>
              </form>
            </div>

            {error ? (
              <div className="note home-board-load-error" role="alert">
                <p>{t.loadError}</p>
              </div>
            ) : null}

            <section className="home-board-results" aria-labelledby="companies-results-heading">
              <div className="home-board-results-head">
                <div className="home-board-results-titles">
                  <p className="home-board-catalogue-kicker">{t.companiesTitle}</p>
                  <h2 id="companies-results-heading" className="home-board-results-count">
                    {t.companiesCount(total)}
                  </h2>
                </div>
              </div>

              {!error && items.length === 0 ? (
                <div className="job-empty">
                  <p className="job-empty-copy">{q ? t.companiesEmpty : t.companiesEmptyAll}</p>
                  {q ? (
                    <a className="btn job-empty-clear" href={hrefFor(locale, { mode: "companies" })}>
                      {t.companiesReset}
                    </a>
                  ) : null}
                </div>
              ) : null}

              {items.length ? (
                <>
                  <div className="home-board-card-list">
                    {items.map((company) => (
                      <CompanyBoardCard key={company.slug} locale={locale} company={company} />
                    ))}
                  </div>
                  <p className="companies-board-help">{t.popularityHelp}</p>
                </>
              ) : null}

              <LinkPager
                locale={locale}
                page={page}
                pages={pages}
                hrefOf={(next) => listHref(locale, { q, sort, page: next })}
              />
            </section>
          </div>
        </div>
      </div>
    </Shell>
  );
}

export function CompaniesLoading({ locale }) {
  const t = text(locale);
  return (
    <Shell locale={locale} mode="companies">
      <div className="home home-board companies-board companies-loading" role="status" aria-live="polite">
        <span className="visually-hidden">{t.companiesLoading}</span>
        <div className="home-board-shell companies-board-shell">
          <BoardSideNav locale={locale} />
          <div className="home-board-main">
            <div className="home-board-front">
              <section className="home-board-hero-copy">
                <span className="skeleton skeleton-line short" />
                <span className="skeleton skeleton-line" />
                <span className="skeleton skeleton-line short" />
              </section>
            </div>
            <div className="home-board-card-list">
              {Array.from({ length: 5 }, (_, index) => (
                <div key={index} className="job-board-card job-board-card-skeleton" aria-hidden="true">
                  <div className="job-board-card-main">
                    <span className="skeleton job-board-skel-logo" />
                    <div className="job-board-card-body">
                      <span className="skeleton skeleton-line short" />
                      <span className="skeleton skeleton-line" />
                      <span className="skeleton skeleton-line short" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Shell>
  );
}
