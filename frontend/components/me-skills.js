"use client";

import { useEffect, useState } from "react";
import {
  academyCareerPathUrl,
  academyCourseLabel,
  academyCourseUrl,
} from "../lib/academy-urls";
import { hrefFor, text } from "../lib/copy";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const GROWTH_CAP_PCT = 300;
const MAX_COURSE_LINKS = 2;

function countSkills(items) {
  if (!Array.isArray(items)) return 0;
  return items.filter((item) => {
    if (typeof item === "string") return Boolean(item.trim());
    if (item && typeof item === "object") return Boolean(String(item.name || "").trim());
    return false;
  }).length;
}

function sharePct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

function growthLabel(t, growth) {
  if (typeof growth !== "number" || Number.isNaN(growth)) return null;
  const pct = Math.round(growth * 100);
  if (!Number.isFinite(pct) || pct === 0) return null;
  if (Math.abs(pct) > GROWTH_CAP_PCT) {
    return pct > 0 ? t.recommendationsGapGrowthSurge : t.recommendationsGapGrowthDrop;
  }
  return t.recommendationsGapGrowth(pct);
}

function CareerPathLink({ t, pathId }) {
  const href = academyCareerPathUrl(pathId);
  if (!href) return null;
  return (
    <a className="skills-career-link" href={href} target="_blank" rel="noreferrer">
      {t.recommendationsGapCareerPath}
    </a>
  );
}

function AcademyCourseLinks({ item }) {
  const courses = Array.isArray(item.academy_courses)
    ? item.academy_courses.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
  if (!courses.length) return null;
  const visible = courses.slice(0, MAX_COURSE_LINKS);
  const extra = courses.length - visible.length;
  return (
    <span className="skills-course-links">
      {visible.map((courseId) => {
        const href = academyCourseUrl(courseId);
        if (!href) return null;
        const label = academyCourseLabel(courseId);
        return (
          <a
            key={courseId}
            className="skills-course-link"
            href={href}
            target="_blank"
            rel="noreferrer"
            title={label}
          >
            {label}
          </a>
        );
      })}
      {extra > 0 ? (
        <span className="skills-course-more" title={courses.slice(MAX_COURSE_LINKS).map(academyCourseLabel).join(", ")}>
          +{extra}
        </span>
      ) : null}
    </span>
  );
}

function OftenWith({ t, item }) {
  const hit = item?.often_with;
  if (!hit || typeof hit !== "object") return null;
  const base = String(hit.base_name || "").trim();
  const pct = sharePct(hit.share);
  if (!base || pct === null) return null;
  return <span className="hint">{t.recommendationsGapOftenWith(base, pct)}</span>;
}

function SkillShareBar({ share }) {
  const pct = sharePct(share);
  if (pct === null) return null;
  const width = Math.max(4, Math.min(100, pct));
  return (
    <div className="skills-share" title={`${pct}%`}>
      <div className="skills-share-track" aria-hidden="true">
        <div className="skills-share-fill" style={{ width: `${width}%` }} />
      </div>
      <span className="skills-share-label">{pct}%</span>
    </div>
  );
}

function SkillRow({ t, item, tone }) {
  const growth = growthLabel(t, item.growth);
  const showCourses = tone === "missing";
  return (
    <li className={`skills-row skills-row-${tone}`}>
      <div className="skills-row-top">
        <strong className="skills-row-name">{item.name}</strong>
        {showCourses ? <AcademyCourseLinks item={item} /> : null}
      </div>
      <SkillShareBar share={item.share} />
      <div className="skills-row-meta">
        {growth ? <span className="hint">{growth}</span> : null}
        <OftenWith t={t} item={item} />
      </div>
    </li>
  );
}

export function MeSkills({ locale }) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const [me, setMe] = useState(undefined);
  const [roles, setRoles] = useState(null);
  const [gap, setGap] = useState(null);
  const [activeRole, setActiveRole] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff)) return undefined;
    let cancelled = false;
    fetch(`/api/auth/me/roles?lang=${lang}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((rolesPayload) => {
        if (cancelled) return;
        setRoles(rolesPayload);
        const topRole = rolesPayload?.roles?.[0]?.canonical_name || "";
        setActiveRole(topRole);
      })
      .catch(() => {
        if (!cancelled) setRoles(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !activeRole) {
      setGap(null);
      return undefined;
    }
    let cancelled = false;
    const qs = new URLSearchParams({ lang, role: activeRole });
    fetch(`/api/auth/me/skill-gap?${qs}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setGap(data);
      })
      .catch(() => {
        if (!cancelled) setGap(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, activeRole]);

  const consentOk = roles?.matching_consent !== false;
  const candidate = Boolean(me?.candidate || me?.staff);
  const missing = Array.isArray(gap?.missing) ? gap.missing : [];
  const have = Array.isArray(gap?.have) ? gap.have : [];
  const hasGap = missing.length > 0 || have.length > 0;

  return (
    <Shell locale={locale} mode="skills">
      {me === undefined ? (
        <section className="empty">
          <p className="lede">…</p>
        </section>
      ) : candidate ? (
        <div className="cabinet skills-page">
          <div className="skills-head">
            <h1>{t.skillsTitle}</h1>
            <p className="lede">{t.skillsLede}</p>
            <p className="hint skills-disclaimer">{t.trendsDisclaimer}</p>
          </div>

          {!consentOk ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          <div className="skills-layout">
            <section className="skills-roles" aria-label={t.skillsTargetRole}>
              <h2>{t.skillsTargetRole}</h2>
              {!roles?.roles?.length ? (
                <p className="hint">
                  {t.recommendationsEmptyRoles}{" "}
                  <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
                </p>
              ) : (
                <ul className="skills-role-list">
                  {roles.roles.map((role) => {
                    const on = activeRole === role.canonical_name;
                    const score =
                      typeof role.score === "number" ? Math.round(role.score * 100) : null;
                    const haveN = countSkills(role.have);
                    const missN = countSkills(role.missing);
                    return (
                      <li key={role.canonical_name}>
                        <button
                          type="button"
                          className={on ? "skills-role-pick on" : "skills-role-pick"}
                          onClick={() => setActiveRole(role.canonical_name)}
                          aria-pressed={on}
                        >
                          <span className="skills-role-score" aria-hidden={score === null}>
                            {score !== null ? `${score}%` : "—"}
                          </span>
                          <span className="skills-role-body">
                            <strong>{role.canonical_name}</strong>
                            <span className="hint">
                              {[
                                role.category,
                                haveN ? t.skillsHaveCount(haveN) : null,
                                missN ? t.skillsMissingCount(missN) : null,
                              ]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            {activeRole ? (
              <section className="skills-detail" aria-live="polite">
                <header className="skills-detail-head">
                  <div>
                    <p className="skills-detail-kicker">{t.recommendationsGap}</p>
                    <h2>{activeRole}</h2>
                  </div>
                  <CareerPathLink t={t} pathId={gap?.academy_career_path} />
                </header>

                {!hasGap ? (
                  <p className="hint">{t.recommendationsGapEmpty}</p>
                ) : (
                  <div className="skills-panels">
                    <div className="skills-panel skills-panel-missing">
                      <h3>
                        {t.recommendationsGapLearn}
                        <span className="skills-panel-count">{missing.length}</span>
                      </h3>
                      {!missing.length ? (
                        <p className="hint">{t.skillsMissingEmpty}</p>
                      ) : (
                        <ul className="skills-rows">
                          {missing.map((item) => (
                            <SkillRow key={`missing-${item.name}`} t={t} item={item} tone="missing" />
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="skills-panel skills-panel-have">
                      <h3>
                        {t.skillsHave}
                        <span className="skills-panel-count">{have.length}</span>
                      </h3>
                      {!have.length ? (
                        <p className="hint">{t.skillsHaveEmpty}</p>
                      ) : (
                        <ul className="skills-rows">
                          {have.map((item) => (
                            <SkillRow key={`have-${item.name}`} t={t} item={item} tone="have" />
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                )}
              </section>
            ) : null}
          </div>

          <p className="hint skills-footer">
            <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
            {" · "}
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
          </p>
        </div>
      ) : (
        <section className="empty profile-gate">
          <h1>{t.skillsTitle}</h1>
          <p className="lede">{t.skillsGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "skills" })} />
        </section>
      )}
    </Shell>
  );
}
