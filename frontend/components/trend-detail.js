"use client";

import { hrefFor, text } from "../lib/copy";
import { loginHref } from "../lib/auth-link";
import { AcademyCourseLinks, SkillRow } from "./skill-gap-bits";
import { PageChrome } from "./page-chrome";
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

function oneSalaryParts(t, salary) {
  if (!salary || typeof salary !== "object") return null;
  const median = formatMoney(salary.median);
  const currency = String(salary.currency || "").trim();
  const n = typeof salary.n === "number" ? salary.n : 0;
  if (!median || !currency || n <= 0) return null;
  const low = formatMoney(salary.low);
  const high = formatMoney(salary.high);
  const range =
    low && high && low !== high && low !== median ? t.trendsSalaryRange(low, high, currency) : null;
  return {
    median: t.trendsSalaryMedian(median, currency),
    range,
    sample: t.trendsSalaryN(n),
    currency,
  };
}

function salaryGroups(t, data) {
  const list =
    Array.isArray(data?.salaries) && data.salaries.length
      ? data.salaries
      : data?.salary
        ? [data.salary]
        : [];
  return list.map((row) => oneSalaryParts(t, row)).filter(Boolean);
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

function TrendStat({ label, href, children }) {
  if (href) {
    return (
      <a className="h2-trend-stat" href={href}>
        <span className="h2-trend-stat-label">{label}</span>
        <span className="h2-trend-stat-value">{children}</span>
      </a>
    );
  }
  return (
    <div className="h2-trend-stat">
      <span className="h2-trend-stat-label">{label}</span>
      <span className="h2-trend-stat-value">{children}</span>
    </div>
  );
}

function FactsCard({ t, share, growth, data, salaries, marketCourses, showGuestCta, detailHref, jobsHref }) {
  return (
    <div className="h2-trend-facts">
      <div className="h2-trend-stats" role="group" aria-label={t.keyFacts}>
        {share !== null ? (
          <TrendStat label={t.trendsShare} href={jobsHref}>
            {share}%
          </TrendStat>
        ) : null}
        {growth ? (
          <TrendStat label={t.trendsGrowth} href={jobsHref}>
            <span className={`trends-growth trends-growth-${growth.direction}`}>{growth.label}</span>
          </TrendStat>
        ) : null}
        {typeof data.ad_count === "number" ? (
          <TrendStat label={t.trendsAds} href={jobsHref}>
            {data.ad_count.toLocaleString("en-US")}
          </TrendStat>
        ) : null}
        {salaries.map((salary) => (
          <TrendStat key={salary.currency} label={t.trendsSalaryLabel} href={jobsHref}>
            {salary.median}
            {salary.range || salary.sample ? (
              <span className="h2-trend-stat-sub">
                {[salary.range, salary.sample].filter(Boolean).join(" · ")}
              </span>
            ) : null}
          </TrendStat>
        ))}
        {data.as_of ? (
          <TrendStat label={t.trendsAsOfLabel} href={jobsHref}>
            {data.as_of}
          </TrendStat>
        ) : null}
      </div>

      <p className="hint trends-disclaimer">{data.disclaimer || t.trendsDisclaimer}</p>

      <div className="trend-detail-courses">
        <AcademyCourseLinks item={marketCourses} />
      </div>

      <div className="h2-trend-facts-actions actions">
        <a className="btn ink" href={jobsHref}>
          {t.trendsDetailJobs}
        </a>
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
  const detailHref =
    skillId != null ? hrefFor(locale, { mode: "trend", skillId }) : hrefFor(locale, { mode: "trends" });
  const jobsHref = skillId != null ? hrefFor(locale, { mode: "trendJobs", skillId }) : detailHref;

  if (error || !data) {
    return (
      <Shell locale={locale} mode="trends">
        <div className="h2-public">
          <PageChrome
            backHref={hrefFor(locale, { mode: "trends" })}
            backLabel={t.trendsTitle}
            title={t.trendsDetailNotFound}
          />
          <p className="note">{t.trendsDetailNotFound}</p>
        </div>
      </Shell>
    );
  }

  const share = pct(data.share);
  const growth = growthParts(data.growth_wow);
  const salaries = salaryGroups(t, data);
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

  const facts = (
    <FactsCard
      t={t}
      share={share}
      growth={growth}
      data={data}
      salaries={salaries}
      marketCourses={marketCourses}
      showGuestCta={showGuestCta}
      detailHref={detailHref}
      jobsHref={jobsHref}
    />
  );

  const youSection = showYouSection ? (
    <section className="h2-panel trend-detail-section">
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
  ) : null;

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <div className="h2-public h2-trend-detail">
        <PageChrome
          backHref={hrefFor(locale, { mode: "trends" })}
          backLabel={t.trendsTitle}
          title={data.name}
        />

        <div className={showCompanions ? "h2-detail-layout" : "h2-trend-detail-stack"}>
          {showCompanions ? (
            <>
              <div className="h2-detail-main">{youSection}</div>
              <aside className="h2-detail-aside" aria-label={t.keyFacts}>
                {facts}
              </aside>
            </>
          ) : (
            <>
              {facts}
              {youSection}
            </>
          )}
        </div>

        <p className="hint skills-footer">
          <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
        </p>
      </div>
    </Shell>
  );
}
