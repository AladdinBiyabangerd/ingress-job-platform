"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { RoleSkillParts } from "./role-skill-parts";
import { CareerPathLink } from "./skill-gap-bits";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

function localePrefix(locale) {
  return locale === "en" || locale === "ru" ? `/${locale}` : "";
}

function resolveHref(locale, href) {
  if (typeof href !== "string" || !href) return "";
  if (href.startsWith("http")) return href;
  if (!href.startsWith("/")) return "";
  if (href.startsWith("/en/") || href.startsWith("/ru/")) return href;
  return `${localePrefix(locale)}${href}`;
}

function skillNames(items) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item) => {
      if (typeof item === "string") return item.trim();
      if (item && typeof item === "object") return String(item.name || "").trim();
      return "";
    })
    .filter(Boolean);
}

function scorePct(score) {
  if (typeof score !== "number" || Number.isNaN(score)) return null;
  return Math.round(score * 100);
}

function CoachSection({ t, locale, coach }) {
  if (!coach) {
    return <p className="hint">{t.insightsCoachEmpty}</p>;
  }
  const role = String(coach.role || "").trim();
  const title = String(coach.ai_title || "").trim() || (role ? t.insightsCoachRole(role) : t.insightsCoachTitle);
  const body = String(coach.ai_body || "").trim();
  const must = skillNames(coach.must_learn);
  const strong = skillNames(coach.already_strong);
  const courses = Array.isArray(coach.academy_courses) ? coach.academy_courses : [];
  const pathId = String(coach.academy_career_path || "").trim();

  return (
    <section className="insights-block">
      <h2>{t.insightsCoachTitle}</h2>
      <p className="lede">{title}</p>
      {body ? <p className="hint">{body}</p> : null}
      <RoleSkillParts t={t} have={strong} missing={must} />
      {must.length ? (
        <p className="hint">
          <span className="role-skill-label">{t.skillsCoachMustLearn}</span>
          {`: ${must.join(", ")}`}
        </p>
      ) : null}
      {strong.length ? (
        <p className="hint">
          <span className="role-skill-label">{t.skillsCoachStrong}</span>
          {`: ${strong.join(", ")}`}
        </p>
      ) : null}
      <div className="insights-links">
        {courses.slice(0, 3).map((course) => {
          const url = String(course?.url || "").trim();
          const label = String(course?.skill || course?.slug || t.recommendationsGapCourse).trim();
          if (!url) return null;
          return (
            <a key={url} className="btn small" href={url} target="_blank" rel="noreferrer">
              {label}
            </a>
          );
        })}
        {pathId ? <CareerPathLink t={t} pathId={pathId} /> : null}
        <a className="btn small" href={hrefFor(locale, { mode: "recommendations" })}>
          {t.recommendationsOpen}
        </a>
      </div>
    </section>
  );
}

function NearMissSection({ t, locale, items }) {
  if (!Array.isArray(items) || items.length === 0) {
    return (
      <section className="insights-block">
        <h2>{t.insightsNearTitle}</h2>
        <p className="hint">{t.insightsNearEmpty}</p>
      </section>
    );
  }
  return (
    <section className="insights-block">
      <h2>{t.insightsNearTitle}</h2>
      <ul className="insights-near-list">
        {items.map((item, index) => {
          const pct = scorePct(item.score);
          const href = resolveHref(locale, item.cta_href) || hrefFor(locale, { jobId: item.job_id });
          const title = String(item.job_title || "").trim() || "—";
          const key = `${item.job_id || title}-${index}`;
          return (
            <li key={key} className="insights-near-item">
              <div className="insights-near-top">
                {pct !== null ? <span className="notice-score">{pct}%</span> : null}
                <a href={href}>
                  <strong>{title}</strong>
                </a>
              </div>
              <RoleSkillParts t={t} have={item.have} missing={item.missing} />
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function GrowthSection({ t, courses, roadmap }) {
  const list = Array.isArray(courses) ? courses : [];
  const roads = Array.isArray(roadmap) ? roadmap : [];
  if (!list.length && !roads.length) {
    return (
      <section className="insights-block">
        <h2>{t.insightsGrowthTitle}</h2>
        <p className="hint">{t.insightsGrowthEmpty}</p>
      </section>
    );
  }
  return (
    <section className="insights-block">
      <h2>{t.insightsGrowthTitle}</h2>
      {list.length ? (
        <ul className="insights-course-list">
          {list.map((course) => {
            const url = String(course?.url || "").trim();
            const label = String(course?.skill || course?.slug || t.recommendationsGapCourse).trim();
            if (!url) return null;
            return (
              <li key={url}>
                <a href={url} target="_blank" rel="noreferrer">
                  {label}
                </a>
              </li>
            );
          })}
        </ul>
      ) : null}
      {roads.length ? (
        <div className="notice-roadmap">
          <p className="hint notice-roadmap-title">{t.noticeRoadmapTitle}</p>
          <ul className="notice-roadmap-list">
            {roads.slice(0, 5).map((entry) => {
              const skill = String(entry?.skill || "").trim();
              const steps = Array.isArray(entry?.steps) ? entry.steps.filter(Boolean) : [];
              return (
                <li key={skill || steps[0]}>
                  {skill ? <strong>{skill}</strong> : null}
                  {entry?.coming_soon ? <span className="hint"> — {t.noticeComingSoon}</span> : null}
                  {steps.length ? (
                    <ol>
                      {steps.slice(0, 3).map((step) => (
                        <li key={String(step)}>{String(step)}</li>
                      ))}
                    </ol>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function Insights({ locale, initialInsights = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seeded = initialInsights && typeof initialInsights === "object";
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [data, setData] = useState(() => (seeded ? initialInsights : null));
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe.authenticated ? initialMe : null);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((payload) => {
        if (!cancelled) setMe(payload?.authenticated ? payload : null);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  useEffect(() => {
    if (!me?.authenticated || !(me.candidate || me.staff)) return undefined;
    if (seeded) return undefined;
    let cancelled = false;
    const lang = locale === "en" || locale === "ru" ? locale : "az";
    fetch(`/api/auth/me/insights?lang=${encodeURIComponent(lang)}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((payload) => {
        if (cancelled || !payload) return;
        setData(payload);
      })
      .catch(() => {
        if (!cancelled) setError(t.loadError);
      });
    return () => {
      cancelled = true;
    };
  }, [me, seeded, locale, t.loadError]);

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  return (
    <Shell locale={locale} mode="insights">
      {allowed ? (
        <div className="cabinet insights-page">
          <div className="cabinet-head">
            <div>
              <h1>{t.insightsTitle}</h1>
              <p className="lede">{t.insightsLede}</p>
            </div>
          </div>
          {error ? <p className="note">{error}</p> : null}
          {data && data.matching_consent === false ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}
          <CoachSection t={t} locale={locale} coach={data?.coach} />
          <NearMissSection t={t} locale={locale} items={data?.near_misses} />
          <GrowthSection t={t} courses={data?.academy_courses} roadmap={data?.roadmap} />
          <p className="hint">
            <a href={hrefFor(locale, { mode: "emailSettings" })}>{t.emailSettingsOpen}</a>
            {" · "}
            <a href={hrefFor(locale, { mode: "notifications" })}>{t.notifications}</a>
          </p>
        </div>
      ) : me === undefined ? null : (
        <section className="empty profile-gate">
          <h1>{t.insightsTitle}</h1>
          <p className="lede">{t.insightsGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "insights" })} />
        </section>
      )}
    </Shell>
  );
}
