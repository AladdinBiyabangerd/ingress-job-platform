"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
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

function CtaLink({ locale, cta, className = "btn ink", children }) {
  if (!cta || typeof cta !== "object") return null;
  const href = resolveHref(locale, cta.href);
  if (!href) return null;
  const label = children || String(cta.label || "").trim();
  if (!label) return null;
  const external = Boolean(cta.external) || href.startsWith("http");
  return (
    <a
      className={className}
      href={href}
      {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
    >
      {label}
    </a>
  );
}

export function SkillPills({ have = [], missing = [], limit = 8 }) {
  const haveList = (Array.isArray(have) ? have : []).map(String).filter(Boolean).slice(0, limit);
  const missList = (Array.isArray(missing) ? missing : []).map(String).filter(Boolean).slice(0, limit);
  if (!haveList.length && !missList.length) return null;
  return (
    <ul className="roadmap-pills">
      {haveList.map((name) => (
        <li key={`have-${name}`} className="roadmap-pill is-have">
          <span className="roadmap-pill-text">{name}</span>
        </li>
      ))}
      {missList.map((name) => (
        <li key={`miss-${name}`} className="roadmap-pill is-missing">
          <span className="roadmap-pill-text">{name}</span>
        </li>
      ))}
    </ul>
  );
}

function RoadmapArt() {
  return (
    <div className="roadmap-art" aria-hidden="true">
      <svg viewBox="0 0 160 140" width="160" height="140" fill="none">
        <rect x="48" y="28" width="64" height="84" rx="10" fill="#dfe7ff" stroke="#9db0ff" strokeWidth="2" />
        <rect x="58" y="40" width="44" height="10" rx="3" fill="#b8c8ff" />
        <rect x="58" y="56" width="44" height="10" rx="3" fill="#b8c8ff" />
        <rect x="58" y="72" width="44" height="10" rx="3" fill="#b8c8ff" />
        <rect x="58" y="88" width="28" height="10" rx="3" fill="#9db0ff" />
        <circle cx="36" cy="48" r="10" fill="#c8d4ff" stroke="#7f96f5" strokeWidth="2" />
        <circle cx="128" cy="64" r="12" fill="#c8d4ff" stroke="#7f96f5" strokeWidth="2" />
        <circle cx="42" cy="100" r="8" fill="#dfe7ff" stroke="#9db0ff" strokeWidth="2" />
        <path d="M36 48h12M128 64H112M42 100h16" stroke="#7f96f5" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </div>
  );
}

/** Compact Insights aside preview of the rich learning roadmap. */
export function RoadmapPreview({ t, locale, roadmap }) {
  if (!roadmap || typeof roadmap !== "object") return null;
  const hero = roadmap.hero && typeof roadmap.hero === "object" ? roadmap.hero : null;
  const title = String(hero?.title || "").trim();
  const lede = String(hero?.lede || hero?.motivation || "").trim();
  const open = roadmap.cta_open || {
    label: t.roadmapOpenFull,
    href: hrefFor(locale, { mode: "insightsRoadmap" }),
    external: false,
  };
  const pending = roadmap.status === "pending";

  return (
    <div className="roadmap-preview">
      {pending ? <p className="hint roadmap-preview-pending">{t.roadmapPending}</p> : null}
      {title ? <p className="roadmap-preview-title">{title}</p> : null}
      {lede ? <p className="hint roadmap-preview-lede">{lede}</p> : null}
      <div className="roadmap-preview-actions">
        <CtaLink locale={locale} cta={open} className="btn small ink">
          {t.roadmapOpenFull}
        </CtaLink>
        {hero?.cta?.href && String(hero.cta.href) !== String(open.href) ? (
          <CtaLink locale={locale} cta={hero.cta} className="btn small" />
        ) : null}
      </div>
    </div>
  );
}

function WeekCard({ t, locale, section }) {
  const items = Array.isArray(section?.items) ? section.items : [];
  return (
    <section className="roadmap-card">
      <h2 className="roadmap-card-title">{t.roadmapThisWeek}</h2>
      {items.length ? (
        <ul className="roadmap-check-list">
          {items.slice(0, 5).map((item, index) => {
            const label = String(item?.text || "").trim();
            if (!label) return null;
            return (
              <li key={`${item?.milestone_id || label}-${index}`}>
                <span className="roadmap-check" aria-hidden="true" />
                <span className="roadmap-check-text">{label}</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="hint">{t.roadmapSectionEmpty}</p>
      )}
      <CtaLink locale={locale} cta={section?.cta} className="btn ink roadmap-card-cta" />
    </section>
  );
}

function NextCard({ t, locale, section }) {
  const items = Array.isArray(section?.items) ? section.items : [];
  return (
    <section className="roadmap-card">
      <h2 className="roadmap-card-title">{t.roadmapNext}</h2>
      {items.length ? (
        <ul className="roadmap-next-list">
          {items.slice(0, 4).map((item, index) => {
            const title = String(item?.title || "").trim();
            const body = String(item?.body || "").trim();
            if (!title && !body) return null;
            return (
              <li key={`${item?.milestone_id || title}-${index}`}>
                {title ? <strong className="roadmap-next-title">{title}</strong> : null}
                {body ? <p className="hint roadmap-next-body">{body}</p> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="hint">{t.roadmapSectionEmpty}</p>
      )}
      <CtaLink locale={locale} cta={section?.cta} className="btn roadmap-card-cta" />
    </section>
  );
}

function PathCard({ t, locale, section }) {
  if (!section) {
    return (
      <section className="roadmap-card">
        <h2 className="roadmap-card-title">{t.roadmapAcademyPath}</h2>
        <p className="hint">{t.roadmapPathEmpty}</p>
      </section>
    );
  }
  const steps = Array.isArray(section.steps) ? section.steps : [];
  return (
    <section className="roadmap-card">
      <h2 className="roadmap-card-title">{t.roadmapAcademyPath}</h2>
      {steps.length ? (
        <ol className="roadmap-path-list">
          {steps.slice(0, 5).map((step, index) => {
            const title = String(step?.title || "").trim();
            if (!title) return null;
            const n = step?.n || index + 1;
            return (
              <li key={`${n}-${title}`}>
                <span className="roadmap-path-n">{n}.</span>
                <span className="roadmap-path-text">{title}</span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="hint">{t.roadmapPathEmpty}</p>
      )}
      <CtaLink locale={locale} cta={section.cta} className="btn ink roadmap-card-cta" />
    </section>
  );
}

function courseFallbackWeek(courses) {
  const list = Array.isArray(courses) ? courses : [];
  const items = list
    .slice(0, 4)
    .map((course) => {
      const text = String(course?.skill || course?.slug || "").trim();
      return text ? { text, done: false, milestone_id: "" } : null;
    })
    .filter(Boolean);
  if (!items.length) return null;
  const first = list[0];
  const href = typeof first?.url === "string" ? first.url : "";
  return {
    items,
    cta: href
      ? { label: items[0].text, href, external: href.startsWith("http") }
      : null,
  };
}

function RoadmapBento({ t, locale, roadmap, insights = null }) {
  const profileStatus = String(insights?.profile_status || "").trim();
  const matchingConsent = insights?.matching_consent !== false;
  const needsProfile = Boolean(insights) && profileStatus && profileStatus !== "confirmed";
  const needsConsent = Boolean(insights) && insights.matching_consent === false;

  if (needsProfile || needsConsent) {
    return (
      <section className="roadmap-hero roadmap-hero-empty">
        <div className="roadmap-hero-copy">
          <h2 className="roadmap-hero-title">{t.roadmapGateTitle}</h2>
          <p className="hint">{t.roadmapGateLede}</p>
          <div className="roadmap-preview-actions">
            {needsProfile ? (
              <a className="btn ink" href={hrefFor(locale, { mode: "profileReview" })}>
                {t.roadmapGateProfileCta}
              </a>
            ) : null}
            {needsConsent ? (
              <a className="btn" href={hrefFor(locale, { mode: "profile" })}>
                {t.roadmapGateConsentCta}
              </a>
            ) : null}
          </div>
        </div>
      </section>
    );
  }

  const hero = roadmap?.hero && typeof roadmap.hero === "object" ? roadmap.hero : {};
  const pending = roadmap?.status === "pending";
  const empty = !roadmap || roadmap.status === "empty";

  if (empty) {
    const emptyHref = matchingConsent
      ? hrefFor(locale, { mode: "recommendations" })
      : hrefFor(locale, { mode: "profile" });
    const emptyLabel = matchingConsent ? t.recommendationsOpen : t.roadmapGateConsentCta;
    return (
      <section className="roadmap-hero roadmap-hero-empty">
        <div className="roadmap-hero-copy">
          <h2 className="roadmap-hero-title">{t.roadmapEmptyTitle}</h2>
          <p className="hint">{t.roadmapEmptyLede}</p>
          <a className="btn ink" href={emptyHref}>
            {emptyLabel}
          </a>
        </div>
      </section>
    );
  }

  let weekSection = roadmap.this_week;
  const weekItems = Array.isArray(weekSection?.items) ? weekSection.items : [];
  if (!weekItems.length) {
    const fallback = courseFallbackWeek(insights?.academy_courses || roadmap?.academy_courses);
    if (fallback) weekSection = fallback;
  }

  return (
    <div className="roadmap-bento">
      <section className="roadmap-hero">
        <div className="roadmap-hero-copy">
          {pending ? <p className="hint roadmap-preview-pending">{t.roadmapPending}</p> : null}
          <h2 className="roadmap-hero-title">{String(hero.title || t.roadmapTitle)}</h2>
          {hero.lede ? <p className="roadmap-hero-lede">{hero.lede}</p> : null}
          {hero.motivation ? <p className="hint roadmap-hero-motivation">{hero.motivation}</p> : null}
          <SkillPills have={hero.have} missing={hero.missing} />
          <CtaLink locale={locale} cta={hero.cta} className="btn ink roadmap-hero-cta" />
        </div>
        <RoadmapArt />
      </section>
      <div className="roadmap-grid">
        <WeekCard t={t} locale={locale} section={weekSection} />
        <NextCard t={t} locale={locale} section={roadmap.next} />
        <PathCard t={t} locale={locale} section={roadmap.academy_path} />
      </div>
      <p className="hint roadmap-footer">
        {t.roadmapFooter}{" "}
        <a href="https://ingress.academy/" target="_blank" rel="noreferrer">
          Ingress Academy
        </a>
      </p>
    </div>
  );
}

export function InsightsRoadmap({ locale, initialInsights = null }) {
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

  // Brief poll only when roadmap is empty/pending (no readable milestones yet).
  useEffect(() => {
    if (!me?.authenticated || !(me.candidate || me.staff)) return undefined;
    const lr = data?.learning_roadmap;
    if (!lr || lr.status !== "pending") return undefined;
    let cancelled = false;
    let tries = 0;
    const lang = locale === "en" || locale === "ru" ? locale : "az";
    const timer = setInterval(() => {
      tries += 1;
      if (tries > 4) {
        clearInterval(timer);
        return;
      }
      fetch(`/api/auth/me/insights?lang=${encodeURIComponent(lang)}`, { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((payload) => {
          if (cancelled || !payload) return;
          setData(payload);
        })
        .catch(() => {});
    }, 2000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [me, data?.learning_roadmap?.status, locale]);

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));
  const roadmap = data?.learning_roadmap && typeof data.learning_roadmap === "object" ? data.learning_roadmap : null;

  return (
    <Shell locale={locale} mode="insights">
      {allowed ? (
        <div className="h2-candidate insights-page roadmap-page">
          <PageChrome
            backHref={hrefFor(locale, { mode: "recommendations" })}
            backLabel={t.recommendationsOpen}
            title={t.roadmapTitle}
          />
          {error ? <p className="note">{error}</p> : null}
          <RoadmapBento t={t} locale={locale} roadmap={roadmap} insights={data} />
        </div>
      ) : me === undefined ? null : (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale, { mode: "recommendations" })}
            backLabel={t.recommendationsOpen}
            title={t.roadmapTitle}
          />
          <div className="h2-empty h2-gate">
            <p>{t.insightsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "insightsRoadmap" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
