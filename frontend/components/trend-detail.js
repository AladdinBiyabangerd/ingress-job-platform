"use client";

import { hrefFor, text } from "../lib/copy";
import { LoginLink } from "./login-link";
import { recommendationsEnabled } from "../lib/product-features";
import { AcademyCourseLinks, SkillRow, sharePct } from "./skill-gap-bits";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";
import { SkillIcon } from "./skill-icon";
import { useInitialMe } from "./me-seed";

const MAX_DISPLAY_GROWTH = 5;
const MAX_COMPANION_CARDS = 3;

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

function companionsOf(data) {
  if (!Array.isArray(data?.often_with)) return [];
  return data.often_with
    .map((row) => {
      const name = String(row?.name || "").trim();
      const share = pct(row?.share);
      if (!name || share === null) return null;
      return {
        skill_id: row?.skill_id ?? null,
        name,
        share,
      };
    })
    .filter(Boolean)
    .slice(0, MAX_COMPANION_CARDS);
}

function PulseKpi({ label, href, children }) {
  const body = (
    <>
      <span className="td-pulse-kpi-label">{label}</span>
      <span className="td-pulse-kpi-value">{children}</span>
    </>
  );
  if (href) {
    return (
      <a className="td-pulse-kpi" href={href}>
        {body}
      </a>
    );
  }
  return <div className="td-pulse-kpi">{body}</div>;
}

function CompanionCards({ t, locale, items }) {
  if (!items.length) return null;
  return (
    <section className="td-pulse-companions" aria-label={t.trendsDetailPulseOftenLabel}>
      {items.map((item) => {
        const href =
          item.skill_id != null ? hrefFor(locale, { mode: "trend", skillId: item.skill_id }) : null;
        const inner = (
          <>
            <p className="td-pulse-comp-label">{t.trendsDetailPulseOftenLabel}</p>
            <h2 className="td-pulse-comp-title">
              <SkillIcon name={item.name} />
              <span>
                {item.name} · {item.share}%
              </span>
            </h2>
            <p className="td-pulse-comp-body">{t.trendsDetailPulseCompanionShare(item.share)}</p>
          </>
        );
        return href ? (
          <a key={item.skill_id || item.name} className="td-pulse-comp" href={href}>
            {inner}
          </a>
        ) : (
          <article key={item.name} className="td-pulse-comp">
            {inner}
          </article>
        );
      })}
    </section>
  );
}

function YouPanel({
  t,
  locale,
  showGuestCta,
  detailHref,
  showConsentHint,
  showHave,
  showLearn,
  companionsHave,
  learnNext,
  focusHave,
}) {
  return (
    <section id="you" className="td-pulse-panel td-pulse-you" aria-labelledby="td-pulse-you-title">
      <h2 id="td-pulse-you-title">{t.trendsDetailYou}</h2>

      {showConsentHint ? (
        <p className="hint td-pulse-you-hint">
          {t.recommendationsConsent}{" "}
          <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
        </p>
      ) : null}

      {showGuestCta ? (
        <>
          <p className="td-pulse-you-sub">{t.trendsDetailGuest}</p>
          <LoginLink
            className="td-pulse-guest-chip"
            intent="job_candidate"
            returnTo={detailHref}
          >
            {t.trendsDetailPulseGuestChip}
            <em> · {t.trendsDetailGuestCta}</em>
          </LoginLink>
          <p className="hint td-pulse-you-hint">{t.trendsDetailPulseGuestHint}</p>
        </>
      ) : (
        <>
          {focusHave != null ? (
            <p className={`td-pulse-focus ${focusHave ? "is-have" : "is-miss"}`}>
              {focusHave ? t.trendsDetailHaveFocus : t.trendsDetailMissingFocus}
            </p>
          ) : null}

          {showHave ? (
            <div className="td-pulse-have">
              <h3>
                {t.trendsDetailCompanionsHave}
                <span className="skills-panel-count">{companionsHave.length}</span>
              </h3>
              <ul className="td-pulse-have-chips">
                {companionsHave.map((item) => {
                  const share = sharePct(item.share);
                  return (
                    <li key={`have-${item.skill_id || item.name}`} className="td-pulse-have-chip">
                      <SkillIcon name={item.name} />
                      <strong>{item.name}</strong>
                      {share !== null ? <span>{share}%</span> : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}

          {showLearn ? (
            <div className="td-pulse-learn">
              <h3>
                {t.trendsDetailCompanionsLearn}
                <span className="skills-panel-count">{learnNext.length}</span>
              </h3>
              <ul className="skills-rows td-pulse-learn-grid">
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

          {!showHave && !showLearn && focusHave == null ? (
            <p className="hint td-pulse-you-hint">{t.trendsDetailGuest}</p>
          ) : null}
        </>
      )}
    </section>
  );
}

function NextAside({ t, data, marketCourses, showGuestCta, detailHref, jobsHref }) {
  return (
    <aside className="td-pulse-panel td-pulse-aside" aria-label={t.trendsDetailPulseNext}>
      <h2>{t.trendsDetailPulseNext}</h2>
      <p className="td-pulse-aside-sub">{t.trendsDetailPulseNextLede}</p>

      <div className="td-pulse-courses">
        <AcademyCourseLinks item={marketCourses} />
      </div>

      <div className="td-pulse-aside-actions">
        <a className="btn ink" href={jobsHref}>
          {t.trendsDetailJobs}
        </a>
        {showGuestCta ? (
          <LoginLink className="btn" intent="job_candidate" returnTo={detailHref}>
            {t.trendsDetailGuestCta}
          </LoginLink>
        ) : null}
      </div>

      {data.as_of ? <p className="hint td-pulse-meta">{t.trendsAsOf(data.as_of)}</p> : null}
      <p className="hint td-pulse-meta">{data.disclaimer || t.trendsDisclaimer}</p>
    </aside>
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
  const trendsHref = hrefFor(locale, { mode: "trends" });

  if (error || !data) {
    return (
      <Shell locale={locale} mode="trends">
        <div className="h2-public">
          <PageChrome
            backHref={trendsHref}
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
  const companions = companionsOf(data);
  const windowDays =
    typeof data.window_days === "number" && data.window_days > 0 ? data.window_days : 7;
  const you = data.you && typeof data.you === "object" ? data.you : null;
  const learnNext = Array.isArray(you?.learn_next) ? you.learn_next : [];
  const companionsHave = Array.isArray(you?.have) ? you.have : [];
  const showYou = Boolean(you && you.matching_consent !== false);
  const marketCourses = { academy_courses: data.academy_courses };
  const showGuestCta = !authenticated || !candidate;
  const showConsentHint = Boolean(you && you.matching_consent === false);
  const showLearn = authenticated && candidate && showYou && learnNext.length > 0;
  const showHave = authenticated && candidate && showYou && companionsHave.length > 0;
  const focusHave =
    authenticated && candidate && showYou && typeof you?.have_focus === "boolean"
      ? you.have_focus
      : null;
  const barWidth = share === null ? 0 : Math.max(8, Math.min(100, share));
  const hasKpis =
    share !== null ||
    growth ||
    typeof data.ad_count === "number" ||
    salaries.length > 0;

  return (
    <Shell locale={locale} mode="trends" skillId={skillId}>
      <div className="h2-public h2-trend-detail td-pulse">
        <section className="td-pulse-stage" aria-labelledby="td-pulse-title">
          <a className="td-pulse-back" href={trendsHref}>
            ← {t.trendsTitle}
          </a>

          <div className="td-pulse-hero">
            <div className="td-pulse-copy">
              <p className="td-pulse-kicker">
                {t.trendsDetailPulseKicker}
                <span aria-hidden="true"> · </span>
                {t.trendsDetailPulseWindow(windowDays)}
              </p>
              <div className="td-pulse-skill-head">
                <SkillIcon name={data.name} className="td-pulse-skill-icon" />
                <h1 id="td-pulse-title">{data.name}</h1>
              </div>
              <p className="td-pulse-lede">{t.trendsDetailPulseLede(data.name)}</p>
              <div className="td-pulse-cta">
                <a className="btn td-pulse-btn-primary" href={jobsHref}>
                  {t.trendsDetailJobs}
                </a>
                {showGuestCta ? (
                  <LoginLink
                    className="btn td-pulse-btn-ghost"
                    intent="job_candidate"
                    returnTo={detailHref}
                  >
                    {t.trendsDetailPulseCompare}
                  </LoginLink>
                ) : (
                  <a className="btn td-pulse-btn-ghost" href="#you">
                    {t.trendsDetailPulseCompare}
                  </a>
                )}
              </div>
            </div>

            {hasKpis ? (
              <aside className="td-pulse-kpi-card" aria-label={t.keyFacts}>
                <div className="td-pulse-kpi-grid">
                  {share !== null ? (
                    <PulseKpi label={t.trendsShare} href={jobsHref}>
                      {share}%
                    </PulseKpi>
                  ) : null}
                  {typeof data.ad_count === "number" ? (
                    <PulseKpi label={t.trendsAds} href={jobsHref}>
                      {data.ad_count.toLocaleString("en-US")}
                    </PulseKpi>
                  ) : null}
                  {growth ? (
                    <PulseKpi label={t.trendsGrowth} href={jobsHref}>
                      <span className={`trends-growth trends-growth-${growth.direction}`}>
                        {growth.label}
                      </span>
                    </PulseKpi>
                  ) : null}
                  {salaries.map((salary) => (
                    <PulseKpi key={salary.currency} label={t.trendsSalaryLabel} href={jobsHref}>
                      {salary.median}
                      {salary.range || salary.sample ? (
                        <span className="td-pulse-kpi-sub">
                          {[salary.range, salary.sample].filter(Boolean).join(" · ")}
                        </span>
                      ) : null}
                    </PulseKpi>
                  ))}
                </div>
                {share !== null ? (
                  <div className="td-pulse-bar" aria-hidden="true">
                    <span style={{ width: `${barWidth}%` }} />
                  </div>
                ) : null}
              </aside>
            ) : null}
          </div>
        </section>

        <div className="td-pulse-body">
          <CompanionCards t={t} locale={locale} items={companions} />

          <div className="td-pulse-split">
            <YouPanel
              t={t}
              locale={locale}
              showGuestCta={showGuestCta}
              detailHref={detailHref}
              showConsentHint={showConsentHint}
              showHave={showHave}
              showLearn={showLearn}
              companionsHave={companionsHave}
              learnNext={learnNext}
              focusHave={focusHave}
            />
            <NextAside
              t={t}
              data={data}
              marketCourses={marketCourses}
              showGuestCta={showGuestCta}
              detailHref={detailHref}
              jobsHref={jobsHref}
            />
          </div>

          {recommendationsEnabled() ? (
            <p className="hint skills-footer td-pulse-footer">
              <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
            </p>
          ) : null}
        </div>
      </div>
    </Shell>
  );
}
