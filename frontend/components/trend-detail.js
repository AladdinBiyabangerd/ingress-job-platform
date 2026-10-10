"use client";

import { hrefFor, text } from "../lib/copy";
import { loginHref } from "../lib/auth-link";
import { recommendationsEnabled } from "../lib/product-features";
import { AcademyCourseLinks, SkillRow, sharePct } from "./skill-gap-bits";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";
import { SkillIcon } from "./skill-icon";
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

function KpiStrip({ t, share, growth, data, salaries, jobsHref }) {
  const hasAny =
    share !== null ||
    growth ||
    typeof data.ad_count === "number" ||
    salaries.length > 0;
  if (!hasAny) return null;
  return (
    <div className="h2-trend-stats td-a-kpis" role="group" aria-label={t.keyFacts}>
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
    </div>
  );
}

function AsideActions({ t, data, marketCourses, showGuestCta, detailHref, jobsHref }) {
  return (
    <aside className="td-a-aside h2-panel" aria-label={t.keyFacts}>
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
      {data.as_of ? <p className="hint td-a-asof">{t.trendsAsOf(data.as_of)}</p> : null}
      <p className="hint trends-disclaimer">{data.disclaimer || t.trendsDisclaimer}</p>
    </aside>
  );
}

function HaveStrip({ t, items }) {
  if (!items.length) return null;
  return (
    <section className="td-a-have skills-panel skills-panel-have">
      <h3>
        {t.trendsDetailCompanionsHave}
        <span className="skills-panel-count">{items.length}</span>
      </h3>
      <ul className="td-a-have-chips">
        {items.map((item) => {
          const share = sharePct(item.share);
          return (
            <li key={`have-${item.skill_id || item.name}`} className="td-a-have-chip">
              <strong>{item.name}</strong>
              {share !== null ? <span>{share}%</span> : null}
            </li>
          );
        })}
      </ul>
    </section>
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
  const showLearn = authenticated && candidate && showYou && learnNext.length > 0;
  const showHave = authenticated && candidate && showYou && companionsHave.length > 0;

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <div className="h2-public h2-trend-detail td-a">
        <PageChrome
          backHref={hrefFor(locale, { mode: "trends" })}
          backLabel={t.trendsTitle}
          title={
            <span className="page-chrome-title-with-icon">
              <SkillIcon name={data.name} />
              <span>{data.name}</span>
            </span>
          }
        />

        <KpiStrip t={t} share={share} growth={growth} data={data} salaries={salaries} jobsHref={jobsHref} />

        {showConsentHint ? (
          <p className="hint">
            {t.recommendationsConsent}{" "}
            <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
          </p>
        ) : null}

        {showLearn ? (
          <div className="td-a-body">
            <div className="td-a-main">
              <section className="skills-panel skills-panel-missing td-a-learn">
                <h3>
                  {t.trendsDetailCompanionsLearn}
                  <span className="skills-panel-count">{learnNext.length}</span>
                </h3>
                <ul className="skills-rows td-a-learn-grid">
                  {learnNext.map((item) => (
                    <SkillRow
                      key={`learn-${item.skill_id || item.name}`}
                      t={t}
                      item={item}
                      tone="missing"
                    />
                  ))}
                </ul>
              </section>
            </div>
            <AsideActions
              t={t}
              data={data}
              marketCourses={marketCourses}
              showGuestCta={showGuestCta}
              detailHref={detailHref}
              jobsHref={jobsHref}
            />
          </div>
        ) : (
          <AsideActions
            t={t}
            data={data}
            marketCourses={marketCourses}
            showGuestCta={showGuestCta}
            detailHref={detailHref}
            jobsHref={jobsHref}
          />
        )}

        {showHave ? <HaveStrip t={t} items={companionsHave} /> : null}

        {recommendationsEnabled() ? (
          <p className="hint skills-footer">
            <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
          </p>
        ) : null}
      </div>
    </Shell>
  );
}
