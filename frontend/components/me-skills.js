"use client";

import { useEffect, useState } from "react";
import { academyCourseUrl, hrefFor, text } from "../lib/copy";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

function SkillMeta({ t, item }) {
  const sharePct = typeof item.share === "number" ? Math.round(item.share * 100) : null;
  const growthPct = typeof item.growth === "number" ? Math.round(item.growth * 100) : null;
  if (sharePct === null && growthPct === null) return null;
  return (
    <span className="hint">
      {" · "}
      {[
        sharePct !== null ? t.recommendationsGapShare(sharePct) : null,
        growthPct !== null ? t.recommendationsGapGrowth(growthPct) : null,
      ]
        .filter(Boolean)
        .join(" · ")}
    </span>
  );
}

function AcademyLinks({ t, item }) {
  const courses = Array.isArray(item.academy_courses)
    ? item.academy_courses.filter(Boolean)
    : [];
  if (!courses.length) return null;
  return (
    <span className="hint">
      {" · "}
      {courses.map((courseId, index) => {
        const href = academyCourseUrl(courseId);
        if (!href) return null;
        return (
          <span key={String(courseId)}>
            {index > 0 ? ", " : null}
            <a href={href} target="_blank" rel="noreferrer">
              {t.recommendationsGapCourse}
            </a>
          </span>
        );
      })}
    </span>
  );
}

function OftenWith({ t, item }) {
  const hit = item?.often_with;
  if (!hit || typeof hit !== "object") return null;
  const base = String(hit.base_name || "").trim();
  const sharePct = typeof hit.share === "number" ? Math.round(hit.share * 100) : null;
  if (!base || sharePct === null) return null;
  return (
    <span className="hint">
      {" · "}
      {t.recommendationsGapOftenWith(base, sharePct)}
    </span>
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

  return (
    <Shell locale={locale} mode="skills">
      {me === undefined ? (
        <section className="empty">
          <p className="lede">…</p>
        </section>
      ) : candidate ? (
        <div className="cabinet recommendations-page">
          <div className="cabinet-form-head">
            <h1>{t.skillsTitle}</h1>
            <p className="lede">{t.skillsLede}</p>
          </div>

          {!consentOk ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          <p className="hint trends-disclaimer">{t.trendsDisclaimer}</p>

          <section className="recommendations-section">
            <h2>{t.skillsTargetRole}</h2>
            {!roles?.roles?.length ? (
              <p className="hint">
                {t.recommendationsEmptyRoles}{" "}
                <a href={hrefFor(locale, { mode: "recommendations" })}>{t.recommendationsOpen}</a>
              </p>
            ) : (
              <ul className="role-suggest-list">
                {roles.roles.map((role) => (
                  <li key={role.canonical_name} className="role-suggest-item">
                    <button
                      type="button"
                      className={
                        activeRole === role.canonical_name
                          ? "role-suggest-pick on"
                          : "role-suggest-pick"
                      }
                      onClick={() => setActiveRole(role.canonical_name)}
                    >
                      <span className="role-suggest-head">
                        <strong>{role.canonical_name}</strong>
                        <span className="hint">
                          {role.category}
                          {typeof role.score === "number"
                            ? ` · ${t.recommendationsScore(role.score)}`
                            : ""}
                        </span>
                      </span>
                      {role.explanation ? <p className="hint">{role.explanation}</p> : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {activeRole ? (
            <section className="recommendations-section">
              <h2>
                {t.recommendationsGap}: {activeRole}
              </h2>
              {!gap?.missing?.length && !gap?.have?.length ? (
                <p className="hint">{t.recommendationsGapEmpty}</p>
              ) : (
                <>
                  {gap?.explanation ? <p className="hint">{gap.explanation}</p> : null}
                  {gap?.missing?.length ? (
                    <ul className="gap-list">
                      <li className="hint">{t.recommendationsGapLearn}</li>
                      {gap.missing.map((item) => (
                        <li key={`missing-${item.name}`}>
                          <strong>{item.name}</strong>
                          <SkillMeta t={t} item={item} />
                          <OftenWith t={t} item={item} />
                          <AcademyLinks t={t} item={item} />
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {gap?.have?.length ? (
                    <ul className="gap-list">
                      <li className="hint">{t.skillsHave}</li>
                      {gap.have.map((item) => (
                        <li key={`have-${item.name}`}>
                          <strong>{item.name}</strong>
                          <SkillMeta t={t} item={item} />
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              )}
            </section>
          ) : null}

          <p className="hint">
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
