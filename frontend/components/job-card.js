import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { SaveJobButton } from "./save-job-button";

function Icon({ name }) {
  const props = {
    className: "filter-icon",
    width: 16,
    height: 16,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
    focusable: "false",
  };
  if (name === "date") {
    return (
      <svg {...props}>
        <rect x="2.5" y="3.5" width="11" height="10" rx="1.5" />
        <path d="M2.5 6.5h11M5.5 2v2M10.5 2v2" />
      </svg>
    );
  }
  if (name === "relocation") {
    return (
      <svg {...props}>
        <path d="M2.5 9.5 13.5 4l-2 9-3-3.25L6 11.5V8.5" />
        <path d="M8.5 9.75 13.5 4" />
      </svg>
    );
  }
  if (name === "applications") {
    return (
      <svg {...props}>
        <circle cx="6" cy="5.5" r="2.25" />
        <path d="M2 13c.4-2.2 2-3.5 4-3.5s3.6 1.3 4 3.5M10.5 3.6a2.1 2.1 0 0 1 0 3.8M12 9.8c1 .5 1.7 1.6 2 3.2" />
      </svg>
    );
  }
  return (
    <svg {...props}>
      <path d="M8 13.5s4.25-3.7 4.25-6.55a4.25 4.25 0 0 0-8.5 0C3.75 9.8 8 13.5 8 13.5z" />
      <circle cx="8" cy="6.9" r="1.35" />
    </svg>
  );
}

/** On-site application count for a job; null when applying happens on the source site. */
export function applicationsLabel(t, job, { short = false } = {}) {
  if (!job.onsite || typeof job.applications !== "number") return null;
  if (job.applications > 0) return t.applicationsCount(job.applications);
  return short ? t.applicationsFirst : t.applicationsNone;
}

/**
 * One job in a list. The title link covers the whole card; the company name
 * is its own link to the company page, so no link is nested in another.
 */
export function JobCard({ locale, job, showCompany = true, showSave = true }) {
  const t = text(locale);
  const when = calendarDate(job.created_at, locale);
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack : [];
  const applications = applicationsLabel(t, job, { short: true });
  const company = job.company || t.noCompany;
  return (
    <article className="job-card">
      <div className="job-card-body">
        {showCompany || job.source_name ? (
          <p className="job-kicker">
            {showCompany ? (
              job.company_slug ? (
                <a className="job-company job-company-link" href={hrefFor(locale, { companySlug: job.company_slug })}>
                  {company}
                </a>
              ) : (
                <span className="job-company">{company}</span>
              )
            ) : null}
            {job.source_name ? <span className="source-pill">{job.source_name}</span> : null}
          </p>
        ) : null}
        <h2>
          <a className="job-card-link" href={hrefFor(locale, { jobId: job.id })}>
            {job.title}
          </a>
        </h2>
        {job.category ? <span className="category-tag">{categoryLabel(locale, job.category)}</span> : null}
        {stack.length ? (
          <span className="tech-chips" aria-label={t.techStack}>
            {stack.slice(0, 6).map((name) => (
              <span key={name} className="tech-chip">{name}</span>
            ))}
            {stack.length > 6 ? <span className="tech-chip more">+{stack.length - 6}</span> : null}
          </span>
        ) : null}
        <span className="job-facts">
          <span className="job-fact">
            <Icon name="city" />
            {place}
          </span>
          {job.relocation ? (
            <span className="job-fact">
              <Icon name="relocation" />
              {t.relocationBadge}
            </span>
          ) : null}
          {when ? (
            <span className="job-fact">
              <Icon name="date" />
              <time dateTime={job.created_at}>{when}</time>
            </span>
          ) : null}
          {applications ? (
            <span className={job.applications > 0 ? "job-fact" : "job-fact job-fact-first"}>
              <Icon name="applications" />
              {applications}
            </span>
          ) : null}
        </span>
      </div>
      <div className="job-card-aside">
        {showSave ? (
          <SaveJobButton
            locale={locale}
            jobId={job.id}
            returnTo={hrefFor(locale, { jobId: job.id })}
            className="save-job-btn-card"
          />
        ) : null}
        <span className="job-open" aria-hidden="true">{t.openRole}</span>
      </div>
    </article>
  );
}
