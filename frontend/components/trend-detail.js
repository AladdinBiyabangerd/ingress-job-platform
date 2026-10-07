"use client";

import { hrefFor, text } from "../lib/copy";
import { loginHref } from "../lib/auth-link";
import { AcademyCourseLinks, SkillRow } from "./skill-gap-bits";
import { PageHeader } from "./page-header";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const MAX_DISPLAY_GROWTH = 5;

function pct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

function growthParts(growth) {
  if (typeof growth !== "number" || Number.isNaN(growth)) return null;
  if (Math.abs(growth) > MAX_DISPLAY_GROWTH) return null;
  const value = pct(growth);
  if (value === null) return null;
  const sign = value > 0 ? "+" : "";
  return {
    label: `${sign}${value}%`,
    direction: value > 0 ? "up" : value < 0 ? "down" : "flat",
  };
}

function formatMoney(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.round(value).toLocaleString("en-US");
}

function salaryParts(t, salary) {
  if (!salary || typeof salary !== "object") return null;
  const median = formatMoney(salary.median);
  const currency = String(salary.currency || "").trim();
  const n = typeof salary.n === "number" ? salary.n : 0;
  if (!median || !currency || n <= 0) return null;
  const low = formatMoney(salary.low);
  const high = formatMoney(salary.high);
  const range =
    low && high && low !== high && low !== median
      ? t.trendsSalaryRange(low, high, currency)
      : null;
  return {
    median: t.trendsSalaryMedian(median, currency),
    range,
    sample: t.trendsSalaryN(n),
  };
}

function jobMeta(t, job) {
  return [job.company, job.city, job.remote ? t.placeRemote : null, job.salary]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" · ");
}

export function TrendDetailPage({ locale, data, error }) {
  const t = text(locale);
  const me = useInitialMe();
  const authenticated = Boolean(me?.authenticated);
  const candidate = Boolean(me?.candidate || me?.staff);
  const skillId = data?.skill_id;
  const detailHref = skillId != null ? hrefFor(locale, { mode: "trend", skillId }) : hrefFor(locale, { mode: "trends" });

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
        <main className="trends-page trend-detail-page">
          <p className="note">{t.trendsDetailNotFound}</p>
          <p className="hint">
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsDetailBack}</a>
          </p>
        </main>
      </Shell>
    );
  }

  const share = pct(data.share);
  const growth = growthParts(data.growth_wow);
  const salary = salaryParts(t, data.salary);
  const jobs = Array.isArray(data.jobs) ? data.jobs : [];
  const you = data.you && typeof data.you === "object" ? data.you : null;
  const learnNext = Array.isArray(you?.learn_next) ? you.learn_next : [];
  const companionsHave = Array.isArray(you?.have) ? you.have : [];
  const showYou = Boolean(you && you.matching_consent !== false);
  const marketCourses = { academy_courses: data.academy_courses };

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
        <ol>
          <li>
            <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
          </li>
          <li>
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
          </li>
          <li>
            <span aria-current="page">{data.name}</span>
          </li>
        </ol>
      </nav>

      <main className="trends-page trend-detail-page">
        <PageHeader className="trends-hero" title={data.name} lede={t.trendsLede}>
          <div className="trend-detail-stats">
            {share !== null ? <span className="trends-share-value">{share}%</span> : null}
            {growth ? (
              <span className={`trends-growth trends-growth-${growth.direction}`}>{growth.label}</span>
            ) : null}
            {typeof data.ad_count === "number" ? (
              <span className="hint">{t.trendsAdsCount(data.ad_count)}</span>
            ) : null}
          </div>
        </PageHeader>

        <div className="trends-meta">
          <p className="hint trends-disclaimer">{data.disclaimer || t.trendsDisclaimer}</p>
          {data.as_of ? <p className="hint trends-window">{t.trendsAsOf(data.as_of)}</p> : null}
          {salary ? (
            <p className="hint">
              {[salary.median, salary.range, salary.sample].filter(Boolean).join(" · ")}
            </p>
          ) : null}
          <AcademyCourseLinks item={marketCourses} />
        </div>

        <section className="trend-detail-block" aria-labelledby="trend-you-heading">
          <h2 id="trend-you-heading">{t.trendsDetailYou}</h2>
          {!authenticated || !candidate ? (
            <div className="trend-detail-guest">
              <p className="lede">{t.trendsDetailGuest}</p>
              <a className="btn primary" href={loginHref({ intent: "job_candidate", returnTo: detailHref })}>
                {t.trendsDetailGuestCta}
              </a>
            </div>
          ) : you && you.matching_consent === false ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : showYou ? (
            <>
              <p className="hint">
                {you.have_focus ? t.trendsDetailHaveFocus : t.trendsDetailMissingFocus}
              </p>
              {learnNext.length ? (
                <div className="skills-panel skills-panel-missing">
                  <h3>
                    {t.trendsDetailCompanionsLearn}
                    <span className="skills-panel-count">{learnNext.length}</span>
                  </h3>
                  <ul className="skills-rows">
                    {learnNext.map((item) => (
                      <SkillRow
                        key={`learn-${item.skill_id || item.name}`}
                        t={t}
                        item={item}
                        tone="missing"
                      />
                    ))}
                  </ul>
                </div>
              ) : null}
              {companionsHave.length ? (
                <div className="skills-panel skills-panel-have">
                  <h3>
                    {t.trendsDetailCompanionsHave}
                    <span className="skills-panel-count">{companionsHave.length}</span>
                  </h3>
                  <ul className="skills-rows">
                    {companionsHave.map((item) => (
                      <SkillRow
                        key={`have-${item.skill_id || item.name}`}
                        t={t}
                        item={item}
                        tone="have"
                      />
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <div className="trend-detail-guest">
              <p className="lede">{t.trendsDetailGuest}</p>
              <a className="btn primary" href={loginHref({ intent: "job_candidate", returnTo: detailHref })}>
                {t.trendsDetailGuestCta}
              </a>
            </div>
          )}
        </section>

        <section className="trend-detail-block" aria-labelledby="trend-jobs-heading">
          <h2 id="trend-jobs-heading">
            {t.trendsDetailJobs}
            <span className="recommendations-panel-count">{jobs.length}</span>
          </h2>
          {!jobs.length ? (
            <p className="hint">{t.trendsDetailJobsEmpty}</p>
          ) : (
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
          )}
        </section>

        <p className="hint skills-footer">
          <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsDetailBack}</a>
          {" · "}
          <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
          {" · "}
          <a href={hrefFor(locale, { mode: "skills" })}>{t.skillsOpen}</a>
        </p>
      </main>
    </Shell>
  );
}
