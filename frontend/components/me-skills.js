"use client";

import { useEffect, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { loadSkillGap } from "../lib/server/refresh";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";
import { CareerPathLink, SkillRow } from "./skill-gap-bits";

function countSkills(items) {
  if (!Array.isArray(items)) return 0;
  return items.filter((item) => {
    if (typeof item === "string") return Boolean(item.trim());
    if (item && typeof item === "object") return Boolean(String(item.name || "").trim());
    return false;
  }).length;
}

export function MeSkills({ locale, initialRoles = null, initialGap = null }) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const initialMe = useInitialMe();
  const seededRoles = initialRoles != null;
  const initialTopRole = initialRoles?.roles?.[0]?.canonical_name || "";
  const seededInitialGap = initialGap != null;
  const ssrGapPending = useRef(seededInitialGap);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [roles, setRoles] = useState(initialRoles);
  const [gap, setGap] = useState(initialGap);
  const [activeRole, setActiveRole] = useState(initialTopRole);

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe.authenticated ? initialMe : null);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data?.authenticated ? data : null);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff)) return undefined;
    if (seededRoles) return undefined;
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
  }, [me, lang, seededRoles]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !activeRole) {
      if (!ssrGapPending.current) setGap(null);
      return undefined;
    }
    if (ssrGapPending.current && activeRole === initialTopRole) {
      ssrGapPending.current = false;
      return undefined;
    }
    ssrGapPending.current = false;
    let cancelled = false;
    loadSkillGap(lang, activeRole)
      .then((data) => {
        if (!cancelled) setGap(data);
      })
      .catch(() => {
        if (!cancelled) setGap(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, activeRole, initialTopRole]);

  const consentOk = roles?.matching_consent !== false;
  const candidate = Boolean(me?.candidate || me?.staff);
  const missing = Array.isArray(gap?.missing) ? gap.missing : [];
  const have = Array.isArray(gap?.have) ? gap.have : [];
  const hasGap = missing.length > 0 || have.length > 0;
  const coach = gap?.coach && typeof gap.coach === "object" ? gap.coach : null;
  const mustLearn = Array.isArray(coach?.must_learn) ? coach.must_learn : [];
  const alreadyStrong = Array.isArray(coach?.already_strong) ? coach.already_strong : [];
  const transferable = Array.isArray(coach?.transferable) ? coach.transferable : [];
  const hasCoach = Boolean(coach?.fit_summary);

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

                {hasCoach ? (
                  <div className="skills-coach">
                    <h3>{t.skillsCoachTitle}</h3>
                    <p className="lede skills-coach-summary">{coach.fit_summary}</p>
                    {mustLearn.length ? (
                      <div className="skills-coach-block">
                        <h4>{t.skillsCoachMustLearn}</h4>
                        <ul className="skills-coach-list">
                          {mustLearn.map((item) => (
                            <li key={`coach-learn-${item.skill}`}>
                              <strong>{item.skill}</strong>
                              {item.why ? <span className="hint"> — {item.why}</span> : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {alreadyStrong.length ? (
                      <div className="skills-coach-block">
                        <h4>{t.skillsCoachStrong}</h4>
                        <p className="hint">{alreadyStrong.join(" · ")}</p>
                      </div>
                    ) : null}
                    {transferable.length ? (
                      <div className="skills-coach-block">
                        <h4>{t.skillsCoachTransferable}</h4>
                        <ul className="skills-coach-list">
                          {transferable.map((item) => (
                            <li key={`xfer-${item.from}-${item.to}`}>
                              <strong>{t.skillsCoachTransfer(item.from, item.to)}</strong>
                              {item.note ? <span className="hint"> — {item.note}</span> : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}

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
