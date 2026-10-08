import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { SaveJobButton } from "./save-job-button";

function companyInitial(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

function jobTypeLabel(t, jobType) {
  if (jobType === "ofis") return t.jobOffice;
  if (jobType === "hibrid") return t.jobHybrid;
  if (jobType === "uzaqdan") return t.jobRemoteType;
  return "";
}

function placeLine(t, job) {
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const type = jobTypeLabel(t, job.job_type);
  if (type && !job.remote) return `${place} · ${type}`;
  if (job.relocation) return `${place} · ${t.relocationBadge}`;
  return place;
}

/**
 * Hybrid 2 table-style job row. Title and company are separate links
 * (same nested-link rule as legacy JobCard).
 */
export function JobRow({
  locale,
  job,
  matchScore = null,
  active = false,
  showSave = true,
  showCompany = true,
  leading = null,
}) {
  const t = text(locale);
  const when = calendarDate(job.created_at, locale);
  const company = job.company || t.noCompany;
  const salary = String(job.salary || "").trim();
  const place = placeLine(t, job);
  const score =
    typeof matchScore === "number" && Number.isFinite(matchScore)
      ? Math.round(matchScore * 100)
      : null;
  const jobHref = hrefFor(locale, { jobId: job.id });
  return (
    <article
      className={[
        "job-row",
        active ? "is-active" : "",
        showCompany ? "" : "job-row-no-company",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="job-row-save">
        {leading != null ? (
          leading
        ) : showSave ? (
          <SaveJobButton
            locale={locale}
            jobId={job.id}
            returnTo={jobHref}
            className="save-job-btn-row"
          />
        ) : null}
      </div>
      <div className="job-row-role">
        <a className="job-row-title" href={jobHref}>
          {job.title}
        </a>
        {job.category ? (
          <span className="job-row-category">{categoryLabel(locale, job.category)}</span>
        ) : null}
        <p className="job-row-stack">
          {showCompany ? (
            <>
              {job.company_slug ? (
                <a className="job-row-stack-company" href={hrefFor(locale, { companySlug: job.company_slug })}>
                  {company}
                </a>
              ) : (
                <span>{company}</span>
              )}
              <span className="job-row-stack-dot" aria-hidden="true">
                {" "}
                ·{" "}
              </span>
            </>
          ) : null}
          <span>{place}</span>
          {salary ? (
            <>
              <span className="job-row-stack-dot" aria-hidden="true">
                {" "}
                ·{" "}
              </span>
              <span>{salary}</span>
            </>
          ) : null}
          {when ? (
            <>
              <span className="job-row-stack-dot" aria-hidden="true">
                {" "}
                ·{" "}
              </span>
              <time dateTime={job.created_at}>{when}</time>
            </>
          ) : null}
        </p>
      </div>
      {showCompany ? (
        <div className="job-row-company">
          <span className="job-row-avatar" aria-hidden="true">
            {companyInitial(company)}
          </span>
          {job.company_slug ? (
            <a className="job-row-company-link" href={hrefFor(locale, { companySlug: job.company_slug })}>
              {company}
            </a>
          ) : (
            <span>{company}</span>
          )}
        </div>
      ) : null}
      <div className="job-row-place">{place}</div>
      <div className="job-row-salary">{salary || "—"}</div>
      <div className="job-row-posted">
        {when ? <time dateTime={job.created_at}>{when}</time> : "—"}
      </div>
      {score !== null ? (
        <div className="job-row-match" title={t.recommendationsScore(matchScore)}>
          <span className="job-row-match-badge">{score}%</span>
        </div>
      ) : (
        <div className="job-row-match job-row-match-empty" aria-hidden="true" />
      )}
      <a className="job-row-open" href={jobHref} aria-label={t.openRole}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
          <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </a>
    </article>
  );
}
