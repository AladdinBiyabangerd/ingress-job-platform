import { AccountActions } from "./account-actions";
import { applicationsLabel } from "./job-card";
import { JsonLd } from "./json-ld";
import { Shell } from "./shell";
import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { descriptionBlocks, linkParts } from "../lib/description";
import { jobPostingJsonLd } from "../lib/seo";

function Linked({ value }) {
  return linkParts(value).map((part, index) =>
    part.type === "link" ? (
      <a key={index} href={part.href} target="_blank" rel="nofollow noopener noreferrer ugc">
        {part.text}
      </a>
    ) : (
      part.text
    ),
  );
}

function Description({ blocks }) {
  return (
    <div className="posting">
      {blocks.map((block, index) => {
        if (block.type === "heading") return <h3 key={index}>{block.text}</h3>;
        if (block.type === "list") {
          const List = block.ordered ? "ol" : "ul";
          return (
            <List key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <Linked value={item} />
                </li>
              ))}
            </List>
          );
        }
        return (
          <p key={index}>
            <Linked value={block.text} />
          </p>
        );
      })}
    </div>
  );
}

function jobTypeLabel(t, jobType) {
  if (jobType === "ofis") return t.jobOffice;
  if (jobType === "hibrid") return t.jobHybrid;
  if (jobType === "uzaqdan") return t.jobRemoteType;
  return "";
}

export function JobDetail({ locale, job }) {
  const t = text(locale);
  const blocks = descriptionBlocks(job.text, job.title);
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const jobType = jobTypeLabel(t, job.job_type);
  const posted = calendarDate(job.created_at, locale);
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack : [];
  const companyName = job.company || t.noCompany;
  const company = job.company_slug ? (
    <a className="company-link" href={hrefFor(locale, { companySlug: job.company_slug })}>
      {companyName}
    </a>
  ) : (
    companyName
  );
  const applications = applicationsLabel(t, job);
  return (
    <>
      <JsonLd data={jobPostingJsonLd(job, locale)} />
      <Shell locale={locale} mode="browse" jobId={job.id}>
        <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
          <ol>
            <li>
              <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
            </li>
            <li>
              <span aria-current="page">{job.title}</span>
            </li>
          </ol>
        </nav>
        <article className="detail">
          <header className="detail-head">
            {job.source_name ? (
              job.source_homepage ? (
                <p className="source-line">
                  <a className="source-pill" href={job.source_homepage} target="_blank" rel="noopener" title={t.sourceSite}>
                    {job.source_name}
                  </a>
                </p>
              ) : (
                <p className="source-pill">{job.source_name}</p>
              )
            ) : null}
            <h1>{job.title}</h1>
            <p className="meta line">
              <span className="detail-company">{company}</span>
              <span>{place}</span>
              {jobType ? <span>{jobType}</span> : null}
              {job.salary ? <span>{job.salary}</span> : null}
              {job.relocation ? <span className="relocation-badge">{t.relocationBadge}</span> : null}
            </p>
          </header>
          <div className="detail-layout">
            <section className="detail-main" aria-label={t.description}>
              {blocks.length ? <Description blocks={blocks} /> : null}
            </section>
            <aside className="detail-aside" aria-label={t.keyFacts}>
              <div className="facts-card">
                <h2 className="facts-title">{t.keyFacts}</h2>
                <dl className="facts">
                  <div>
                    <dt>{t.companies}</dt>
                    <dd>{company}</dd>
                  </div>
                  <div>
                    <dt>{t.factLocation}</dt>
                    <dd>
                      {place}
                      {job.remote && job.city ? <span className="fact-sub"> · {job.city}</span> : null}
                    </dd>
                  </div>
                  {jobType ? (
                    <div>
                      <dt>{t.adJobType}</dt>
                      <dd>{jobType}</dd>
                    </div>
                  ) : null}
                  {job.salary ? (
                    <div>
                      <dt>{t.adSalary}</dt>
                      <dd>{job.salary}</dd>
                    </div>
                  ) : null}
                  {job.category ? (
                    <div>
                      <dt>{t.categoryFilter}</dt>
                      <dd>
                        <span className="category-tag">{categoryLabel(locale, job.category)}</span>
                      </dd>
                    </div>
                  ) : null}
                  {job.source_name ? (
                    <div>
                      <dt>{t.sources}</dt>
                      <dd>
                        {job.source_homepage ? (
                          <a href={job.source_homepage} target="_blank" rel="noopener">
                            {job.source_name}
                          </a>
                        ) : (
                          job.source_name
                        )}
                      </dd>
                    </div>
                  ) : null}
                  {posted ? (
                    <div>
                      <dt>{t.factPosted}</dt>
                      <dd>
                        <time dateTime={job.created_at}>{posted}</time>
                      </dd>
                    </div>
                  ) : null}
                </dl>
                {job.relocation ? <p className="facts-badge">{t.relocationBadge}</p> : null}
                {stack.length ? (
                  <div className="tech-block">
                    <h2 className="tech-title">{t.techStack}</h2>
                    <ul className="tech-chips">
                      {stack.map((name) => (
                        <li key={name} className="tech-chip">{name}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {applications ? (
                  <p className={job.applications > 0 ? "applications-line" : "applications-line first"} title={t.applicationsNote}>
                    {applications}
                  </p>
                ) : null}
                <AccountActions
                  locale={locale}
                  jobId={job.id}
                  returnTo={hrefFor(locale, { jobId: job.id })}
                  onsite={Boolean(job.onsite)}
                  hasOriginal={Boolean(job.has_original)}
                  form={job.form}
                />
              </div>
            </aside>
          </div>
        </article>
      </Shell>
    </>
  );
}
