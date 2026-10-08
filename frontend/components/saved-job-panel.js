import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";

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

export function placeLine(t, job) {
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const type = jobTypeLabel(t, job.job_type);
  if (type && !job.remote) return `${place} · ${type}`;
  if (job.relocation) return `${place} · ${t.relocationBadge}`;
  return place;
}

/** Compact selectable row for the saved-jobs split list. */
export function SavedJobListItem({ locale, job, selected, onSelect }) {
  const t = text(locale);
  const company = job.company || t.noCompany;
  const place = placeLine(t, job);
  const savedWhen = calendarDate(job.saved_at || job.created_at, locale);
  return (
    <button
      type="button"
      className={["saved-list-item", selected ? "is-selected" : ""].filter(Boolean).join(" ")}
      onClick={() => onSelect(job.id)}
      aria-current={selected ? "true" : undefined}
    >
      <span className="saved-list-avatar" aria-hidden="true">
        {companyInitial(company)}
      </span>
      <span className="saved-list-body">
        <span className="saved-list-title">{job.title}</span>
        <span className="saved-list-meta">
          <span className="saved-list-company">{company}</span>
          <span aria-hidden="true"> · </span>
          <span>{place}</span>
          {savedWhen ? (
            <>
              <span aria-hidden="true"> · </span>
              <time dateTime={job.saved_at || job.created_at}>{savedWhen}</time>
            </>
          ) : null}
        </span>
      </span>
    </button>
  );
}

/** Preview pane using list payload fields only. */
export function SavedJobPreview({ locale, job, onUnsave, onBack = null }) {
  const t = text(locale);
  if (!job) return null;

  const company = job.company || t.noCompany;
  const place = placeLine(t, job);
  const salary = String(job.salary || "").trim();
  const posted = calendarDate(job.created_at, locale);
  const savedWhen = calendarDate(job.saved_at, locale);
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack.slice(0, 6) : [];
  const jobHref = hrefFor(locale, { jobId: job.id });

  return (
    <article className="saved-preview">
      {onBack ? (
        <button type="button" className="saved-preview-back text-btn" onClick={onBack}>
          ← {t.savedJobsBackToList}
        </button>
      ) : null}
      <header className="saved-preview-head">
        <span className="saved-preview-avatar" aria-hidden="true">
          {companyInitial(company)}
        </span>
        <div className="saved-preview-head-text">
          {job.company_slug ? (
            <a className="saved-preview-company" href={hrefFor(locale, { companySlug: job.company_slug })}>
              {company}
            </a>
          ) : (
            <span className="saved-preview-company">{company}</span>
          )}
          {job.category ? (
            <span className="saved-preview-category">{categoryLabel(locale, job.category)}</span>
          ) : null}
        </div>
      </header>
      <h2 className="saved-preview-title">{job.title}</h2>
      {stack.length ? (
        <ul className="saved-preview-stack">
          {stack.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ) : null}
      <p className="saved-preview-line">
        <span>{place}</span>
        <span aria-hidden="true"> · </span>
        <span>{salary || "—"}</span>
      </p>
      <dl className="saved-preview-facts">
        {posted ? (
          <div>
            <dt>{t.savedJobsPosted}</dt>
            <dd>
              <time dateTime={job.created_at}>{posted}</time>
            </dd>
          </div>
        ) : null}
        {savedWhen ? (
          <div>
            <dt>{t.savedJobsSavedAt}</dt>
            <dd>
              <time dateTime={job.saved_at}>{savedWhen}</time>
            </dd>
          </div>
        ) : null}
      </dl>
      <div className="saved-preview-actions">
        <a className="btn primary" href={jobHref}>
          {t.savedJobsViewJob}
        </a>
        <button type="button" className="text-btn" onClick={() => onUnsave(job.id)}>
          {t.unsaveJob}
        </button>
      </div>
    </article>
  );
}
