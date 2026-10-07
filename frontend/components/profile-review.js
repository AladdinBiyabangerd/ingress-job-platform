"use client";

import { useEffect, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import {
  cancelCvParse,
  deleteCvProfile,
  loadCvProfile,
  loadRoles as loadRolesFromApi,
  saveCvProfile,
  uploadCvProfile,
} from "../lib/server/refresh";
import { RegisterChoice } from "./register-choice";
import { RoleSkillParts } from "./role-skill-parts";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const SENIORITY = ["", "intern", "junior", "middle", "senior", "lead", "principal", "staff"];
const LANG_LEVELS = ["", "A1", "A2", "B1", "B2", "C1", "C2", "native"];
const LANG_CODES = ["az", "en", "ru", "tr", "de", "fr"];
const CV_ACCEPT =
  ".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const POLL_MS = 2000;
const POLL_MAX = 45;

function emptyWork() {
  return {
    title: "",
    company: "",
    start: "",
    end: "",
    location: "",
    summary: "",
    skills: [],
    employment_type: "",
  };
}

function emptyEdu() {
  return { degree: "", field: "", school: "", year: "" };
}

function emptyLang() {
  return { code: "", level: "" };
}

function snapshotFromPayload(data) {
  const profile = data?.profile || {};
  const contact = profile.contact || {};
  const links = profile.links || {};
  return {
    headline: data?.headline || profile.headline || "",
    summary: profile.summary || "",
    seniority: data?.seniority || profile.seniority || "",
    totalYears:
      data?.total_years != null
        ? String(data.total_years)
        : profile.total_years != null
          ? String(profile.total_years)
          : "",
    fullName: contact.full_name || "",
    email: contact.email || "",
    phone: contact.phone || "",
    city: contact.city || "",
    country: contact.country || "",
    linkedin: links.linkedin_url || "",
    github: links.github || "",
    portfolio: links.portfolio || "",
    skills: Array.isArray(profile.skills)
      ? profile.skills.map((item) => ({
          name: item?.name || "",
          years: item?.years != null ? String(item.years) : "",
          level: item?.level || "",
          source: item?.source || "user",
        }))
      : [],
    work: Array.isArray(profile.work_history)
      ? profile.work_history.map((item) => ({
          title: item?.title || "",
          company: item?.company || "",
          start: item?.start || "",
          end: item?.end || "",
          location: item?.location || "",
          summary: item?.summary || "",
          skills: Array.isArray(item?.skills) ? item.skills : [],
          employment_type: item?.employment_type || "",
        }))
      : [],
    education: Array.isArray(profile.education)
      ? profile.education.map((item) => ({
          degree: item?.degree || "",
          field: item?.field || "",
          school: item?.school || "",
          year: item?.year != null ? String(item.year) : "",
        }))
      : [],
    languages: Array.isArray(profile.languages)
      ? profile.languages.map((item) => ({
          code: item?.code || "",
          level: item?.level || "",
        }))
      : [],
    lowFields: Array.isArray(data?.low_confidence_fields) ? data.low_confidence_fields : [],
  };
}

function applyPayload(data, setters) {
  const snap = snapshotFromPayload(data);
  setters.setHeadline(snap.headline);
  setters.setSummary(snap.summary);
  setters.setSeniority(snap.seniority);
  setters.setTotalYears(snap.totalYears);
  setters.setFullName(snap.fullName);
  setters.setEmail(snap.email);
  setters.setPhone(snap.phone);
  setters.setCity(snap.city);
  setters.setCountry(snap.country);
  setters.setLinkedin(snap.linkedin);
  setters.setGithub(snap.github);
  setters.setPortfolio(snap.portfolio);
  setters.setSkills(snap.skills);
  setters.setWork(snap.work);
  setters.setEducation(snap.education);
  setters.setLanguages(snap.languages);
  setters.setLowFields(snap.lowFields);
}

function entryFromPayload(data) {
  if (!data || typeof data !== "object") return null;
  if (data.exists) return "form";
  if (parseOpen(data.parse_status)) return "upload";
  return null;
}

function FieldMark({ show, label }) {
  if (!show) return null;
  return <span className="profile-review-warn">{label}</span>;
}

function parseOpen(status) {
  return status === "pending" || status === "processing";
}

function parseStep(uploading, parseStatus) {
  if (uploading) return 0;
  if (parseStatus === "processing") return 2;
  return 1;
}

function ParseProgress({ t, uploading, parseStatus, fileName, onCancel, cancelBusy }) {
  const step = parseStep(uploading, parseStatus);
  const steps = [
    { key: "upload", label: t.profileReviewStepUpload },
    { key: "queue", label: t.profileReviewStepQueue },
    { key: "parse", label: t.profileReviewStepParse },
  ];
  return (
    <div className="cv-parse-progress" role="status" aria-live="polite" aria-busy="true">
      <div className="cv-parse-progress-head">
        <strong>{t.profileReviewProgressTitle}</strong>
        <span className="hint">{steps[step]?.label}</span>
      </div>
      {fileName ? <p className="hint cv-parse-progress-file">{fileName}</p> : null}
      <div className="cv-parse-progress-track is-indeterminate" aria-hidden="true">
        <div className="cv-parse-progress-fill" />
      </div>
      <ol className="cv-parse-steps">
        {steps.map((item, index) => {
          const state = index < step ? "done" : index === step ? "active" : "todo";
          return (
            <li key={item.key} className={`cv-parse-step is-${state}`}>
              <span className="cv-parse-step-dot" aria-hidden="true" />
              <span>{item.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="hint">{t.profileReviewPending}</p>
      {onCancel ? (
        <div className="cv-parse-progress-actions">
          <button type="button" className="btn ghost" disabled={cancelBusy || uploading} onClick={onCancel}>
            {t.profileReviewCancelParse}
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function ProfileReview({ locale, initialProfile = null, initialRoles = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const seededProfile = initialProfile != null && typeof initialProfile === "object";
  const seededRoles = initialRoles != null && typeof initialRoles === "object";
  const seedSnap = seededProfile ? snapshotFromPayload(initialProfile) : null;
  const seedParseOpen = Boolean(seededProfile && parseOpen(initialProfile.parse_status));
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [payload, setPayload] = useState(() => (seededProfile ? initialProfile : null));
  const [entry, setEntry] = useState(() => (seededProfile ? entryFromPayload(initialProfile) : null));
  const [headline, setHeadline] = useState(() => seedSnap?.headline || "");
  const [summary, setSummary] = useState(() => seedSnap?.summary || "");
  const [seniority, setSeniority] = useState(() => seedSnap?.seniority || "");
  const [totalYears, setTotalYears] = useState(() => seedSnap?.totalYears || "");
  const [fullName, setFullName] = useState(() => seedSnap?.fullName || "");
  const [email, setEmail] = useState(() => seedSnap?.email || "");
  const [phone, setPhone] = useState(() => seedSnap?.phone || "");
  const [city, setCity] = useState(() => seedSnap?.city || "");
  const [country, setCountry] = useState(() => seedSnap?.country || "");
  const [linkedin, setLinkedin] = useState(() => seedSnap?.linkedin || "");
  const [github, setGithub] = useState(() => seedSnap?.github || "");
  const [portfolio, setPortfolio] = useState(() => seedSnap?.portfolio || "");
  const [skills, setSkills] = useState(() => seedSnap?.skills || []);
  const [work, setWork] = useState(() => seedSnap?.work || []);
  const [education, setEducation] = useState(() => seedSnap?.education || []);
  const [languages, setLanguages] = useState(() => seedSnap?.languages || []);
  const [skillDraft, setSkillDraft] = useState("");
  const [skillYearsDraft, setSkillYearsDraft] = useState("");
  const [lowFields, setLowFields] = useState(() => seedSnap?.lowFields || []);
  const [rolesPayload, setRolesPayload] = useState(() => (seededRoles ? initialRoles : null));
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [polling, setPolling] = useState(() => seedParseOpen);
  const [cvName, setCvName] = useState("");
  const fileRef = useRef(null);
  const pollLeft = useRef(seedParseOpen ? POLL_MAX : 0);
  /** Bumped on cancel/reset so in-flight poll responses cannot re-open the progress UI. */
  const pollEpoch = useRef(0);

  function loadRoles() {
    return loadRolesFromApi(locale)
      .then((data) => {
        if (data) setRolesPayload(data);
      })
      .catch(() => {});
  }

  const setters = {
    setHeadline,
    setSummary,
    setSeniority,
    setTotalYears,
    setFullName,
    setEmail,
    setPhone,
    setCity,
    setCountry,
    setLinkedin,
    setGithub,
    setPortfolio,
    setSkills,
    setWork,
    setEducation,
    setLanguages,
    setLowFields,
  };

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  function ingestProfile(data) {
    setPayload(data);
    if (data?.exists) {
      applyPayload(data, setters);
      setEntry("form");
      if (parseOpen(data.parse_status)) {
        setPolling(true);
        pollLeft.current = POLL_MAX;
      }
    } else if (parseOpen(data?.parse_status)) {
      setEntry("upload");
      setPolling(true);
      pollLeft.current = POLL_MAX;
    }
  }

  useEffect(() => {
    if (!allowed) return undefined;
    if (seededProfile) {
      if (!seededRoles) loadRoles();
      return undefined;
    }
    let cancelled = false;
    loadCvProfile()
      .then((data) => {
        if (cancelled || !data) return;
        ingestProfile(data);
      })
      .catch(() => {});
    loadRoles();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load once when access is known
  }, [allowed, seededProfile, seededRoles]);

  useEffect(() => {
    if (!polling || !allowed) return undefined;
    let cancelled = false;
    const epoch = pollEpoch.current;
    const stillCurrent = () => !cancelled && epoch === pollEpoch.current;
    const tick = async () => {
      if (!stillCurrent()) return;
      if (pollLeft.current <= 0) {
        setPolling(false);
        try {
          const res = await cancelCvParse();
          const data = res.ok ? res.data : null;
          if (stillCurrent() && data) {
            setPayload(data);
            if (!data.exists) setEntry(null);
          }
        } catch {
          /* ignore — user can cancel manually */
        }
        if (stillCurrent()) setError(t.profileReviewStalled);
        return;
      }
      pollLeft.current -= 1;
      try {
        const data = await loadCvProfile();
        if (!stillCurrent() || !data) return;
        setPayload(data);
        if (data.parse_status === "failed") {
          setPolling(false);
          setError(t.profileReviewFailed);
          return;
        }
        if (parseOpen(data.parse_status)) {
          return;
        }
        if (data.exists) {
          applyPayload(data, setters);
          setEntry("form");
          setPolling(false);
          setNote(t.profileReviewFilledFromCv);
          await loadRoles();
          return;
        }
        setPolling(false);
      } catch {
        /* keep polling */
      }
    };
    const id = setInterval(tick, POLL_MS);
    tick();
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- poll while flagged
  }, [polling, allowed]);

  function buildBody(confirm) {
    const yearsValue = totalYears.trim() === "" ? null : Number(totalYears);
    return {
      confirm,
      headline,
      seniority,
      total_years: Number.isFinite(yearsValue) ? yearsValue : null,
      profile: {
        contact: { full_name: fullName, email, phone, city, country },
        links: {
          linkedin_url: linkedin.trim(),
          github: github.trim(),
          portfolio: portfolio.trim(),
        },
        headline,
        summary,
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
        work_history: work
          .filter((item) => item.title.trim() || item.company.trim())
          .map((item) => ({
            title: item.title,
            company: item.company,
            start: item.start,
            end: item.end || null,
            location: item.location || "",
            summary: item.summary || "",
            skills: item.skills || [],
            employment_type: item.employment_type || "",
          })),
        education: education
          .filter((item) => item.degree.trim() || item.field.trim() || item.school.trim() || item.year.trim())
          .map((item) => ({
            degree: item.degree,
            field: item.field,
            school: item.school,
            year: item.year.trim() === "" ? null : Number(item.year),
          })),
        languages: languages
          .filter((item) => item.code.trim())
          .map((item) => ({
            code: item.code.trim().toLowerCase(),
            level: item.level || "",
          })),
      },
    };
  }

  async function submit(confirm) {
    setError("");
    setNote("");
    setBusy(true);
    try {
      const res = await saveCvProfile(buildBody(confirm));
      if (!res.ok) {
        setError(t.profileReviewError);
        return;
      }
      const data = res.data;
      setPayload(data);
      applyPayload(data, setters);
      setEntry("form");
      setNote(confirm ? t.profileReviewConfirmed : t.profileReviewSaved);
      await loadRoles();
    } catch {
      setError(t.profileReviewError);
    } finally {
      setBusy(false);
    }
  }

  async function uploadCv(file) {
    if (!file) return;
    setError("");
    setNote("");
    setUploading(true);
    setCvName(file.name || "");
    try {
      const body = new FormData();
      body.set("cv", file);
      const res = await uploadCvProfile(body);
      if (!res.ok) {
        setError(res.status === 422 ? t.applyCvRequired : t.profileReviewUploadError);
        return;
      }
      const data = res.data;
      setPayload(data);
      setEntry("upload");
      setNote(t.profileReviewUploadQueued);
      setPolling(true);
      pollLeft.current = POLL_MAX;
    } catch {
      setError(t.profileReviewUploadError);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function startManual() {
    setError("");
    setNote("");
    setEntry("manual");
    setHeadline("");
    setSummary("");
    setSeniority("");
    setTotalYears("");
    setFullName("");
    setEmail("");
    setPhone("");
    setCity("");
    setCountry("");
    setLinkedin("");
    setGithub("");
    setPortfolio("");
    setSkills([]);
    setWork([emptyWork()]);
    setEducation([]);
    setLanguages([]);
    setLowFields([]);
  }

  function clearLocalForm() {
    setHeadline("");
    setSummary("");
    setSeniority("");
    setTotalYears("");
    setFullName("");
    setEmail("");
    setPhone("");
    setCity("");
    setCountry("");
    setLinkedin("");
    setGithub("");
    setPortfolio("");
    setSkills([]);
    setWork([]);
    setEducation([]);
    setLanguages([]);
    setSkillDraft("");
    setSkillYearsDraft("");
    setLowFields([]);
    setCvName("");
    setRolesPayload(null);
  }

  function stopParseLocally({ keepEntry = false } = {}) {
    pollEpoch.current += 1;
    setPolling(false);
    pollLeft.current = 0;
    setUploading(false);
    setPayload((prev) =>
      prev
        ? { ...prev, parse_status: "failed", needs_review: Boolean(prev.exists) }
        : { exists: false, parse_status: "failed", status: "empty" },
    );
    if (!keepEntry) setEntry(null);
  }

  async function cancelParse() {
    setError("");
    setNote("");
    setBusy(true);
    const hadProfile = Boolean(payload?.exists);
    // Optimistic: clear progress immediately so a late poll cannot stick the UI.
    stopParseLocally({ keepEntry: hadProfile });
    try {
      const res = await cancelCvParse();
      const data = res.data;
      if (!res.ok) {
        if (!hadProfile) setEntry(null);
        setError(t.profileReviewFailed);
        return;
      }
      setPayload(data);
      if (!data.exists) {
        setEntry(null);
      } else {
        applyPayload(data, setters);
        setEntry("form");
      }
      setNote(t.profileReviewCancelDone);
    } catch {
      if (!hadProfile) setEntry(null);
      setError(t.profileReviewFailed);
    } finally {
      setBusy(false);
    }
  }

  async function resetProfile() {
    if (!window.confirm(t.profileReviewResetConfirm)) return;
    setError("");
    setNote("");
    setBusy(true);
    pollEpoch.current += 1;
    setPolling(false);
    pollLeft.current = 0;
    try {
      const res = await deleteCvProfile();
      const data = res.data;
      if (!res.ok) {
        setError(t.profileReviewResetError);
        return;
      }
      setPayload(data);
      clearLocalForm();
      setEntry(null);
      setNote(t.profileReviewResetDone);
      await loadRoles();
    } catch {
      setError(t.profileReviewResetError);
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

  function addWork() {
    setWork((current) => [...current, emptyWork()]);
  }

  function removeWork(index) {
    setWork((current) => current.filter((_, i) => i !== index));
  }

  function updateEducation(index, patch) {
    setEducation((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function addEducation() {
    setEducation((current) => [...current, emptyEdu()]);
  }

  function removeEducation(index) {
    setEducation((current) => current.filter((_, i) => i !== index));
  }

  function updateLanguage(index, patch) {
    setLanguages((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function addLanguage() {
    setLanguages((current) => [...current, emptyLang()]);
  }

  function removeLanguage(index) {
    setLanguages((current) => current.filter((_, i) => i !== index));
  }

  const statusLabel =
    payload?.status === "confirmed" ? t.profileReviewStatusConfirmed : t.profileReviewStatusDraft;
  const warn = (field) => lowFields.includes(field);
  const showForm = entry === "form" || entry === "manual" || Boolean(payload?.exists);
  const showChooser = allowed && payload && !payload.exists && !parseOpen(payload.parse_status) && !entry;
  const isParsing = uploading || polling || parseOpen(payload?.parse_status);

  return (
    <Shell locale={locale} mode="profileReview">
      {me === undefined ? null : allowed ? (
        <div className="cabinet profile-review-page">
          <div className="cabinet-head">
            <div>
              <h1>{t.profileReviewTitle}</h1>
              <p className="lede">{t.profileReviewLede}</p>
            </div>
            <a className="btn ghost" href={hrefFor(locale, { mode: "profile" })}>
              {t.profileReviewBack}
            </a>
          </div>

          {error ? <p className="note profile-review-flash">{error}</p> : null}
          {note ? <p className="note profile-review-flash ok">{note}</p> : null}

          <input
            ref={fileRef}
            type="file"
            accept={CV_ACCEPT}
            hidden
            onChange={(event) => uploadCv(event.target.files?.[0] || null)}
          />

          {showChooser ? (
            <section className="profile-review-chooser" aria-label={t.profileReviewChooserTitle}>
              <h2>{t.profileReviewChooserTitle}</h2>
              <p className="hint">{t.profileReviewChooserLede}</p>
              {payload.parse_status === "failed" ? <p className="hint">{t.profileReviewFailed}</p> : null}
              <div className="profile-review-options">
                <button
                  type="button"
                  className="profile-review-option"
                  onClick={() => {
                    setEntry("upload");
                    fileRef.current?.click();
                  }}
                >
                  <strong>{t.profileReviewOptionUpload}</strong>
                  <span>{t.profileReviewOptionUploadHint}</span>
                </button>
                <button type="button" className="profile-review-option" onClick={startManual}>
                  <strong>{t.profileReviewOptionManual}</strong>
                  <span>{t.profileReviewOptionManualHint}</span>
                </button>
              </div>
            </section>
          ) : null}

          {(entry === "upload" || showForm || isParsing) && !showChooser ? (
            <section className={`profile-review-source${isParsing ? " is-parsing" : ""}`}>
              {isParsing ? (
                <ParseProgress
                  t={t}
                  uploading={uploading}
                  parseStatus={payload?.parse_status}
                  fileName={cvName}
                  onCancel={cancelParse}
                  cancelBusy={busy}
                />
              ) : (
                <>
                  <div className="profile-review-source-copy">
                    <h2>{t.profileReviewUploadTitle}</h2>
                    <p className="hint">
                      {cvName ? t.profileReviewUploadedName(cvName) : t.profileReviewUploadHint}
                    </p>
                  </div>
                  <div className="profile-review-source-actions">
                    <button
                      type="button"
                      className="btn primary"
                      disabled={uploading || busy}
                      onClick={() => fileRef.current?.click()}
                    >
                      {showForm ? t.profileReviewReuploadCta : t.profileReviewUploadCta}
                    </button>
                    {!showForm ? (
                      <button type="button" className="btn ghost" onClick={startManual} disabled={uploading}>
                        {t.profileReviewOptionManual}
                      </button>
                    ) : null}
                  </div>
                </>
              )}
            </section>
          ) : null}

          {showForm ? (
            <form
              className="profile-review-form"
              onSubmit={(event) => {
                event.preventDefault();
                submit(false);
              }}
            >
              <div className="profile-review-meta">
                <span className={`profile-review-status status-${payload?.status || "draft"}`}>
                  {payload?.exists ? statusLabel : t.profileReviewStatusDraft}
                </span>
                {typeof payload?.confidence === "number" ? (
                  <span className="hint">{t.profileReviewConfidence(payload.confidence)}</span>
                ) : null}
                {entry === "manual" && !payload?.exists ? (
                  <span className="hint">{t.profileReviewManualBadge}</span>
                ) : null}
              </div>

              <div className="profile-review-layout">
                <section className={`review-panel review-panel-contact${warn("contact") ? " field-warn" : ""}`}>
                  <header className="review-panel-head">
                    <h2>{t.profileReviewContact}</h2>
                    <FieldMark show={warn("contact")} label={t.profileReviewCheck} />
                  </header>
                  <div className="profile-grid profile-grid-contact">
                    <label>
                      {t.profileReviewFullName}
                      <input
                        value={fullName}
                        maxLength={120}
                        onChange={(event) => setFullName(event.target.value)}
                      />
                    </label>
                    <label>
                      {t.applyEmail}
                      <input
                        type="email"
                        value={email}
                        maxLength={120}
                        onChange={(event) => setEmail(event.target.value)}
                      />
                    </label>
                    <label>
                      {t.applyPhone}
                      <input
                        type="tel"
                        value={phone}
                        maxLength={40}
                        onChange={(event) => setPhone(event.target.value)}
                      />
                    </label>
                    <label>
                      {t.profileReviewCity}
                      <input
                        value={city}
                        maxLength={120}
                        onChange={(event) => setCity(event.target.value)}
                      />
                    </label>
                    <label>
                      {t.profileReviewCountry}
                      <input
                        value={country}
                        maxLength={120}
                        onChange={(event) => setCountry(event.target.value)}
                      />
                    </label>
                  </div>
                </section>

                <section className="review-panel review-panel-links">
                  <header className="review-panel-head">
                    <h2>{t.profileReviewLinks}</h2>
                  </header>
                  <div className="profile-grid profile-grid-links">
                    <label>
                      {t.profileReviewLinkedin}
                      <input
                        type="url"
                        value={linkedin}
                        maxLength={300}
                        placeholder="https://linkedin.com/in/…"
                        onChange={(event) => setLinkedin(event.target.value)}
                      />
                    </label>
                    <label>
                      {t.profileReviewGithub}
                      <input
                        type="url"
                        value={github}
                        maxLength={300}
                        placeholder="https://github.com/…"
                        onChange={(event) => setGithub(event.target.value)}
                      />
                    </label>
                    <label className="profile-span">
                      {t.profileReviewPortfolio}
                      <input
                        type="url"
                        value={portfolio}
                        maxLength={300}
                        placeholder="https://"
                        onChange={(event) => setPortfolio(event.target.value)}
                      />
                    </label>
                  </div>
                </section>

                <section className="review-panel review-panel-basics">
                  <header className="review-panel-head">
                    <h2>{t.profileReviewBasics}</h2>
                  </header>
                  <div className="profile-grid profile-grid-basics">
                    <label className={`profile-span${warn("headline") ? " field-warn" : ""}`}>
                      {t.profileReviewHeadline}
                      <FieldMark show={warn("headline")} label={t.profileReviewCheck} />
                      <input
                        value={headline}
                        maxLength={200}
                        onChange={(event) => setHeadline(event.target.value)}
                      />
                    </label>
                    <label className="profile-span">
                      {t.profileReviewAbout}
                      <textarea
                        value={summary}
                        maxLength={2000}
                        rows={3}
                        placeholder={t.profileReviewAboutHint}
                        onChange={(event) => setSummary(event.target.value)}
                      />
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
                </section>

                <section className={`review-panel review-panel-skills${warn("skills") ? " field-warn" : ""}`}>
                  <header className="review-panel-head">
                    <h2>{t.profileReviewSkills}</h2>
                    <FieldMark show={warn("skills")} label={t.profileReviewCheck} />
                  </header>
                  <div className="skill-chip-box">
                    {skills.length ? (
                      <div className="skill-chip-cloud" role="list">
                        {skills.map((skill, index) => (
                          <div key={`${skill.name}-${index}`} className="skill-pill" role="listitem">
                            <button
                              type="button"
                              className="skill-pill-main"
                              title={t.profileReviewSkillEdit}
                              onClick={() => {
                                setSkillDraft(skill.name);
                                setSkillYearsDraft(skill.years || "");
                                removeSkill(index);
                              }}
                            >
                              <span className="skill-pill-name">{skill.name}</span>
                              {skill.years ? (
                                <span className="skill-pill-years">
                                  {skill.years} {t.profileReviewSkillYears}
                                </span>
                              ) : null}
                            </button>
                            <button
                              type="button"
                              className="skill-pill-remove"
                              onClick={() => removeSkill(index)}
                              aria-label={t.profileReviewRemove}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="hint">{t.profileReviewSkillsEmpty}</p>
                    )}
                    <div className="skill-add-row">
                      <input
                        value={skillDraft}
                        maxLength={60}
                        placeholder={t.profileReviewSkillName}
                        onChange={(event) => setSkillDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") addSkill(event);
                        }}
                      />
                      <input
                        type="number"
                        min="0"
                        max="60"
                        step="0.5"
                        value={skillYearsDraft}
                        placeholder={t.profileReviewSkillYears}
                        onChange={(event) => setSkillYearsDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") addSkill(event);
                        }}
                      />
                      <button type="button" className="btn" onClick={addSkill}>
                        {t.profileReviewSkillAdd}
                      </button>
                    </div>
                  </div>
                </section>

                <section className={`review-panel review-panel-work${warn("work_history") ? " field-warn" : ""}`}>
                  <header className="review-panel-head">
                    <h2>{t.profileReviewWork}</h2>
                    <FieldMark show={warn("work_history")} label={t.profileReviewCheck} />
                  </header>
                  {work.length === 0 ? <p className="hint">{t.profileReviewWorkEmpty}</p> : null}
                  {work.map((job, index) => (
                    <div key={`job-${index}`} className="work-block">
                      <div className="work-block-head">
                        <span className="hint">{t.profileReviewWorkItem(index + 1)}</span>
                        <button type="button" className="btn ghost small" onClick={() => removeWork(index)}>
                          {t.profileReviewRemove}
                        </button>
                      </div>
                      <div className="profile-grid profile-grid-work">
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
                        <label className="profile-span">
                          {t.profileReviewLocation}
                          <input
                            value={job.location || ""}
                            maxLength={120}
                            onChange={(event) => updateWork(index, { location: event.target.value })}
                          />
                        </label>
                        <label className="profile-span">
                          {t.profileReviewJobSummary}
                          <textarea
                            value={job.summary || ""}
                            maxLength={2000}
                            rows={2}
                            onChange={(event) => updateWork(index, { summary: event.target.value })}
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                  <button type="button" className="btn ghost" onClick={addWork}>
                    {t.profileReviewWorkAdd}
                  </button>
                </section>

                <div className="profile-review-side">
                  <section className="review-panel">
                    <header className="review-panel-head">
                      <h2>{t.profileReviewEducation}</h2>
                    </header>
                    {education.length === 0 ? <p className="hint">{t.profileReviewEducationEmpty}</p> : null}
                    {education.map((item, index) => (
                      <div key={`edu-${index}`} className="work-block">
                        <div className="work-block-head">
                          <span className="hint">{t.profileReviewEducationItem(index + 1)}</span>
                          <button type="button" className="btn ghost small" onClick={() => removeEducation(index)}>
                            {t.profileReviewRemove}
                          </button>
                        </div>
                        <div className="profile-grid profile-grid-work">
                          <label>
                            {t.profileReviewDegree}
                            <input
                              value={item.degree}
                              maxLength={120}
                              onChange={(event) => updateEducation(index, { degree: event.target.value })}
                            />
                          </label>
                          <label>
                            {t.profileReviewField}
                            <input
                              value={item.field}
                              maxLength={120}
                              onChange={(event) => updateEducation(index, { field: event.target.value })}
                            />
                          </label>
                          <label>
                            {t.profileReviewSchool}
                            <input
                              value={item.school}
                              maxLength={120}
                              onChange={(event) => updateEducation(index, { school: event.target.value })}
                            />
                          </label>
                          <label>
                            {t.profileReviewEduYear}
                            <input
                              type="number"
                              min="1950"
                              max="2100"
                              value={item.year}
                              onChange={(event) => updateEducation(index, { year: event.target.value })}
                            />
                          </label>
                        </div>
                      </div>
                    ))}
                    <button type="button" className="btn ghost" onClick={addEducation}>
                      {t.profileReviewEducationAdd}
                    </button>
                  </section>

                  <section className="review-panel">
                    <header className="review-panel-head">
                      <h2>{t.profileReviewLanguages}</h2>
                    </header>
                    {languages.length === 0 ? <p className="hint">{t.profileReviewLanguagesEmpty}</p> : null}
                    {languages.map((item, index) => (
                      <div key={`lang-${index}`} className="profile-grid profile-grid-lang">
                        <label>
                          {t.profileReviewLangCode}
                          <select value={item.code} onChange={(event) => updateLanguage(index, { code: event.target.value })}>
                            <option value="">—</option>
                            {LANG_CODES.map((code) => (
                              <option key={code} value={code}>
                                {t.profileReviewLangLabel(code)}
                              </option>
                            ))}
                            {item.code && !LANG_CODES.includes(item.code) ? (
                              <option value={item.code}>{item.code}</option>
                            ) : null}
                          </select>
                        </label>
                        <label>
                          {t.profileReviewLangLevel}
                          <select
                            value={item.level}
                            onChange={(event) => updateLanguage(index, { level: event.target.value })}
                          >
                            {LANG_LEVELS.map((level) => (
                              <option key={level || "empty"} value={level}>
                                {level === "native" ? t.profileReviewLangNative : level || "—"}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button type="button" className="btn ghost small" onClick={() => removeLanguage(index)}>
                          {t.profileReviewRemove}
                        </button>
                      </div>
                    ))}
                    <button type="button" className="btn ghost" onClick={addLanguage}>
                      {t.profileReviewLanguageAdd}
                    </button>
                  </section>

                  {rolesPayload ? (
                    <section className="review-panel review-panel-muted">
                      <header className="review-panel-head">
                        <h2>{t.profileReviewRolesTitle}</h2>
                      </header>
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
                              <RoleSkillParts t={t} have={role.have} missing={role.missing} />
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                  ) : null}
                </div>
              </div>

              <div className="profile-review-actions">
                <button
                  type="button"
                  className="btn red"
                  disabled={busy || uploading}
                  onClick={resetProfile}
                >
                  {t.profileReviewReset}
                </button>
                <button type="submit" className="btn" disabled={busy || uploading}>
                  {t.profileReviewSave}
                </button>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy || uploading}
                  onClick={() => submit(true)}
                >
                  {t.profileReviewConfirm}
                </button>
              </div>
            </form>
          ) : null}
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
