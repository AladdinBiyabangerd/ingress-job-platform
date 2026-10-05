import { AccountActions } from "./account-actions";
import { JsonLd } from "./json-ld";
import { Shell } from "./shell";
import { hrefFor, text } from "../lib/copy";
import { jobPostingJsonLd } from "../lib/seo";

function tidyLines(raw, title) {
  const lines = String(raw || "")
    .replace(/\u00a0/g, " ")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter((line) => line && !/^[,.;:]+$/.test(line));
  const merged = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const next = lines[i + 1];
    const after = lines[i + 2];
    if (next && after && /\ba$/i.test(line) && next.length < 80 && /^,/.test(after)) {
      merged.push(`${line} ${next}${after}`.replace(/\s+,/g, ","));
      i += 2;
      continue;
    }
    if (title && line.toLowerCase() === title.toLowerCase() && merged.length === 0) continue;
    merged.push(line);
  }
  return merged;
}

function bulletOf(line) {
  const marked = line.match(/^(?:[•●▪‣\-–—]\s+|\d+[.)]\s+)(.+)$/);
  if (marked) return marked[1].trim();
  if (/;$/.test(line) && line.length < 280) return line.replace(/;$/, "").trim();
  return null;
}

function looksLikeHeading(line) {
  if (!line || line.length > 64) return false;
  const words = line.split(/\s+/);
  if (words.length > 7) return false;
  if (/[.!?;]$/.test(line)) return false;
  if (/,/.test(line)) return false;
  if (/:$/.test(line)) return true;
  return words.length <= 5;
}

function blocks(raw, title) {
  const lines = tidyLines(raw, title);
  const out = [];
  let list = null;
  const flush = () => {
    if (list) {
      out.push({ type: "list", items: list });
      list = null;
    }
  };
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const bullet = bulletOf(line);
    if (bullet) {
      list = list || [];
      list.push(bullet);
      continue;
    }
    const next = lines[i + 1];
    const nextBullet = next ? bulletOf(next) : null;
    const nextSentence = next && /^.{12,220}[.]$/.test(next);
    if (looksLikeHeading(line) && (nextBullet || nextSentence || (next && looksLikeHeading(next) === false && next.length > line.length))) {
      flush();
      out.push({ type: "heading", text: line.replace(/:$/, "") });
      continue;
    }
    if (list && /^.{12,180}[.]$/.test(line)) {
      list.push(line.replace(/\.$/, ""));
      continue;
    }
    flush();
    out.push({ type: "text", text: line });
  }
  flush();
  return out;
}

export function JobDetail({ locale, job }) {
  const t = text(locale);
  const parts = blocks(job.text, job.title);
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
            <span>{job.company || t.noCompany}</span>
            <span>{job.remote ? t.placeRemote : (job.city || t.noCity)}</span>
            {job.job_type === "ofis" ? <span>{t.jobOffice}</span> : null}
            {job.job_type === "hibrid" ? <span>{t.jobHybrid}</span> : null}
            {job.job_type === "uzaqdan" ? <span>{t.jobRemoteType}</span> : null}
            {job.salary ? <span>{job.salary}</span> : null}
            {job.relocation ? <span>{t.relocationBadge}</span> : null}
          </p>
          {Array.isArray(job.tech_stack) && job.tech_stack.length ? (
            <div className="tech-block">
              <h2 className="tech-title">{t.techStack}</h2>
              <ul className="tech-chips">
                {job.tech_stack.map((name) => (
                  <li key={name} className="tech-chip">{name}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {parts.length ? (
            <div className="posting">
              {parts.map((part, index) => {
                if (part.type === "heading") return <h2 key={index}>{part.text.replace(/:$/, "")}</h2>;
                if (part.type === "list") {
                  return (
                    <ul key={index}>
                      {part.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  );
                }
                return <p key={index}>{part.text}</p>;
              })}
            </div>
          ) : null}
          <AccountActions
            locale={locale}
            jobId={job.id}
            returnTo={hrefFor(locale, { jobId: job.id })}
            onsite={Boolean(job.onsite)}
            hasOriginal={Boolean(job.has_original)}
            form={job.form}
          />
        </article>
      </Shell>
    </>
  );
}
