import { LinkPager } from "./companies";
import { CompanyAvatar, Popularity } from "./company-bits";
import { JobRow } from "./job-row";
import { PageChrome } from "./page-chrome";
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
      <div className="h2-public h2-company">
        <PageChrome
          backHref={hrefFor(locale, { mode: "companies" })}
          backLabel={t.companiesTitle}
          title={company.name}
          count={jobs.total != null ? String(jobs.total) : null}
        >
          <div className="h2-company-kicker">
            <CompanyAvatar name={company.name} slug={company.slug} size="lg" />
            <p className="h2-detail-meta">
              {locations.length ? <span>{locations.join(" · ")}</span> : null}
              {latest ? (
                <span>
                  {t.latestPosted}: <time dateTime={company.latest_posted}>{latest}</time>
                </span>
              ) : null}
            </p>
          </div>
        </PageChrome>

        <dl className="h2-stat-strip">
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
          <div className="h2-company-popularity">
            <Popularity locale={locale} share={company.application_share} withHelp={false} />
            <p className="h2-help">
              {t.popularityHelp} {t.applicationsNote}
            </p>
          </div>
        ) : null}

        {company.top_categories?.length || company.top_tech?.length ? (
          <div className="h2-company-summary">
            {company.top_categories?.length ? (
              <div>
                <h2 className="h2-panel-title">{t.companyCategories}</h2>
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
                <h2 className="h2-panel-title">{t.techStack}</h2>
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

        <section className="h2-company-jobs" aria-labelledby="company-jobs-title">
          <div className="open-roles-head">
            <h2 id="company-jobs-title">{t.companyJobs}</h2>
            <p className="open-roles-count">{jobs.total}</p>
          </div>
          <div className="job-row-list">
            {jobs.items.map((job) => (
              <JobRow key={job.id} locale={locale} job={job} showCompany={false} />
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
    </Shell>
  );
}
