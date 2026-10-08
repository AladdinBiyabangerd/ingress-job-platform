import { AccountActions } from "./account-actions";
import { applicationsLabel } from "./job-card";
import { JsonLd } from "./json-ld";
import { PageChrome } from "./page-chrome";
import { SaveJobButton } from "./save-job-button";
import { Shell } from "./shell";
import { categoryLabel, hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { descriptionBlocks, linkParts, splitDescription } from "../lib/description";
import { jobPostingJsonLd } from "../lib/seo";

const TECH_VISIBLE = 8;

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

function FactCell({ label, children }) {
  return (
    <div className="h2-detail-fact">
      <span className="h2-detail-fact-label">{label}</span>
      <div className="h2-detail-fact-value">{children}</div>
    </div>
  );
}

function TechChips({ names }) {
  const visible = names.slice(0, TECH_VISIBLE);
  const rest = names.length - visible.length;
  return (
    <ul className="tech-chips">
      {visible.map((name) => (
        <li key={name} className="tech-chip">
          {name}
        </li>
      ))}
      {rest > 0 ? <li className="tech-chip more">+{rest}</li> : null}
    </ul>
  );
}

export function JobDetail({ locale, job }) {
  const t = text(locale);
  const blocks = descriptionBlocks(job.text, job.title);
  const { prose, lists, hasLists } = splitDescription(blocks);
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

  const locationValue = (
    <>
      {place}
      {job.remote && job.city ? <span className="fact-sub"> · {job.city}</span> : null}
    </>
  );

  const sourceValue = job.source_homepage ? (
    <a href={job.source_homepage} target="_blank" rel="noopener">
      {job.source_name}
    </a>
  ) : (
    job.source_name
  );

  const actions = (
    <AccountActions
      locale={locale}
      jobId={job.id}
      returnTo={jobHref}
      onsite={Boolean(job.onsite)}
      hasOriginal={Boolean(job.has_original)}
      form={job.form}
    />
  );

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

          <div className="h2-detail-ribbon" aria-label={t.keyFacts}>
            <FactCell label={t.companies}>{company}</FactCell>
            <FactCell label={t.factLocation}>{locationValue}</FactCell>
            {jobType ? <FactCell label={t.adJobType}>{jobType}</FactCell> : null}
            {job.salary ? <FactCell label={t.adSalary}>{job.salary}</FactCell> : null}
            {job.category ? (
              <FactCell label={t.categoryFilter}>
                <span className="category-tag">{categoryLabel(locale, job.category)}</span>
              </FactCell>
            ) : null}
            {job.source_name ? <FactCell label={t.sources}>{sourceValue}</FactCell> : null}
            {posted ? (
              <FactCell label={t.factPosted}>
                <time dateTime={job.created_at}>{posted}</time>
              </FactCell>
            ) : null}
            {job.relocation ? <FactCell label={t.relocationBadge}>{t.relocationBadge}</FactCell> : null}
            {stack.length ? (
              <FactCell label={t.techStack}>
                <TechChips names={stack} />
              </FactCell>
            ) : null}
            {applications ? (
              <FactCell label={t.applicationsTitle}>
                <span
                  className={job.applications > 0 ? "applications-line" : "applications-line first"}
                  title={t.applicationsNote}
                >
                  {applications}
                </span>
              </FactCell>
            ) : null}
          </div>

          {hasLists ? (
            <div className={`h2-detail-split${prose.length ? "" : " is-single"}`}>
              {prose.length ? (
                <section className="h2-detail-main h2-panel" aria-label={t.description}>
                  <Description blocks={prose} />
                </section>
              ) : null}
              <section className="h2-detail-tasks h2-panel" aria-label={t.keyFacts}>
                <Description blocks={lists} />
                <div className="h2-detail-cta">{actions}</div>
              </section>
            </div>
          ) : (
            <div className="h2-detail-split is-single">
              {prose.length || blocks.length ? (
                <section className="h2-detail-main h2-panel" aria-label={t.description}>
                  <Description blocks={prose.length ? prose : blocks} />
                </section>
              ) : null}
              <div className="h2-detail-cta-band h2-panel">{actions}</div>
            </div>
          )}
        </article>
      </Shell>
    </>
  );
}
