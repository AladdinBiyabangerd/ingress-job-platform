import { hrefFor, text } from "../lib/copy";
import { LinkPager } from "./companies";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";

function jobMeta(t, job) {
  return [job.company, job.city, job.remote ? t.placeRemote : null, job.salary]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" · ");
}

function companyInitial(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

function JobsList({ t, locale, jobs }) {
  if (!jobs.length) {
    return <p className="hint">{t.trendsDetailJobsEmpty}</p>;
  }
  return (
    <ul className="trend-jobs-list">
      {jobs.map((job) => {
        const meta = jobMeta(t, job);
        const href = hrefFor(locale, { jobId: job.job_id });
        return (
          <li key={job.job_id} className="trend-job-row">
            <span className="job-row-avatar" aria-hidden="true">
              {companyInitial(job.company)}
            </span>
            <div className="trend-job-body">
              <a className="trend-job-title" href={href}>
                {job.title}
              </a>
              {meta ? <span className="trend-job-meta">{meta}</span> : null}
            </div>
            <a className="job-row-open" href={href} aria-label={t.openRole}>
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
          </li>
        );
      })}
    </ul>
  );
}

export function TrendJobsPage({ locale, data, error, page = 1 }) {
  const t = text(locale);
  const skillId = data?.skill_id;
  const detailHref =
    skillId != null ? hrefFor(locale, { mode: "trend", skillId }) : hrefFor(locale, { mode: "trends" });
  const jobsBase =
    skillId != null ? hrefFor(locale, { mode: "trendJobs", skillId }) : hrefFor(locale, { mode: "trends" });
  const skillName = data?.name || t.trendsDetailNotFound;

  if (error || !data) {
    return (
      <Shell locale={locale} mode="trends">
        <div className="h2-public">
          <PageChrome
            backHref={hrefFor(locale, { mode: "trends" })}
            backLabel={t.trendsTitle}
            title={t.trendsDetailNotFound}
          />
          <p className="note">{t.trendsDetailNotFound}</p>
        </div>
      </Shell>
    );
  }

  const jobs = Array.isArray(data.jobs) ? data.jobs : [];
  const total = typeof data.jobs_total === "number" ? data.jobs_total : jobs.length;
  const perPage = typeof data.jobs_per_page === "number" && data.jobs_per_page > 0 ? data.jobs_per_page : 20;
  const currentPage = typeof data.jobs_page === "number" && data.jobs_page > 0 ? data.jobs_page : page;
  const pages = Math.max(1, Math.ceil(total / perPage));

  function hrefOf(nextPage) {
    return nextPage > 1 ? `${jobsBase}?page=${nextPage}` : jobsBase;
  }

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <div className="h2-public h2-trend-jobs">
        <PageChrome
          backHref={detailHref}
          backLabel={skillName}
          title={t.trendsDetailJobs}
          count={String(total)}
        />
        <JobsList t={t} locale={locale} jobs={jobs} />
        <LinkPager locale={locale} page={currentPage} pages={pages} hrefOf={hrefOf} />
      </div>
    </Shell>
  );
}
