import { LinkPager } from "./companies";
import { CompanyAvatar, Popularity } from "./company-bits";
import { JobCard } from "./job-card";
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
      <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
        <ol>
          <li>
            <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
          </li>
          <li>
            <a href={hrefFor(locale, { mode: "companies" })}>{t.companiesTitle}</a>
          </li>
          <li>
            <span aria-current="page">{company.name}</span>
          </li>
        </ol>
      </nav>
      <section className="company-header">
        <div className="company-header-top">
          <CompanyAvatar name={company.name} slug={company.slug} size="lg" />
          <div className="company-header-title">
            <h1>{company.name}</h1>
            <p className="meta line">
              {locations.length ? <span>{locations.join(" · ")}</span> : null}
              {latest ? (
                <span>
                  {t.latestPosted}: <time dateTime={company.latest_posted}>{latest}</time>
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <dl className="company-stats">
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
          <div className="company-popularity">
            <Popularity locale={locale} share={company.application_share} withHelp={false} />
            <p className="company-help">
              {t.popularityHelp} {t.applicationsNote}
            </p>
          </div>
        ) : null}
        {company.top_categories?.length || company.top_tech?.length ? (
          <div className="company-summary">
            {company.top_categories?.length ? (
              <div>
                <h2 className="tech-title">{t.companyCategories}</h2>
                <ul className="tech-chips">
                  {company.top_categories.map((item) => (
                    <li key={item.name} className="category-tag">
                      {categoryLabel(locale, item.name)} <span className="chip-count">{item.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {company.top_tech?.length ? (
              <div>
                <h2 className="tech-title">{t.techStack}</h2>
                <ul className="tech-chips">
                  {company.top_tech.map((item) => (
                    <li key={item.name} className="tech-chip">
                      {item.name} <span className="chip-count">{item.count}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
      <section className="company-jobs" aria-labelledby="company-jobs-title">
        <h2 id="company-jobs-title" className="company-jobs-title">
          {t.companyJobs} <span className="check-count">{jobs.total}</span>
        </h2>
        <div className="job-list">
          {jobs.items.map((job) => (
            <JobCard key={job.id} locale={locale} job={job} showCompany={false} />
          ))}
        </div>
        <LinkPager
          locale={locale}
          page={jobs.page}
          pages={jobs.pages}
          hrefOf={(next) => (next > 1 ? `${base}?page=${next}` : base)}
        />
      </section>
    </Shell>
  );
}
