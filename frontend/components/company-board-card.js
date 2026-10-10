import { CompanyAvatar, Popularity, companyHref } from "./company-bits";
import { categoryLabel, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";

/**
 * Board-style company card — matches JobBoardCard density and chrome.
 */
export function CompanyBoardCard({ locale, company }) {
  const t = text(locale);
  const category = company.top_categories?.[0];
  const tech = (company.top_tech || []).slice(0, 3);
  const latest = calendarDate(company.latest_posted, locale);
  const href = companyHref(locale, company.slug);

  return (
    <article className="job-board-card company-board-card">
      <div className="job-board-card-main">
        <CompanyAvatar name={company.name} slug={company.slug} />
        <div className="job-board-card-body">
          <div className="job-board-card-titles">
            <p className="company-board-card-jobs">{t.openJobs(company.open_jobs)}</p>
            <h3 className="job-board-card-title">
              <a href={href}>{company.name}</a>
            </h3>
          </div>
          {category || tech.length || company.remote_jobs || company.relocation_jobs ? (
            <ul className="job-board-card-tags">
              {category ? (
                <li className="company-board-tag-category">{categoryLabel(locale, category.name)}</li>
              ) : null}
              {tech.map((item) => (
                <li key={item.name}>{item.name}</li>
              ))}
              {company.remote_jobs ? <li className="company-board-tag-remote">{t.remoteJobs(company.remote_jobs)}</li> : null}
              {company.relocation_jobs ? (
                <li className="company-board-tag-relocation">{t.relocationJobs(company.relocation_jobs)}</li>
              ) : null}
            </ul>
          ) : null}
          <div className="job-board-card-meta company-board-card-meta">
            {company.onsite_jobs ? (
              <>
                <span className="job-board-card-meta-item" title={t.applicationsNote}>
                  {t.applicationsCount(company.applications)}
                  <span className="company-board-meta-sub">
                    {t.statPerJob}: {company.applications_per_job}
                  </span>
                </span>
                <span className="company-board-popularity">
                  <Popularity locale={locale} share={company.application_share} compact />
                </span>
              </>
            ) : null}
            {latest ? (
              <span className="job-board-card-meta-item">
                {t.latestPosted}:{" "}
                <time dateTime={company.latest_posted}>{latest}</time>
              </span>
            ) : null}
          </div>
        </div>
        <div className="job-board-card-aside">
          <div className="job-board-card-actions">
            <a className="btn primary job-board-card-cta" href={href}>
              {t.viewCompany}
            </a>
          </div>
        </div>
      </div>
    </article>
  );
}
