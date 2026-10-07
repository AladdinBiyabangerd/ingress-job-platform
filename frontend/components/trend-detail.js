"use client";

import { useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { loginHref } from "../lib/auth-link";
import { AcademyCourseLinks, SkillRow } from "./skill-gap-bits";
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

function YouBlock({ t, locale, authenticated, candidate, you, showYou, learnNext, companionsHave }) {
  if (!authenticated || !candidate || !showYou) {
    if (you && you.matching_consent === false) {
      return (
        <p className="hint">
          {t.recommendationsConsent}{" "}
          <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
        </p>
      );
    }
    return null;
  }
  if (!learnNext.length && !companionsHave.length) return null;
  return (
    <>
      {learnNext.length ? (
        <div className="skills-panel skills-panel-missing">
          <h3>
            {t.trendsDetailCompanionsLearn}
            <span className="skills-panel-count">{learnNext.length}</span>
          </h3>
          <ul className="skills-rows">
            {learnNext.map((item) => (
              <SkillRow key={`learn-${item.skill_id || item.name}`} t={t} item={item} tone="missing" />
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
              <SkillRow key={`have-${item.skill_id || item.name}`} t={t} item={item} tone="have" />
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

function JobsList({ t, locale, jobs }) {
  if (!jobs.length) {
    return <p className="hint">{t.trendsDetailJobsEmpty}</p>;
  }
  return (
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
  );
}

function FactsCard({
  t,
  share,
  growth,
  data,
  salary,
  marketCourses,
  showGuestCta,
  detailHref,
  jobsOpen,
  onToggleJobs,
}) {
  return (
    <div className="facts-card">
      <h2 className="facts-title">{t.keyFacts}</h2>
      <dl className="facts">
        {share !== null ? (
          <div>
            <dt>{t.trendsShare}</dt>
            <dd>{share}%</dd>
          </div>
        ) : null}
        {growth ? (
          <div>
            <dt>{t.trendsGrowth}</dt>
            <dd>
              <span className={`trends-growth trends-growth-${growth.direction}`}>{growth.label}</span>
            </dd>
          </div>
        ) : null}
        {typeof data.ad_count === "number" ? (
          <div>
            <dt>{t.trendsAds}</dt>
            <dd>{data.ad_count.toLocaleString("en-US")}</dd>
          </div>
        ) : null}
        {salary ? (
          <div>
            <dt>{t.trendsSalaryLabel}</dt>
            <dd>
              {salary.median}
              {salary.range ? <span className="fact-sub"> · {salary.range}</span> : null}
              {salary.sample ? <span className="fact-sub"> · {salary.sample}</span> : null}
            </dd>
          </div>
        ) : null}
        {data.as_of ? (
          <div>
            <dt>{t.trendsAsOfLabel}</dt>
            <dd>{data.as_of}</dd>
          </div>
        ) : null}
      </dl>

      <p className="hint trends-disclaimer">{data.disclaimer || t.trendsDisclaimer}</p>

      <div className="trend-detail-courses">
        <AcademyCourseLinks item={marketCourses} />
      </div>

      <div className="actions">
        <button
          type="button"
          className="btn primary"
          aria-expanded={jobsOpen}
          aria-controls="trend-jobs"
          onClick={onToggleJobs}
        >
          {t.trendsDetailJobs}
        </button>
        {showGuestCta ? (
          <a className="btn" href={loginHref({ intent: "job_candidate", returnTo: detailHref })}>
            {t.trendsDetailGuestCta}
          </a>
        ) : null}
      </div>
    </div>
  );
}

export function TrendDetailPage({ locale, data, error }) {
  const t = text(locale);
  const me = useInitialMe();
  const authenticated = Boolean(me?.authenticated);
  const candidate = Boolean(me?.candidate || me?.staff);
  const skillId = data?.skill_id;
  const detailHref = skillId != null ? hrefFor(locale, { mode: "trend", skillId }) : hrefFor(locale, { mode: "trends" });
  const [jobsOpen, setJobsOpen] = useState(false);

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
        <main className="trend-detail-page">
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
  const showGuestCta = !authenticated || !candidate;
  const showConsentHint = Boolean(you && you.matching_consent === false);
  const showCompanions =
    authenticated && candidate && showYou && (learnNext.length > 0 || companionsHave.length > 0);
  const showYouSection = showConsentHint || showCompanions;
  const splitLayout = !showCompanions;

  const facts = (
    <FactsCard
      t={t}
      share={share}
      growth={growth}
      data={data}
      salary={salary}
      marketCourses={marketCourses}
      showGuestCta={showGuestCta}
      detailHref={detailHref}
      jobsOpen={jobsOpen}
      onToggleJobs={() => setJobsOpen((open) => !open)}
    />
  );

  const jobsSection = jobsOpen ? (
    <section className="trend-detail-section" id="trend-jobs" aria-labelledby="trend-jobs-heading">
      <h2 id="trend-jobs-heading">
        {t.trendsDetailJobs}
        <span className="recommendations-panel-count">{jobs.length}</span>
      </h2>
      <JobsList t={t} locale={locale} jobs={jobs} />
    </section>
  ) : (
    <div id="trend-jobs" hidden />
  );

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <div className="trend-detail-top">
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
        <a className="trend-back" href={hrefFor(locale, { mode: "trends" })}>
          {t.trendsDetailBack}
        </a>
      </div>

      <main
        className={
          splitLayout && jobsOpen
            ? "trend-detail-page trend-detail-page-split"
            : "trend-detail-page"
        }
      >
        {splitLayout && jobsOpen ? (
          <div className="detail-layout trend-detail-layout">
            <div className="detail-main">
              {showConsentHint ? (
                <section className="trend-detail-section">
                  <YouBlock
                    t={t}
                    locale={locale}
                    authenticated={authenticated}
                    candidate={candidate}
                    you={you}
                    showYou={showYou}
                    learnNext={learnNext}
                    companionsHave={companionsHave}
                  />
                </section>
              ) : null}
              {jobsSection}
            </div>
            <aside className="detail-aside" aria-label={t.keyFacts}>
              {facts}
            </aside>
          </div>
        ) : (
          <>
            {facts}
            {showYouSection ? (
              <section className="trend-detail-section">
                <YouBlock
                  t={t}
                  locale={locale}
                  authenticated={authenticated}
                  candidate={candidate}
                  you={you}
                  showYou={showYou}
                  learnNext={learnNext}
                  companionsHave={companionsHave}
                />
              </section>
            ) : null}
            {jobsSection}
          </>
        )}

        <p className="hint skills-footer">
          <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
        </p>
      </main>
    </Shell>
  );
}
