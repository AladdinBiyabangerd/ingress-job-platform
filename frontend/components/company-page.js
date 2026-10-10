import { BoardSideNav } from "./board-side-nav";
import { LinkPager } from "./companies";
import { CompanyAvatar, Popularity } from "./company-bits";
import { JobBoardCard } from "./job-board-card";
import { Shell } from "./shell";
import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";

export function CompanyPage({ locale, data }) {
  const t = text(locale);
  const company = data.company;
  const jobs = data.jobs || { items: [], page: 1, pages: 1, total: 0 };
  const base = hrefFor(locale, { companySlug: company.slug });
  const latest = calendarDate(company.latest_posted, locale);
  const locations = company.locations || [];

  return (
    <Shell locale={locale} mode="companies" companySlug={company.slug}>
      <div className="home home-board companies-board">
        <div className="home-board-shell companies-board-shell">
          <BoardSideNav locale={locale} />

          <div className="home-board-main">
            <header className="company-board-profile">
              <a className="company-board-back" href={hrefFor(locale, { mode: "companies" })}>
                ← {t.companiesTitle}
              </a>
              <div className="company-board-profile-head">
                <CompanyAvatar name={company.name} slug={company.slug} size="lg" />
                <div className="company-board-profile-copy">
                  <p className="home-board-eyebrow">{t.companiesEyebrow}</p>
                  <h1 className="home-board-title">{company.name}</h1>
                  <p className="home-board-lede company-board-profile-meta">
                    {locations.length ? <span>{locations.join(" · ")}</span> : null}
                    {latest ? (
                      <span>
                        {t.latestPosted}: <time dateTime={company.latest_posted}>{latest}</time>
                      </span>
                    ) : null}
                  </p>
                </div>
              </div>

              <dl className="company-board-stats">
                <div>
                  <dt>{t.statOpenJobs}</dt>
                  <dd>{company.open_jobs}</dd>
                </div>
                <div>
                  <dt>{t.statRemoteShare}</dt>
                  <dd>{company.remote_share}%</dd>
                </div>
                <div>
                  <dt>{t.statLocations}</dt>
                  <dd>{locations.length}</dd>
                </div>
                {company.relocation_jobs ? (
                  <div>
                    <dt>{t.relocationBadge}</dt>
                    <dd>{company.relocation_jobs}</dd>
                  </div>
                ) : null}
                {company.onsite_jobs ? (
                  <>
                    <div>
                      <dt>{t.statApplications}</dt>
                      <dd>{company.applications}</dd>
                    </div>
                    <div>
                      <dt>{t.statPerJob}</dt>
                      <dd>{company.applications_per_job}</dd>
                    </div>
                  </>
                ) : null}
              </dl>

              {company.onsite_jobs ? (
                <div className="company-board-popularity-block">
                  <Popularity locale={locale} share={company.application_share} withHelp={false} />
                  <p className="companies-board-help">
                    {t.popularityHelp} {t.applicationsNote}
                  </p>
                </div>
              ) : null}

              {company.top_categories?.length || company.top_tech?.length ? (
                <div className="company-board-summary">
                  {company.top_categories?.length ? (
                    <div>
                      <h2 className="home-board-catalogue-kicker">{t.companyCategories}</h2>
                      <ul className="job-board-card-tags">
                        {company.top_categories.map((item) => (
                          <li key={item.name}>
                            {categoryLabel(locale, item.name)}{" "}
                            <span className="chip-count">{item.count}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {company.top_tech?.length ? (
                    <div>
                      <h2 className="home-board-catalogue-kicker">{t.techStack}</h2>
                      <ul className="job-board-card-tags">
                        {company.top_tech.map((item) => (
                          <li key={item.name}>
                            {item.name} <span className="chip-count">{item.count}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </header>

            <section className="home-board-results" aria-labelledby="company-jobs-title">
              <div className="home-board-results-head">
                <div className="home-board-results-titles">
                  <p className="home-board-catalogue-kicker">{t.companyJobs}</p>
                  <h2 id="company-jobs-title" className="home-board-results-count">
                    {t.resultsCount(jobs.total)}
                  </h2>
                </div>
              </div>
              <div className="home-board-card-list">
                {jobs.items.map((job) => (
                  <JobBoardCard key={job.id} locale={locale} job={job} showCompany={false} />
                ))}
              </div>
              <LinkPager
                locale={locale}
                page={jobs.page}
                pages={jobs.pages}
                hrefOf={(next) => (next > 1 ? `${base}?page=${next}` : base)}
              />
            </section>
          </div>
        </div>
      </div>
    </Shell>
  );
}
