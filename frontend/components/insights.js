"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { RoleSkillParts } from "./role-skill-parts";
import { RoadmapPreview } from "./roadmap";
import { CareerPathLink } from "./skill-gap-bits";
import { PageChrome } from "./page-chrome";
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
    return (
      <section className="h2-panel">
        <h2 className="h2-panel-title">{t.insightsCoachTitle}</h2>
        <p className="hint">{t.insightsCoachEmpty}</p>
      </section>
    );
  }
  const role = String(coach.role || "").trim();
  const title = String(coach.ai_title || "").trim() || (role ? t.insightsCoachRole(role) : t.insightsCoachTitle);
  const body = String(coach.ai_body || "").trim();
  const must = skillNames(coach.must_learn);
  const strong = skillNames(coach.already_strong);
  const courses = Array.isArray(coach.academy_courses) ? coach.academy_courses : [];
  const pathId = String(coach.academy_career_path || "").trim();

  return (
    <section className="h2-panel">
      <h2 className="h2-panel-title">{t.insightsCoachTitle}</h2>
      <p className="h2-candidate-lead">{title}</p>
      {body ? <p className="hint">{body}</p> : null}
      <RoleSkillParts t={t} have={strong} missing={must} />
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
        <a className="btn small ink" href={hrefFor(locale, { mode: "recommendations" })}>
          {t.recommendationsOpen}
        </a>
      </div>
    </section>
  );
}

function NearMissItem({ t, locale, item }) {
  const pct = scorePct(item.score);
  const href = resolveHref(locale, item.cta_href) || hrefFor(locale, { jobId: item.job_id });
  const title = String(item.job_title || "").trim() || "—";
  return (
    <li className="insights-near-item">
      <div className="insights-near-top">
        {pct !== null ? <span className="notice-score">{pct}%</span> : null}
        <a href={href}>
          <strong>{title}</strong>
        </a>
      </div>
      <RoleSkillParts t={t} have={item.have} missing={item.missing} limit={4} />
    </li>
  );
}

const NEAR_PREVIEW = 3;

function NearMissSection({ t, locale, items }) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) {
    return (
      <section className="h2-panel">
        <h2 className="h2-panel-title">{t.insightsNearTitle}</h2>
        <p className="hint insights-near-empty">{t.insightsNearEmpty}</p>
      </section>
    );
  }
  const preview = list.slice(0, NEAR_PREVIEW);
  const more = list.length > NEAR_PREVIEW;
  return (
    <section className="h2-panel">
      <h2 className="h2-panel-title">{t.insightsNearTitle}</h2>
      <ul className="insights-near-list">
        {preview.map((item, index) => (
          <NearMissItem
            key={`${item.job_id || item.job_title || "near"}-${index}`}
            t={t}
            locale={locale}
            item={item}
          />
        ))}
      </ul>
      {more ? (
        <div className="insights-links">
          <a className="btn small" href={hrefFor(locale, { mode: "insightsNear" })}>
            {t.insightsNearOpenCount(list.length)}
          </a>
        </div>
      ) : null}
    </section>
  );
}

function GrowthSection({ t, locale, courses, roadmap, learningRoadmap }) {
  const list = Array.isArray(courses) ? courses : [];
  const roads = Array.isArray(roadmap) ? roadmap : [];
  const rich = learningRoadmap && typeof learningRoadmap === "object" ? learningRoadmap : null;
  const hasRich = Boolean(rich && (rich.hero || (rich.milestones || []).length));
  if (!list.length && !roads.length && !hasRich) {
    return (
      <section className="h2-panel">
        <h2 className="h2-panel-title">{t.insightsGrowthTitle}</h2>
        <p className="hint">{t.insightsGrowthEmpty}</p>
      </section>
    );
  }
  return (
    <section className="h2-panel">
      <h2 className="h2-panel-title">{t.insightsGrowthTitle}</h2>
      {hasRich ? <RoadmapPreview t={t} locale={locale} roadmap={rich} /> : null}
      {!hasRich && list.length ? (
        <ul className="insights-course-list">
          {list.slice(0, 4).map((course) => {
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
      {!hasRich && roads.length ? (
        <div className="notice-roadmap">
          {list.length ? (
            <p className="hint notice-roadmap-title">{t.noticeRoadmapTitle}</p>
          ) : null}
          <ul className="notice-roadmap-list">
            {roads.slice(0, 3).map((entry) => {
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
      {!hasRich ? (
        <div className="insights-links">
          <a className="btn small ink" href={hrefFor(locale, { mode: "insightsRoadmap" })}>
            {t.roadmapOpenFull}
          </a>
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
        <div className="h2-candidate insights-page">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.insightsTitle}
          />
          {error ? <p className="note">{error}</p> : null}
          {data && data.matching_consent === false ? (
            <p className="hint h2-consent-banner">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}
          <div className="insights-layout">
            <div className="insights-main">
              <CoachSection t={t} locale={locale} coach={data?.coach} />
            </div>
            <aside className="insights-aside">
              <NearMissSection t={t} locale={locale} items={data?.near_misses} />
              <GrowthSection
                t={t}
                locale={locale}
                courses={data?.academy_courses}
                roadmap={data?.roadmap}
                learningRoadmap={data?.learning_roadmap}
              />
            </aside>
          </div>
          <p className="hint h2-candidate-footer">
            <a href={hrefFor(locale, { mode: "emailSettings" })}>{t.emailSettingsOpen}</a>
            {" · "}
            <a href={hrefFor(locale, { mode: "notifications" })}>{t.notifications}</a>
          </p>
        </div>
      ) : me === undefined ? null : (
        <div className="h2-candidate">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.insightsTitle} />
          <div className="h2-empty h2-gate">
            <p>{t.insightsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "insightsRoadmap" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}

/** Full near-miss list opened from insights overview. */
export function InsightsNear({ locale, initialInsights = null }) {
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
  const items = Array.isArray(data?.near_misses) ? data.near_misses : [];

  return (
    <Shell locale={locale} mode="insights">
      {allowed ? (
        <div className="h2-candidate insights-page insights-near-page">
          <PageChrome
            backHref={hrefFor(locale, { mode: "insightsRoadmap" })}
            backLabel={t.roadmapTitle}
            title={t.insightsNearTitle}
            count={items.length || null}
          />
          {error ? <p className="note">{error}</p> : null}
          {data && data.matching_consent === false ? (
            <p className="hint h2-consent-banner">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}
          <section className="h2-panel">
            {!items.length ? (
              <p className="hint">{t.insightsNearEmpty}</p>
            ) : (
              <ul className="insights-near-list">
                {items.map((item, index) => (
                  <NearMissItem
                    key={`${item.job_id || item.job_title || "near"}-${index}`}
                    t={t}
                    locale={locale}
                    item={item}
                  />
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : me === undefined ? null : (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale, { mode: "insightsRoadmap" })}
            backLabel={t.roadmapTitle}
            title={t.insightsNearTitle}
          />
          <div className="h2-empty h2-gate">
            <p>{t.insightsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "insightsNear" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
