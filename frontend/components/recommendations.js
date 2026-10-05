"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const REASONS = ["location", "seniority", "technology", "salary"];

function reasonLabel(t, reason) {
  if (reason === "location") return t.recommendationsReasonLocation;
  if (reason === "seniority") return t.recommendationsReasonSeniority;
  if (reason === "technology") return t.recommendationsReasonTechnology;
  if (reason === "salary") return t.recommendationsReasonSalary;
  return reason;
}

export function Recommendations({ locale }) {
  const t = text(locale);
  const lang = locale === "en" || locale === "ru" ? locale : "az";
  const [me, setMe] = useState(undefined);
  const [roles, setRoles] = useState(null);
  const [matches, setMatches] = useState(null);
  const [gap, setGap] = useState(null);
  const [activeRole, setActiveRole] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

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
    Promise.all([
      fetch(`/api/auth/me/roles?lang=${lang}`, { cache: "no-store" }).then((res) =>
        res.ok ? res.json() : null,
      ),
      fetch(`/api/auth/me/matches?lang=${lang}&limit=20`, { cache: "no-store" }).then((res) =>
        res.ok ? res.json() : null,
      ),
    ])
      .then(([rolesPayload, matchesPayload]) => {
        if (cancelled) return;
        setRoles(rolesPayload);
        setMatches(matchesPayload);
        const topRole = rolesPayload?.roles?.[0]?.canonical_name || "";
        setActiveRole(topRole);
      })
      .catch(() => {
        if (!cancelled) {
          setRoles(null);
          setMatches(null);
        }
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

  return (
    <Shell locale={locale} mode="recommendations">
      {me === undefined ? (
        <section className="empty">
          <p className="lede">…</p>
        </section>
      ) : candidate ? (
        <div className="cabinet recommendations-page">
          <div className="cabinet-form-head">
            <h1>{t.recommendationsTitle}</h1>
            <p className="lede">{t.recommendationsLede}</p>
          </div>

          {!consentOk ? (
            <p className="hint">
              {t.recommendationsConsent}{" "}
              <a href={hrefFor(locale, { mode: "profile" })}>{t.recommendationsConsentLink}</a>
            </p>
          ) : null}

          {note ? <p className="hint ok">{note}</p> : null}
          {error ? <p className="hint error">{error}</p> : null}

          <section className="recommendations-section">
            <h2>{t.recommendationsRoles}</h2>
            {!roles?.roles?.length ? (
              <p className="hint">{t.recommendationsEmptyRoles}</p>
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
                      {gap.missing.map((item) => {
                        const sharePct =
                          typeof item.share === "number" ? Math.round(item.share * 100) : null;
                        const growthPct =
                          typeof item.growth === "number" ? Math.round(item.growth * 100) : null;
                        return (
                          <li key={item.name}>
                            <strong>{item.name}</strong>
                            {sharePct !== null || growthPct !== null ? (
                              <span className="hint">
                                {" · "}
                                {[
                                  sharePct !== null ? t.recommendationsGapShare(sharePct) : null,
                                  growthPct !== null ? t.recommendationsGapGrowth(growthPct) : null,
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                              </span>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                </>
              )}
            </section>
          ) : null}

          <section className="recommendations-section">
            <h2>{t.recommendationsJobs}</h2>
            {!matches?.matches?.length ? (
              <p className="hint">{t.recommendationsEmptyJobs}</p>
            ) : (
              <ul className="match-list">
                {matches.matches.map((job) => (
                  <li key={job.job_id} className="match-item">
                    <div className="match-head">
                      <a href={hrefFor(locale, { jobId: job.job_id })}>
                        <strong>{job.title}</strong>
                      </a>
                      <span className="hint">
                        {job.company}
                        {typeof job.score === "number"
                          ? ` · ${t.recommendationsScore(job.score)}`
                          : ""}
                      </span>
                    </div>
                    {job.explanation ? <p className="hint">{job.explanation}</p> : null}
                    <div className="match-actions">
                      <button
                        type="button"
                        className={
                          job.feedback?.vote === "up" ? "btn small on" : "btn small"
                        }
                        disabled={busyId === job.job_id}
                        onClick={() => sendFeedback(job.job_id, "up")}
                      >
                        {t.recommendationsUp}
                      </button>
                      <button
                        type="button"
                        className={
                          job.feedback?.vote === "down" ? "btn small on" : "btn small"
                        }
                        disabled={busyId === job.job_id}
                        onClick={() => sendFeedback(job.job_id, "down")}
                      >
                        {t.recommendationsDown}
                      </button>
                      {job.feedback?.vote === "down" || !job.feedback ? (
                        <label className="match-reason">
                          <span className="hint">{t.recommendationsReason}</span>
                          <select
                            value={job.feedback?.reason || ""}
                            disabled={busyId === job.job_id}
                            onChange={(event) => {
                              const reason = event.target.value;
                              if (!reason) return;
                              sendFeedback(job.job_id, "down", reason);
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
                ))}
              </ul>
            )}
          </section>
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
