"use client";

import { useEffect, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { loadSkillGap } from "../lib/server/refresh";
import { CareerPathLink, SkillRow } from "./skill-gap-bits";
import { Pager } from "./pager";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { RoleSkillParts } from "./role-skill-parts";
import { SkillIcon } from "./skill-icon";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const REASONS = ["location", "seniority", "technology", "salary"];
const MATCHES_FETCH_LIMIT = 10;
const SKILL_PREVIEW = 4;
const JOBS_PREVIEW = 3;

function ScoreRing({ pct, label }) {
  const value = typeof pct === "number" && !Number.isNaN(pct) ? Math.max(0, Math.min(100, pct)) : null;
  const ring =
    value === null ? (
      <div className="recommendations-score-ring recommendations-score-ring-empty" aria-hidden="true">
        <span>—</span>
      </div>
    ) : (
      <div
        className="recommendations-score-ring"
        style={{ "--score": String(value) }}
        role="img"
        aria-label={label ? `${label} ${value}%` : `${value}%`}
      >
        <span>{value}%</span>
      </div>
    );
  if (!label) return ring;
  return (
    <div className="recommendations-score-wrap">
      {ring}
      <span className="recommendations-score-label">{label}</span>
    </div>
  );
}

function normalizeCoach(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  return raw;
}

function coachLearnItems(list) {
  if (!Array.isArray(list)) return [];
  return list.filter(
    (item) => item && typeof item === "object" && String(item.skill || "").trim(),
  );
}

function coachNameList(list) {
  if (!Array.isArray(list)) return [];
  return list.map((item) => String(item || "").trim()).filter(Boolean);
}

function coachTransferItems(list) {
  if (!Array.isArray(list)) return [];
  return list.filter(
    (item) =>
      item &&
      typeof item === "object" &&
      String(item.from || "").trim() &&
      String(item.to || "").trim(),
  );
}

function coachEmptyMessage(t, coachError) {
  const code = String(coachError || "").trim();
  if (!code) return t.skillsCoachEmpty;
  if (code === "ai_pending") return t.skillsCoachPending || t.skillsCoachEmpty;
  if (code === "ai_no_key") return t.skillsCoachErrorNoKey;
  if (code === "ai_disabled" || code === "role_coach_disabled") return t.skillsCoachErrorOff;
  if (code === "ai_budget_exceeded") return t.skillsCoachErrorBudget;
  if (code === "ai_validation_failed") return t.skillsCoachErrorValidation;
  if (code.startsWith("ai_provider") || code === "ai_bad_json" || code === "ai_failed") {
    return t.skillsCoachErrorProvider;
  }
  if (typeof t.skillsCoachErrorCode === "function") return t.skillsCoachErrorCode(code);
  return t.skillsCoachEmpty;
}

function JobPreviewItem({ t, locale, job }) {
  const score = typeof job.score === "number" ? Math.round(job.score * 100) : null;
  const meta = jobMeta(t, job);
  return (
    <li className="recommendations-job-preview">
      <a className="recommendations-job-preview-link" href={hrefFor(locale, { jobId: job.job_id })}>
        <strong>{job.title}</strong>
        {meta ? <span className="hint">{meta}</span> : null}
      </a>
      <span className="recommendations-job-preview-score" aria-hidden={score === null}>
        {score !== null ? `${score}%` : "—"}
      </span>
    </li>
  );
}

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
          <RoleSkillParts t={t} have={job.have} missing={job.missing} limit={SKILL_PREVIEW} />
        </div>
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
          {votedDown ? (
            <label className="reco-job-reason">
              <span className="visually-hidden">{t.recommendationsReason}</span>
              <select
                value={job.feedback?.reason || ""}
                disabled={busy}
                aria-label={t.recommendationsReason}
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
      </div>
    </li>
  );
}

function useCandidateMe(initialMe) {
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });

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

  return me;
}

function Gate({ locale, title, message, returnTo }) {
  const t = text(locale);
  return (
    <div className="h2-candidate">
      <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={title} />
      <div className="h2-empty h2-gate">
        <p>{message}</p>
        <RegisterChoice locale={locale} returnTo={returnTo} />
      </div>
    </div>
  );
}

/** Overview: roles + coach/gap + CTA to matching-jobs page. */
export function Recommendations({
  locale,
  initialRoles = null,
  initialMatches = null,
  initialGap = null,
}) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const initialMe = useInitialMe();
  const me = useCandidateMe(initialMe);
  const seededCatalog = initialRoles != null && initialMatches != null;
  const initialTopRole = initialRoles?.roles?.[0]?.canonical_name || "";
  const seededInitialGap = initialGap != null;
  const ssrGapPending = useRef(seededInitialGap);
  const ssrMatchesPending = useRef(seededCatalog);
  const [roles, setRoles] = useState(initialRoles);
  const [matches, setMatches] = useState(initialMatches);
  const [activeRole, setActiveRole] = useState(initialTopRole);
  const [gap, setGap] = useState(initialGap);

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
    loadSkillGap(lang, activeRole)
      .then((gapPayload) => {
        if (!cancelled) setGap(gapPayload);
      })
      .catch(() => {
        if (!cancelled) setGap(null);
      });
    fetch(`/api/auth/me/matches?lang=${lang}&limit=${MATCHES_FETCH_LIMIT}${roleQs}`, {
      cache: "no-store",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((matchesPayload) => {
        if (!cancelled) setMatches(matchesPayload);
      })
      .catch(() => {
        if (!cancelled) setMatches(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, activeRole, initialTopRole]);

  // AI coach / match LLM warm in a background thread — poll until ready.
  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !activeRole) return undefined;
    const coachPending = String(gap?.coach_error || "").trim() === "ai_pending";
    const matchesPending = Boolean(matches?.ai_pending);
    if (!coachPending && !matchesPending) return undefined;
    let cancelled = false;
    let attempts = 0;
    const roleQs = `&role=${encodeURIComponent(activeRole)}`;
    const tick = () => {
      attempts += 1;
      if (attempts > 20 || cancelled) return;
      if (coachPending) {
        loadSkillGap(lang, activeRole)
          .then((gapPayload) => {
            if (!cancelled && gapPayload) setGap(gapPayload);
          })
          .catch(() => {});
      }
      if (matchesPending) {
        fetch(`/api/auth/me/matches?lang=${lang}&limit=${MATCHES_FETCH_LIMIT}${roleQs}`, {
          cache: "no-store",
        })
          .then((res) => (res.ok ? res.json() : null))
          .then((matchesPayload) => {
            if (!cancelled && matchesPayload) setMatches(matchesPayload);
          })
          .catch(() => {});
      }
    };
    const id = setInterval(tick, 2500);
    tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [me, lang, activeRole, gap?.coach_error, matches?.ai_pending]);

  const jobCount = Array.isArray(matches?.matches) ? matches.matches.length : 0;
  const consentOk = roles?.matching_consent !== false && matches?.matching_consent !== false;
  const candidate = Boolean(me?.candidate || me?.staff);
  const roleList = Array.isArray(roles?.roles) ? roles.roles : [];
  const selected = roleList.find((role) => role.canonical_name === activeRole) || null;
  const selectedScore =
    selected && typeof selected.score === "number" ? Math.round(selected.score * 100) : null;
  const coach = normalizeCoach(gap?.coach);
  const mustLearn = coachLearnItems(coach?.must_learn);
  const alreadyStrong = coachNameList(coach?.already_strong);
  const transferable = coachTransferItems(coach?.transferable);
  const fitSummary = String(coach?.fit_summary || "").trim();
  const hasCoach = Boolean(
    fitSummary || mustLearn.length || alreadyStrong.length || transferable.length,
  );
  const coachError = String(gap?.coach_error || "").trim();
  const missing = Array.isArray(gap?.missing) ? gap.missing : [];
  const have = Array.isArray(gap?.have) ? gap.have : [];
  const hasGap = missing.length > 0 || have.length > 0;
  const jobsHref = hrefFor(locale, { mode: "recommendationJobs", role: activeRole || undefined });
  const jobPreview = Array.isArray(matches?.matches) ? matches.matches.slice(0, JOBS_PREVIEW) : [];

  return (
    <Shell locale={locale} mode="recommendations">
      {me === undefined ? null : candidate ? (
        <div className="h2-candidate recommendations-page">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.recommendationsTitle}
          />

          {!consentOk ? (
            <p className="hint h2-consent-banner">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          <div className="recommendations-layout recommendations-bento" aria-live="polite">
            <section
              className="h2-panel recommendations-tile recommendations-tile-roles"
              aria-label={t.recommendationsRoles}
            >
              <h2 className="h2-panel-title">{t.recommendationsRoles}</h2>
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

            <section className="h2-panel recommendations-tile recommendations-tile-selected">
              {selected ? (
                <>
                  <header className="recommendations-selected-head">
                    <div className="recommendations-selected-copy">
                      <p className="recommendations-detail-kicker">{t.recommendationsSelectedRole}</p>
                      <h2 className="h2-panel-title">{selected.canonical_name}</h2>
                      {selected.category ? <p className="hint">{selected.category}</p> : null}
                    </div>
                    <ScoreRing pct={selectedScore} label={t.jobRowMatch} />
                  </header>
                  <div className="recommendations-selected-actions">
                    <CareerPathLink t={t} pathId={gap?.academy_career_path} />
                    {jobCount ? (
                      <a className="btn" href={jobsHref}>
                        {t.recommendationsJobsOpenCount(jobCount)}
                      </a>
                    ) : (
                      <p className="hint">{t.recommendationsEmptyJobs}</p>
                    )}
                  </div>
                </>
              ) : (
                <p className="hint">
                  {t.recommendationsEmptyRoles}{" "}
                  <a href={hrefFor(locale, { mode: "profileReview" })}>{t.profileReviewOpen}</a>
                </p>
              )}
            </section>

            <section
              className="h2-panel recommendations-tile recommendations-tile-coach"
              aria-label={t.skillsCoachTitle}
            >
              <h2 className="h2-panel-title">{t.skillsCoachTitle}</h2>
              {!selected ? (
                <p className="hint">{t.recommendationsGapEmpty}</p>
              ) : hasCoach ? (
                <>
                  {fitSummary ? <p className="lede skills-coach-summary">{fitSummary}</p> : null}
                  <div className="recommendations-coach-grid">
                    <div className="skills-coach-block">
                      <h3>{t.skillsCoachMustLearn}</h3>
                      {mustLearn.length ? (
                        <ul className="skills-coach-list">
                          {mustLearn.map((item) => {
                            const skill = String(item.skill || "").trim();
                            const why = String(item.why || "").trim();
                            return (
                              <li key={`coach-learn-${skill}`}>
                                <SkillIcon name={skill} />
                                <span>
                                  <strong>{skill}</strong>
                                  {why ? <span className="hint"> — {why}</span> : null}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <p className="hint">{t.skillsMissingEmpty}</p>
                      )}
                    </div>
                    <div className="skills-coach-block">
                      <h3>{t.skillsCoachStrong}</h3>
                      {alreadyStrong.length ? (
                        <ul className="recommendations-coach-chips">
                          {alreadyStrong.map((skill) => (
                            <li key={`strong-${skill}`}>
                              <SkillIcon name={skill} />
                              <span>{skill}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="hint">{t.skillsHaveEmpty}</p>
                      )}
                    </div>
                    <div className="skills-coach-block">
                      <h3>{t.skillsCoachTransferable}</h3>
                      {transferable.length ? (
                        <ul className="skills-coach-list">
                          {transferable.map((item) => {
                            const from = String(item.from || "").trim();
                            const to = String(item.to || "").trim();
                            const note = String(item.note || "").trim();
                            return (
                              <li key={`xfer-${from}-${to}`}>
                                <span className="recommendations-xfer-icons" aria-hidden="true">
                                  <SkillIcon name={from} />
                                  <span className="recommendations-xfer-arrow">→</span>
                                  <SkillIcon name={to} />
                                </span>
                                <span>
                                  <strong>{t.skillsCoachTransfer(from, to)}</strong>
                                  {note ? <span className="hint"> — {note}</span> : null}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      ) : (
                        <p className="hint">{t.skillsCoachTransferEmpty}</p>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div
                  className="recommendations-coach-empty"
                  role={coachError === "ai_pending" ? "status" : undefined}
                  aria-live={coachError === "ai_pending" ? "polite" : undefined}
                >
                  <p className="hint">{coachEmptyMessage(t, coachError)}</p>
                  {coachError && coachError !== "ai_pending" ? (
                    <p className="hint recommendations-coach-error-code">{coachError}</p>
                  ) : null}
                </div>
              )}
            </section>

            <section className="h2-panel recommendations-tile recommendations-tile-have">
              <h2 className="h2-panel-title">
                {t.skillsHave}
                <span className="skills-panel-count">{have.length}</span>
              </h2>
              {!selected ? (
                <p className="hint">{t.recommendationsGapEmpty}</p>
              ) : !have.length ? (
                <p className="hint">{hasGap ? t.skillsHaveEmpty : t.recommendationsGapEmpty}</p>
              ) : (
                <ul className="skills-rows">
                  {have.map((item) => (
                    <SkillRow key={`have-${item.name}`} t={t} item={item} tone="have" />
                  ))}
                </ul>
              )}
            </section>

            <section className="h2-panel recommendations-tile recommendations-tile-learn">
              <h2 className="h2-panel-title">
                {t.recommendationsGapLearn}
                <span className="skills-panel-count">{missing.length}</span>
              </h2>
              {!selected ? (
                <p className="hint">{t.recommendationsGapEmpty}</p>
              ) : !missing.length ? (
                <p className="hint">{hasGap ? t.skillsMissingEmpty : t.recommendationsGapEmpty}</p>
              ) : (
                <ul className="skills-rows recommendations-learn-grid">
                  {missing.map((item) => (
                    <SkillRow key={`missing-${item.name}`} t={t} item={item} tone="missing" />
                  ))}
                </ul>
              )}
            </section>

            <section
              className="h2-panel recommendations-tile recommendations-tile-jobs"
              aria-label={t.recommendationsJobs}
            >
              <div className="recommendations-tile-jobs-head">
                <h2 className="h2-panel-title">{t.recommendationsJobs}</h2>
                {jobCount ? (
                  <a className="btn small" href={jobsHref}>
                    {t.recommendationsJobsOpenCount(jobCount)}
                  </a>
                ) : null}
              </div>
              {!jobPreview.length ? (
                <p className="hint">{t.recommendationsEmptyJobs}</p>
              ) : (
                <ul className="recommendations-job-preview-list">
                  {jobPreview.map((job) => (
                    <JobPreviewItem key={job.job_id} t={t} locale={locale} job={job} />
                  ))}
                </ul>
              )}
            </section>
          </div>

          <p className="hint h2-candidate-footer recommendations-footer">
            <a href={hrefFor(locale, { mode: "trends" })}>{t.trendsTitle}</a>
          </p>
        </div>
      ) : (
        <Gate
          locale={locale}
          title={t.recommendationsTitle}
          message={t.recommendationsGate}
          returnTo={hrefFor(locale, { mode: "recommendations" })}
        />
      )}
    </Shell>
  );
}

/** Dedicated matching-jobs list (opened from recommendations overview). */
export function RecommendationJobs({
  locale,
  initialRoles = null,
  initialMatches = null,
  initialRole = "",
}) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const initialMe = useInitialMe();
  const me = useCandidateMe(initialMe);
  const seededCatalog = initialRoles != null && initialMatches != null;
  const topRole = initialRoles?.roles?.[0]?.canonical_name || "";
  const seededRole = String(initialRole || "").trim() || topRole;
  const ssrMatchesPending = useRef(seededCatalog);
  const [roles, setRoles] = useState(initialRoles);
  const [matches, setMatches] = useState(initialMatches);
  const [activeRole, setActiveRole] = useState(seededRole);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff)) return undefined;
    if (seededCatalog) return undefined;
    let cancelled = false;
    fetch(`/api/auth/me/roles?lang=${lang}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((rolesPayload) => {
        if (cancelled) return;
        setRoles(rolesPayload);
        if (!activeRole) {
          setActiveRole(rolesPayload?.roles?.[0]?.canonical_name || "");
        }
      })
      .catch(() => {
        if (!cancelled) setRoles(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, seededCatalog, activeRole]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !activeRole) {
      if (!ssrMatchesPending.current) setMatches(null);
      return undefined;
    }
    if (ssrMatchesPending.current && activeRole === seededRole) {
      ssrMatchesPending.current = false;
      return undefined;
    }
    ssrMatchesPending.current = false;
    let cancelled = false;
    fetch(
      `/api/auth/me/matches?lang=${lang}&limit=${MATCHES_FETCH_LIMIT}&role=${encodeURIComponent(activeRole)}`,
      { cache: "no-store" },
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((matchesPayload) => {
        if (!cancelled) setMatches(matchesPayload);
      })
      .catch(() => {
        if (!cancelled) setMatches(null);
      });
    return () => {
      cancelled = true;
    };
  }, [me, lang, activeRole, seededRole]);

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

  function pickRole(roleName) {
    setActiveRole(roleName);
    if (typeof window !== "undefined") {
      const next = hrefFor(locale, { mode: "recommendationJobs", role: roleName });
      window.history.replaceState(null, "", next);
    }
  }

  return (
    <Shell locale={locale} mode="recommendations">
      {me === undefined ? null : candidate ? (
        <div className="h2-candidate recommendations-page recommendations-jobs-page">
          <PageChrome
            backHref={hrefFor(locale, { mode: "recommendations" })}
            backLabel={t.recommendationsTitle}
            title={t.recommendationsJobs}
            count={total || null}
          />

          {!consentOk ? (
            <p className="hint h2-consent-banner">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          {note ? <p className="hint ok">{note}</p> : null}
          {error ? <p className="hint error">{error}</p> : null}

          {roleList.length ? (
            <div className="h2-panel reco-role-switch" role="tablist" aria-label={t.recommendationsRoles}>
              {roleList.map((role) => {
                const on = activeRole === role.canonical_name;
                return (
                  <button
                    key={role.canonical_name}
                    type="button"
                    role="tab"
                    aria-selected={on}
                    className={on ? "reco-role-chip on" : "reco-role-chip"}
                    onClick={() => pickRole(role.canonical_name)}
                  >
                    {role.canonical_name}
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="hint">
              {t.recommendationsEmptyRoles}{" "}
              <a href={hrefFor(locale, { mode: "profileReview" })}>{t.profileReviewOpen}</a>
            </p>
          )}

          <section className="h2-panel recommendations-jobs-list">
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
          </section>
        </div>
      ) : (
        <Gate
          locale={locale}
          title={t.recommendationsJobs}
          message={t.recommendationsGate}
          returnTo={hrefFor(locale, { mode: "recommendationJobs" })}
        />
      )}
    </Shell>
  );
}
