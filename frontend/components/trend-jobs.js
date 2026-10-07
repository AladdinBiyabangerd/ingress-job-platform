import { hrefFor, text } from "../lib/copy";
import { LinkPager } from "./companies";
import { Shell } from "./shell";

function jobMeta(t, job) {
  return [job.company, job.city, job.remote ? t.placeRemote : null, job.salary]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" · ");
}

function JobsList({ t, locale, jobs }) {
  if (!jobs.length) {
    return <p className="hint">{t.trendsDetailJobsEmpty}</p>;
  }
  return (
    <ul className="reco-jobs trend-detail-jobs">
      {jobs.map((job) => {
        const meta = jobMeta(t, job);
        return (
          <li key={job.job_id} className="reco-job">
            <div className="reco-job-top">
              <div className="reco-job-body">
                <a className="reco-job-title" href={hrefFor(locale, { jobId: job.job_id })}>
                  <strong>{job.title}</strong>
                </a>
                {meta ? <span className="hint">{meta}</span> : null}
              </div>
            </div>
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

  if (error || !data) {
    return (
      <Shell locale={locale} mode="trends">
        <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
          <ol>
            <li>
              <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
            </li>
            <li>
              <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
            </li>
            <li>
              <span aria-current="page">{t.trendsDetailNotFound}</span>
            </li>
          </ol>
        </nav>
        <main className="trend-detail-page">
          <p className="note">{t.trendsDetailNotFound}</p>
          <p className="hint">
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsDetailBack}</a>
          </p>
        </main>
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
      <div className="trend-detail-top">
        <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
          <ol>
            <li>
              <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
            </li>
            <li>
              <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
            </li>
            <li>
              <a href={detailHref}>{data.name}</a>
            </li>
            <li>
              <span aria-current="page">{t.trendsDetailJobs}</span>
            </li>
          </ol>
        </nav>
        <a className="trend-back" href={detailHref}>
          {t.trendsDetailJobsBack}
        </a>
      </div>

      <main className="trend-detail-page">
        <section className="trend-detail-section" aria-labelledby="trend-jobs-heading">
          <h2 id="trend-jobs-heading">
            {t.trendsDetailJobs}
            <span className="recommendations-panel-count">{total.toLocaleString("en-US")}</span>
          </h2>
          <JobsList t={t} locale={locale} jobs={jobs} />
          <LinkPager locale={locale} page={currentPage} pages={pages} hrefOf={hrefOf} />
        </section>
      </main>
    </Shell>
  );
}
