import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { applicationsLabel } from "./job-card";
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

function featuredTags(locale, t, job) {
  const tags = [];
  if (job.category) tags.push(categoryLabel(locale, job.category));
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack : [];
  for (const name of stack) {
    if (tags.length >= 4) break;
    if (name && !tags.includes(name)) tags.push(name);
  }
  const type = jobTypeLabel(t, job.job_type);
  if (type && tags.length < 4 && !tags.includes(type)) tags.push(type);
  if (job.remote && tags.length < 4 && !tags.includes(t.placeRemote)) tags.push(t.placeRemote);
  return tags.slice(0, 4);
}

/** Brand-panel featured role — no stock photo. */
export function FeaturedJob({ locale, job, matchScore = null }) {
  const t = text(locale);
  if (!job) return null;

  const company = job.company || t.noCompany;
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const type = jobTypeLabel(t, job.job_type);
  const when = calendarDate(job.created_at, locale);
  const applications = applicationsLabel(t, job, { short: true });
  const tags = featuredTags(locale, t, job);
  const jobHref = hrefFor(locale, { jobId: job.id });
  const score =
    typeof matchScore === "number" && Number.isFinite(matchScore)
      ? Math.round(matchScore * 100)
      : null;

  return (
    <section className="featured-job" aria-labelledby="featured-job-title">
      <div className="featured-job-panel" aria-hidden="true">
        <span className="featured-job-glyph">{companyInitial(company)}</span>
      </div>
      <div className="featured-job-body">
        <p className="featured-job-badge">
          <span aria-hidden="true">★</span> {t.featuredRole}
          {score !== null ? <span className="featured-job-score">{score}%</span> : null}
        </p>
        <h2 id="featured-job-title" className="featured-job-title">
          <a href={jobHref}>{job.title}</a>
        </h2>
        <p className="featured-job-meta">
          <span className="featured-job-avatar" aria-hidden="true">
            {companyInitial(company)}
          </span>
          {job.company_slug ? (
            <a href={hrefFor(locale, { companySlug: job.company_slug })}>{company}</a>
          ) : (
            <span>{company}</span>
          )}
          <span className="featured-job-dot" aria-hidden="true">
            ·
          </span>
          <span>{place}</span>
          {type ? (
            <>
              <span className="featured-job-dot" aria-hidden="true">
                ·
              </span>
              <span>{type}</span>
            </>
          ) : null}
        </p>
        {tags.length ? (
          <ul className="featured-job-tags">
            {tags.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        ) : null}
        <div className="featured-job-actions">
          <a className="btn featured-job-apply" href={jobHref}>
            {t.apply}
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true" focusable="false">
              <path d="M3.5 8h9M8.5 4l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
          <SaveJobButton
            locale={locale}
            jobId={job.id}
            returnTo={jobHref}
            className="save-job-btn-featured"
          />
        </div>
        <p className="featured-job-foot">
          {when ? (
            <span>
              {t.factPosted}: <time dateTime={job.created_at}>{when}</time>
            </span>
          ) : null}
          {applications ? <span>{applications}</span> : null}
        </p>
      </div>
    </section>
  );
}
