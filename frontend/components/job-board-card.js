import { hrefFor, text } from "../lib/copy";
import { relativePosted } from "../lib/dates";
import { SaveJobButton } from "./save-job-button";

function companyInitial(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

function placeLine(t, job) {
  const parts = [];
  if (job.city) parts.push(job.city);
  if (job.remote) parts.push(t.placeRemote || t.remoteFilter);
  if (job.relocation) parts.push(t.tabRelocation || t.relocationFilter);
  if (!parts.length) return t.noCity;
  return parts.join(" · ");
}

function langCodes(job) {
  const raw = String(job.language || "").trim().toLowerCase();
  if (!raw) return [];
  if (raw.includes(",") || raw.includes(" ")) {
    return raw.split(/[,\s]+/).filter(Boolean);
  }
  return [raw];
}

/**
 * Board mockup job card — compact row with bookmark save and View details CTA.
 */
export function JobBoardCard({ locale, job, featured = false }) {
  const t = text(locale);
  const company = job.company || t.noCompany;
  const salary = String(job.salary || "").trim();
  const place = placeLine(t, job);
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack.slice(0, 5) : [];
  const langs = langCodes(job);
  const when = relativePosted(job.created_at, locale);
  const jobHref = hrefFor(locale, { jobId: job.id });

  return (
    <article className={`job-board-card${featured ? " is-featured" : ""}`}>
      {featured ? <span className="job-board-card-badge">{t.featuredBadge}</span> : null}
      <div className="job-board-card-main">
        <span className="job-board-card-logo" aria-hidden="true">
          {companyInitial(company)}
        </span>
        <div className="job-board-card-body">
          <div className="job-board-card-titles">
            {job.company_slug ? (
              <a className="job-board-card-company" href={hrefFor(locale, { companySlug: job.company_slug })}>
                {company}
              </a>
            ) : (
              <span className="job-board-card-company">{company}</span>
            )}
            <h3 className="job-board-card-title">
              <a href={jobHref}>{job.title}</a>
            </h3>
          </div>
          {stack.length ? (
            <ul className="job-board-card-tags">
              {stack.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          ) : null}
          <div className="job-board-card-meta">
            <span className="job-board-card-meta-item">
              <MetaPin />
              {place}
            </span>
            {langs.length ? (
              <span className="job-board-card-meta-item">
                <MetaGlobe />
                {langs.map((code) => code.toUpperCase()).join(" ")}
              </span>
            ) : null}
            {salary ? (
              <span className="job-board-card-meta-item">
                <MetaPay />
                {salary}
              </span>
            ) : null}
          </div>
        </div>
        <div className="job-board-card-aside">
          <div className="job-board-card-actions">
            <SaveJobButton
              locale={locale}
              jobId={job.id}
              returnTo={jobHref}
              icon="bookmark"
              className="save-job-btn-board"
            />
            <a className="btn primary job-board-card-cta" href={jobHref}>
              {t.viewDetails}
            </a>
          </div>
          {when ? (
            <time className="job-board-card-when" dateTime={job.created_at}>
              {when}
            </time>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function MetaPin() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M12 21s7-5.5 7-11a7 7 0 10-14 0c0 5.5 7 11 7 11z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function MetaGlobe() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18" />
    </svg>
  );
}

function MetaPay() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <path d="M2 10h20" />
    </svg>
  );
}
