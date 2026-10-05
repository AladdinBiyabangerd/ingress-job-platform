"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const SENIORITY = ["", "intern", "junior", "middle", "senior", "lead", "principal", "staff"];

function applyPayload(data, setters) {
  const profile = data?.profile || {};
  const contact = profile.contact || {};
  setters.setHeadline(data?.headline || profile.headline || "");
  setters.setSeniority(data?.seniority || profile.seniority || "");
  setters.setTotalYears(
    data?.total_years != null
      ? String(data.total_years)
      : profile.total_years != null
        ? String(profile.total_years)
        : "",
  );
  setters.setFullName(contact.full_name || "");
  setters.setEmail(contact.email || "");
  setters.setPhone(contact.phone || "");
  setters.setSkills(
    Array.isArray(profile.skills)
      ? profile.skills.map((item) => ({
          name: item?.name || "",
          years: item?.years != null ? String(item.years) : "",
          level: item?.level || "",
          source: item?.source || "user",
        }))
      : [],
  );
  setters.setWork(
    Array.isArray(profile.work_history)
      ? profile.work_history.map((item) => ({
          title: item?.title || "",
          company: item?.company || "",
          start: item?.start || "",
          end: item?.end || "",
          location: item?.location || "",
          summary: item?.summary || "",
          skills: Array.isArray(item?.skills) ? item.skills : [],
        }))
      : [],
  );
  setters.setLowFields(Array.isArray(data?.low_confidence_fields) ? data.low_confidence_fields : []);
}

function FieldMark({ show, label }) {
  if (!show) return null;
  return <span className="profile-review-warn">{label}</span>;
}

export function ProfileReview({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);
  const [payload, setPayload] = useState(null);
  const [headline, setHeadline] = useState("");
  const [seniority, setSeniority] = useState("");
  const [totalYears, setTotalYears] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [skills, setSkills] = useState([]);
  const [work, setWork] = useState([]);
  const [skillDraft, setSkillDraft] = useState("");
  const [skillYearsDraft, setSkillYearsDraft] = useState("");
  const [lowFields, setLowFields] = useState([]);
  const [rolesPayload, setRolesPayload] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  function loadRoles() {
    const lang = locale === "en" || locale === "ru" ? locale : "az";
    return fetch(`/api/auth/me/roles?lang=${lang}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setRolesPayload(data);
      })
      .catch(() => {});
  }

  const setters = {
    setHeadline,
    setSeniority,
    setTotalYears,
    setFullName,
    setEmail,
    setPhone,
    setSkills,
    setWork,
    setLowFields,
  };

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  useEffect(() => {
    if (!allowed) return undefined;
    let cancelled = false;
    fetch("/api/auth/cv-profile", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setPayload(data);
        applyPayload(data, setters);
      })
      .catch(() => {});
    const lang = locale === "en" || locale === "ru" ? locale : "az";
    fetch(`/api/auth/me/roles?lang=${lang}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setRolesPayload(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when access is known
  }, [allowed]);

  function buildBody(confirm) {
    const yearsValue = totalYears.trim() === "" ? null : Number(totalYears);
    return {
      confirm,
      headline,
      seniority,
      total_years: Number.isFinite(yearsValue) ? yearsValue : null,
      profile: {
        contact: { full_name: fullName, email, phone },
        headline,
        seniority,
        total_years: Number.isFinite(yearsValue) ? yearsValue : null,
        skills: skills
          .filter((item) => item.name.trim())
          .map((item) => ({
            name: item.name.trim(),
            years: item.years.trim() === "" ? null : Number(item.years),
            level: item.level || "",
            source: item.source || "user",
          })),
        work_history: work.map((item) => ({
          title: item.title,
          company: item.company,
          start: item.start,
          end: item.end || null,
          location: item.location || "",
          summary: item.summary || "",
          skills: item.skills || [],
        })),
      },
    };
  }

  async function submit(confirm) {
    setError("");
    setNote("");
    setBusy(true);
    try {
      const res = await fetch("/api/auth/cv-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBody(confirm)),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(t.profileReviewError);
        return;
      }
      setPayload(data);
      applyPayload(data, setters);
      setNote(confirm ? t.profileReviewConfirmed : t.profileReviewSaved);
      await loadRoles();
    } catch {
      setError(t.profileReviewError);
    } finally {
      setBusy(false);
    }
  }

  function addSkill(event) {
    event.preventDefault();
    const name = skillDraft.trim();
    if (!name) return;
    if (skills.some((item) => item.name.toLowerCase() === name.toLowerCase())) {
      setSkillDraft("");
      setSkillYearsDraft("");
      return;
    }
    setSkills((current) => [
      ...current,
      { name, years: skillYearsDraft.trim(), level: "", source: "user" },
    ]);
    setSkillDraft("");
    setSkillYearsDraft("");
  }

  function updateSkill(index, patch) {
    setSkills((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function removeSkill(index) {
    setSkills((current) => current.filter((_, i) => i !== index));
  }

  function updateWork(index, patch) {
    setWork((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  const statusLabel =
    payload?.status === "confirmed" ? t.profileReviewStatusConfirmed : t.profileReviewStatusDraft;
  const warn = (field) => lowFields.includes(field);

  return (
    <Shell locale={locale} mode="profileReview">
      {me === undefined ? null : allowed ? (
        <div className="cabinet">
          <div className="cabinet-head">
            <div>
              <h1>{t.profileReviewTitle}</h1>
              <p className="lede">{t.profileReviewLede}</p>
            </div>
            <a className="btn ghost" href={hrefFor(locale, { mode: "profile" })}>
              {t.profileReviewBack}
            </a>
          </div>

          {!payload ? null : !payload.exists ? (
            <section className="form-card profile-card">
              <p className="hint">
                {payload.parse_status === "pending" || payload.parse_status === "processing"
                  ? t.profileReviewPending
                  : payload.parse_status === "failed"
                    ? t.profileReviewFailed
                    : t.profileReviewEmpty}
              </p>
              <div className="ad-actions">
                <a className="btn primary" href={hrefFor(locale, { mode: "applications" })}>
                  {t.myApplications}
                </a>
              </div>
            </section>
          ) : (
            <form
              className="form-card profile-card profile-review"
              onSubmit={(event) => {
                event.preventDefault();
                submit(false);
              }}
            >
              <div className="profile-review-meta">
                <span className={`profile-review-status status-${payload.status || "draft"}`}>
                  {statusLabel}
                </span>
                {typeof payload.confidence === "number" ? (
                  <span className="hint">{t.profileReviewConfidence(payload.confidence)}</span>
                ) : null}
                {payload.parse_status === "pending" || payload.parse_status === "processing" ? (
                  <p className="hint">{t.profileReviewPending}</p>
                ) : null}
              </div>

              {error ? <p className="note">{error}</p> : null}
              {note ? <p className="note">{note}</p> : null}

              <div className={`profile-grid${warn("contact") ? " field-warn" : ""}`}>
                <div className="cabinet-form-head profile-span">
                  <h2>{t.profileReviewContact}</h2>
                  <FieldMark show={warn("contact")} label={t.profileReviewCheck} />
                </div>
                <label>
                  {t.profileReviewFullName}
                  <input value={fullName} maxLength={120} onChange={(event) => setFullName(event.target.value)} />
                </label>
                <label>
                  {t.applyEmail}
                  <input type="email" value={email} maxLength={120} onChange={(event) => setEmail(event.target.value)} />
                </label>
                <label>
                  {t.applyPhone}
                  <input type="tel" value={phone} maxLength={40} onChange={(event) => setPhone(event.target.value)} />
                </label>
              </div>

              <div className="profile-grid">
                <label className={`profile-span${warn("headline") ? " field-warn" : ""}`}>
                  {t.profileReviewHeadline}
                  <FieldMark show={warn("headline")} label={t.profileReviewCheck} />
                  <input value={headline} maxLength={200} onChange={(event) => setHeadline(event.target.value)} />
                </label>
                <label className={warn("seniority") ? "field-warn" : undefined}>
                  {t.profileReviewSeniority}
                  <FieldMark show={warn("seniority")} label={t.profileReviewCheck} />
                  <select value={seniority} onChange={(event) => setSeniority(event.target.value)}>
                    {SENIORITY.map((value) => (
                      <option key={value || "empty"} value={value}>
                        {value || "—"}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={warn("total_years") ? "field-warn" : undefined}>
                  {t.profileReviewYears}
                  <FieldMark show={warn("total_years")} label={t.profileReviewCheck} />
                  <input
                    type="number"
                    min="0"
                    max="60"
                    step="0.1"
                    value={totalYears}
                    onChange={(event) => setTotalYears(event.target.value)}
                  />
                </label>
              </div>

              <div className={`profile-review-skills${warn("skills") ? " field-warn" : ""}`}>
                <div className="cabinet-form-head">
                  <h2>{t.profileReviewSkills}</h2>
                  <FieldMark show={warn("skills")} label={t.profileReviewCheck} />
                </div>
                <div className="skill-chip-list">
                  {skills.map((skill, index) => (
                    <div key={`${skill.name}-${index}`} className="skill-chip">
                      <input
                        className="skill-chip-name"
                        value={skill.name}
                        maxLength={60}
                        aria-label={t.profileReviewSkillName}
                        onChange={(event) => updateSkill(index, { name: event.target.value })}
                      />
                      <input
                        className="skill-chip-years"
                        type="number"
                        min="0"
                        max="60"
                        step="0.5"
                        placeholder={t.profileReviewSkillYears}
                        value={skill.years}
                        aria-label={t.profileReviewSkillYears}
                        onChange={(event) => updateSkill(index, { years: event.target.value })}
                      />
                      <button type="button" className="btn ghost skill-chip-remove" onClick={() => removeSkill(index)}>
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="skill-add-row">
                  <input
                    value={skillDraft}
                    maxLength={60}
                    placeholder={t.profileReviewSkillName}
                    onChange={(event) => setSkillDraft(event.target.value)}
                  />
                  <input
                    type="number"
                    min="0"
                    max="60"
                    step="0.5"
                    value={skillYearsDraft}
                    placeholder={t.profileReviewSkillYears}
                    onChange={(event) => setSkillYearsDraft(event.target.value)}
                  />
                  <button type="button" className="btn" onClick={addSkill}>
                    {t.profileReviewSkillAdd}
                  </button>
                </div>
              </div>

              <div className={`profile-review-work${warn("work_history") ? " field-warn" : ""}`}>
                <div className="cabinet-form-head">
                  <h2>{t.profileReviewWork}</h2>
                  <FieldMark show={warn("work_history")} label={t.profileReviewCheck} />
                </div>
                {work.length === 0 ? <p className="hint">—</p> : null}
                {work.map((job, index) => (
                  <div key={`job-${index}`} className="profile-grid work-row">
                    <label>
                      {t.profileReviewJobTitle}
                      <input
                        value={job.title}
                        maxLength={120}
                        onChange={(event) => updateWork(index, { title: event.target.value })}
                      />
                    </label>
                    <label>
                      {t.profileReviewCompany}
                      <input
                        value={job.company}
                        maxLength={120}
                        onChange={(event) => updateWork(index, { company: event.target.value })}
                      />
                    </label>
                    <label>
                      {t.profileReviewStart}
                      <input
                        value={job.start}
                        maxLength={20}
                        placeholder="2021-03"
                        onChange={(event) => updateWork(index, { start: event.target.value })}
                      />
                    </label>
                    <label>
                      {t.profileReviewEnd}
                      <input
                        value={job.end || ""}
                        maxLength={20}
                        placeholder={t.profileReviewPresent}
                        onChange={(event) => updateWork(index, { end: event.target.value })}
                      />
                    </label>
                  </div>
                ))}
              </div>

              {rolesPayload ? (
                <div className="profile-review-roles">
                  <div className="cabinet-form-head">
                    <h2>{t.profileReviewRolesTitle}</h2>
                  </div>
                  {!rolesPayload.matching_consent ? (
                    <p className="hint">
                      {t.profileReviewRolesConsent}{" "}
                      <a href={hrefFor(locale, { mode: "profile" })}>{t.profileReviewRolesConsentLink}</a>
                    </p>
                  ) : !rolesPayload.roles?.length ? (
                    <p className="hint">{t.profileReviewRolesEmpty}</p>
                  ) : (
                    <ul className="role-suggest-list">
                      {rolesPayload.roles.map((role) => (
                        <li key={role.canonical_name} className="role-suggest-item">
                          <div className="role-suggest-head">
                            <strong>{role.canonical_name}</strong>
                            <span className="hint">
                              {role.category}
                              {typeof role.score === "number"
                                ? ` · ${t.profileReviewRolesScore(role.score)}`
                                : ""}
                            </span>
                          </div>
                          {role.explanation ? <p className="hint">{role.explanation}</p> : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : null}

              <div className="ad-actions">
                <button type="submit" className="btn" disabled={busy}>
                  {t.profileReviewSave}
                </button>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={() => submit(true)}
                >
                  {t.profileReviewConfirm}
                </button>
              </div>
            </form>
          )}
        </div>
      ) : (
        <section className="empty profile-gate">
          <h1>{t.profileReviewTitle}</h1>
          <p className="lede">{t.profileGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "profileReview" })} />
        </section>
      )}
    </Shell>
  );
}
