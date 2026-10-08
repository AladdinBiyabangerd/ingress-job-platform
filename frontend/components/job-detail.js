import { AccountActions } from "./account-actions";
import { applicationsLabel } from "./job-card";
import { JsonLd } from "./json-ld";
import { PageChrome } from "./page-chrome";
import { SaveJobButton } from "./save-job-button";
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

function companyInitial(name) {
  const s = String(name || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

export function JobDetail({ locale, job }) {
  const t = text(locale);
  const blocks = descriptionBlocks(job.text, job.title);
  const place = job.remote ? t.placeRemote : job.city || t.noCity;
  const jobType = jobTypeLabel(t, job.job_type);
  const posted = calendarDate(job.created_at, locale);
  const stack = Array.isArray(job.tech_stack) ? job.tech_stack : [];
  const companyName = job.company || t.noCompany;
  const jobHref = hrefFor(locale, { jobId: job.id });
  const company = job.company_slug ? (
    <a className="company-link" href={hrefFor(locale, { companySlug: job.company_slug })}>
      {companyName}
    </a>
  ) : (
    companyName
  );
  const applications = applicationsLabel(t, job);
  const metaBits = [
    place,
    jobType || null,
    job.salary || null,
    job.relocation ? t.relocationBadge : null,
  ].filter(Boolean);

  return (
    <>
      <JsonLd data={jobPostingJsonLd(job, locale)} />
      <Shell locale={locale} mode="browse" jobId={job.id}>
        <article className="h2-detail">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={job.title}
            actions={
              <SaveJobButton
                locale={locale}
                jobId={job.id}
                returnTo={jobHref}
                className="save-job-btn-detail"
              />
            }
          >
            <div className="h2-detail-kicker">
              {job.source_name ? (
                job.source_homepage ? (
                  <a
                    className="source-pill"
                    href={job.source_homepage}
                    target="_blank"
                    rel="noopener"
                    title={t.sourceSite}
                  >
                    {job.source_name}
                  </a>
                ) : (
                  <span className="source-pill">{job.source_name}</span>
                )
              ) : null}
              <p className="h2-detail-meta">
                <span className="h2-detail-company">
                  <span className="h2-detail-avatar" aria-hidden="true">
                    {companyInitial(companyName)}
                  </span>
                  {company}
                </span>
                {metaBits.map((bit) => (
                  <span key={bit}>{bit}</span>
                ))}
              </p>
            </div>
          </PageChrome>

          <div className="h2-detail-layout">
            <section className="h2-detail-main h2-panel" aria-label={t.description}>
              {blocks.length ? <Description blocks={blocks} /> : null}
            </section>
            <aside className="h2-detail-aside" aria-label={t.keyFacts}>
              <div className="h2-panel h2-facts">
                <h2 className="h2-panel-title">{t.keyFacts}</h2>
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
                        <li key={name} className="tech-chip">
                          {name}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {applications ? (
                  <p
                    className={job.applications > 0 ? "applications-line" : "applications-line first"}
                    title={t.applicationsNote}
                  >
                    {applications}
                  </p>
                ) : null}
                <AccountActions
                  locale={locale}
                  jobId={job.id}
                  returnTo={jobHref}
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
