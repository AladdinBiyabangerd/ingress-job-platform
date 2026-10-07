"use client";

import { useEffect, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { loadSkillGap } from "../lib/server/refresh";
import { CareerPathLink, SkillRow } from "./skill-gap-bits";
import { Pager } from "./pager";
import { RegisterChoice } from "./register-choice";
import { RoleSkillParts } from "./role-skill-parts";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const REASONS = ["location", "seniority", "technology", "salary"];
const MATCHES_FETCH_LIMIT = 10;

function countSkills(items) {
  if (!Array.isArray(items)) return 0;
  return items.filter((item) => {
    if (typeof item === "string") return Boolean(item.trim());
    if (item && typeof item === "object") return Boolean(String(item.name || "").trim());
    return false;
  }).length;
}

function reasonLabel(t, reason) {
  if (reason === "location") return t.recommendationsReasonLocation;
  if (reason === "seniority") return t.recommendationsReasonSeniority;
  if (reason === "technology") return t.recommendationsReasonTechnology;
  if (reason === "salary") return t.recommendationsReasonSalary;
  return reason;
}

function jobMeta(t, job) {
  return [job.company, job.city, job.remote ? t.placeRemote : null, job.salary]
    .map((part) => String(part || "").trim())
    .filter(Boolean)
    .join(" · ");
}

function MatchJob({ t, locale, job, busy, onFeedback }) {
  const score = typeof job.score === "number" ? Math.round(job.score * 100) : null;
  const meta = jobMeta(t, job);
  const votedDown = job.feedback?.vote === "down";
  const showReason = votedDown || !job.feedback;

  return (
    <li className="reco-job">
      <div className="reco-job-top">
        <span className="reco-job-score" aria-hidden={score === null}>
          {score !== null ? `${score}%` : "—"}
        </span>
        <div className="reco-job-body">
          <a className="reco-job-title" href={hrefFor(locale, { jobId: job.job_id })}>
            <strong>{job.title}</strong>
          </a>
          {meta ? <span className="hint">{meta}</span> : null}
        </div>
      </div>

      {job.explanation ? <p className="hint reco-job-explain">{job.explanation}</p> : null}
      <RoleSkillParts t={t} have={job.have} missing={job.missing} />

      <div className="reco-job-actions">
        <button
          type="button"
          className={job.feedback?.vote === "up" ? "btn small on" : "btn small"}
          disabled={busy}
          onClick={() => onFeedback(job.job_id, "up")}
        >
          {t.recommendationsUp}
        </button>
        <button
          type="button"
          className={votedDown ? "btn small on" : "btn small"}
          disabled={busy}
          onClick={() => onFeedback(job.job_id, "down")}
        >
          {t.recommendationsDown}
        </button>
        {showReason ? (
          <label className="reco-job-reason">
            <span className="hint">{t.recommendationsReason}</span>
            <select
              value={job.feedback?.reason || ""}
              disabled={busy}
              onChange={(event) => {
                const reason = event.target.value;
                if (!reason) return;
                onFeedback(job.job_id, "down", reason);
              }}
            >
              <option value="">—</option>
              {REASONS.map((reason) => (
                <option key={reason} value={reason}>
                  {reasonLabel(t, reason)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
    </li>
  );
}

export function Recommendations({
  locale,
  initialRoles = null,
  initialMatches = null,
  initialGap = null,
}) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const initialMe = useInitialMe();
  const seededCatalog = initialRoles != null && initialMatches != null;
  const initialTopRole = initialRoles?.roles?.[0]?.canonical_name || "";
  const seededInitialGap = initialGap != null;
  const ssrGapPending = useRef(seededInitialGap);
  const ssrMatchesPending = useRef(seededCatalog);
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [roles, setRoles] = useState(initialRoles);
  const [matches, setMatches] = useState(initialMatches);
  const [activeRole, setActiveRole] = useState(initialTopRole);
  const [gap, setGap] = useState(initialGap);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

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
    if (seededCatalog) return undefined;
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
  }, [me, lang, seededCatalog]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !activeRole) {
      if (!ssrGapPending.current) setGap(null);
      if (!ssrMatchesPending.current) setMatches(null);
      return undefined;
    }
    if (
      ssrGapPending.current &&
      ssrMatchesPending.current &&
      activeRole === initialTopRole
    ) {
      ssrGapPending.current = false;
      ssrMatchesPending.current = false;
      return undefined;
    }
    ssrGapPending.current = false;
    ssrMatchesPending.current = false;
    let cancelled = false;
    const roleQs = `&role=${encodeURIComponent(activeRole)}`;
    Promise.all([
      loadSkillGap(lang, activeRole),
      fetch(`/api/auth/me/matches?lang=${lang}&limit=${MATCHES_FETCH_LIMIT}${roleQs}`, {
        cache: "no-store",
      }).then((res) => (res.ok ? res.json() : null)),
    ])
      .then(([gapPayload, matchesPayload]) => {
        if (cancelled) return;
        setGap(gapPayload);
        setMatches(matchesPayload);
      })
      .catch(() => {
        if (!cancelled) {
          setGap(null);
          setMatches(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, activeRole, initialTopRole]);

  const jobList = Array.isArray(matches?.matches) ? matches.matches : [];
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage } = usePagination(
    jobList,
    LIST_PAGE_SIZE,
  );

  async function sendFeedback(jobId, vote, reason = "") {
    setBusyId(jobId);
    setNote("");
    setError("");
    try {
      const res = await fetch(`/api/auth/me/matches/${jobId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vote, reason }),
      });
      if (!res.ok) {
        setError(t.recommendationsFeedbackError);
        return;
      }
      const payload = await res.json();
      setMatches((current) => {
        if (!current?.matches) return current;
        return {
          ...current,
          matches: current.matches.map((item) =>
            item.job_id === jobId
              ? { ...item, feedback: { vote: payload.vote, reason: payload.reason || "" } }
              : item,
          ),
        };
      });
      setNote(t.recommendationsFeedbackSaved);
    } catch {
      setError(t.recommendationsFeedbackError);
    } finally {
      setBusyId(null);
    }
  }

  const consentOk = roles?.matching_consent !== false && matches?.matching_consent !== false;
  const candidate = Boolean(me?.candidate || me?.staff);
  const roleList = Array.isArray(roles?.roles) ? roles.roles : [];
  const selected = roleList.find((role) => role.canonical_name === activeRole) || null;
  const selectedScore =
    selected && typeof selected.score === "number" ? Math.round(selected.score * 100) : null;
  const coach = gap?.coach && typeof gap.coach === "object" ? gap.coach : null;
  const mustLearn = Array.isArray(coach?.must_learn) ? coach.must_learn : [];
  const alreadyStrong = Array.isArray(coach?.already_strong) ? coach.already_strong : [];
  const transferable = Array.isArray(coach?.transferable) ? coach.transferable : [];
  const hasCoach = Boolean(coach?.fit_summary);
  const missing = Array.isArray(gap?.missing) ? gap.missing : [];
  const have = Array.isArray(gap?.have) ? gap.have : [];
  const hasGap = missing.length > 0 || have.length > 0;

  return (
    <Shell locale={locale} mode="recommendations">
      {me === undefined ? (
        <section className="empty">
          <p className="lede">…</p>
        </section>
      ) : candidate ? (
        <div className="cabinet recommendations-page">
          <div className="recommendations-head">
            <h1>{t.recommendationsTitle}</h1>
            <p className="lede">{t.recommendationsLede}</p>
            <p className="hint recommendations-disclaimer">{t.recommendationsDisclaimer}</p>
          </div>

          {!consentOk ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          {note ? <p className="hint ok">{note}</p> : null}
          {error ? <p className="hint error">{error}</p> : null}

          <div className="recommendations-layout">
            <section className="recommendations-roles" aria-label={t.recommendationsRoles}>
              <h2>{t.recommendationsRoles}</h2>
              {!roleList.length ? (
                <p className="hint">
                  {t.recommendationsEmptyRoles}{" "}
                  <a href={hrefFor(locale, { mode: "profileReview" })}>{t.profileReviewOpen}</a>
                </p>
              ) : (
                <ul className="recommendations-role-list">
                  {roleList.map((role) => {
                    const on = activeRole === role.canonical_name;
                    const score =
                      typeof role.score === "number" ? Math.round(role.score * 100) : null;
                    const haveN = countSkills(role.have);
                    const missN = countSkills(role.missing);
                    return (
                      <li key={role.canonical_name}>
                        <button
                          type="button"
                          className={on ? "recommendations-role-pick on" : "recommendations-role-pick"}
                          onClick={() => setActiveRole(role.canonical_name)}
                          aria-pressed={on}
                        >
                          <span className="recommendations-role-score" aria-hidden={score === null}>
                            {score !== null ? `${score}%` : "—"}
                          </span>
                          <span className="recommendations-role-body">
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

            <section className="recommendations-detail" aria-live="polite">
              {selected ? (
                <header className="recommendations-detail-head">
                  <div>
                    <p className="recommendations-detail-kicker">{t.recommendationsSelectedRole}</p>
                    <h2>{selected.canonical_name}</h2>
                    <p className="hint">
                      {[
                        selected.category,
                        selectedScore !== null ? t.recommendationsScore(selected.score) : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  <CareerPathLink t={t} pathId={gap?.academy_career_path} />
                </header>
              ) : null}

              {selected && hasCoach ? (
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

              {selected ? (
                !hasGap ? (
                  <p className="hint">{t.recommendationsGapEmpty}</p>
                ) : (
                  <div className="skills-panels recommendations-gap-panels">
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
                )
              ) : null}

              <div className="recommendations-jobs">
                <h3>
                  {t.recommendationsJobs}
                  <span className="recommendations-panel-count">{total}</span>
                </h3>
                {!total ? (
                  <p className="hint">{t.recommendationsEmptyJobs}</p>
                ) : (
                  <>
                    <ul className="reco-jobs">
                      {pageItems.map((job) => (
                        <MatchJob
                          key={job.job_id}
                          t={t}
                          locale={locale}
                          job={job}
                          busy={busyId === job.job_id}
                          onFeedback={sendFeedback}
                        />
                      ))}
                    </ul>
                    <Pager
                      locale={locale}
                      currentPage={currentPage}
                      totalPages={totalPages}
                      total={total}
                      pageSize={pageSize}
                      onPageChange={goToPage}
                    />
                  </>
                )}
              </div>
            </section>
          </div>

          <p className="hint recommendations-footer">
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
          </p>
        </div>
      ) : (
        <section className="empty profile-gate">
          <h1>{t.recommendationsTitle}</h1>
          <p className="lede">{t.recommendationsGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "recommendations" })} />
        </section>
      )}
    </Shell>
  );
}
