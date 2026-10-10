"use client";

import { useEffect, useRef, useState } from "react";
import { beginLogin } from "../../lib/auth-link";
import { hrefFor, text } from "../../lib/copy";
import { LoginLink } from "../login-link";

const POLL_MS = 2500;
const POLL_MAX = 20;

function aiErrorMessage(t, code) {
  const raw = String(code || "").trim();
  if (!raw || raw === "ai_pending") return "";
  if (raw === "job_tailored_cv_disabled" || raw === "ai_disabled") return t.jdTailoredCvAiOff;
  if (raw === "ai_no_key") return t.jdTailoredCvErrorNoKey;
  if (raw.includes("budget")) return t.jdTailoredCvErrorBudget;
  if (raw.includes("provider") || raw === "ai_failed") return t.jdTailoredCvErrorProvider;
  if (raw === "ai_validation_failed") return t.jdTailoredCvErrorValidation;
  return t.jdTailoredCvErrorCode(raw);
}

function contactLine(contact) {
  if (!contact || typeof contact !== "object") return "";
  return [contact.email, contact.phone, [contact.city, contact.country].filter(Boolean).join(", ")]
    .filter(Boolean)
    .join(" · ");
}

function TailoredCvDocument({ t, cv }) {
  if (!cv || typeof cv !== "object") return null;
  const contact = contactLine(cv.contact);
  const skills = Array.isArray(cv.skills) ? cv.skills : [];
  const experience = Array.isArray(cv.experience) ? cv.experience : [];
  const education = Array.isArray(cv.education) ? cv.education : [];
  const languages = Array.isArray(cv.languages) ? cv.languages : [];

  return (
    <article className="jd-tcv-doc" id="jd-tcv-print-root">
      <header className="jd-tcv-doc-head">
        {cv.full_name ? <h3 className="jd-tcv-name">{cv.full_name}</h3> : null}
        {cv.headline ? <p className="jd-tcv-headline">{cv.headline}</p> : null}
        {contact ? <p className="jd-tcv-contact">{contact}</p> : null}
      </header>

      {cv.summary ? (
        <section className="jd-tcv-section">
          <h4>{t.jdTailoredCvSectionSummary}</h4>
          <p>{cv.summary}</p>
        </section>
      ) : null}

      {skills.length ? (
        <section className="jd-tcv-section">
          <h4>{t.jdTailoredCvSectionSkills}</h4>
          <p className="jd-tcv-skills">{skills.join(" · ")}</p>
        </section>
      ) : null}

      {experience.length ? (
        <section className="jd-tcv-section">
          <h4>{t.jdTailoredCvSectionExperience}</h4>
          <ul className="jd-tcv-exp-list">
            {experience.map((role, idx) => (
              <li key={`${role.company}-${role.title}-${idx}`}>
                <div className="jd-tcv-role-top">
                  <strong>
                    {[role.title, role.company].filter(Boolean).join(" — ")}
                  </strong>
                  {role.dates ? <span className="jd-tcv-dates">{role.dates}</span> : null}
                </div>
                {Array.isArray(role.bullets) && role.bullets.length ? (
                  <ul className="jd-tcv-bullets">
                    {role.bullets.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {education.length ? (
        <section className="jd-tcv-section">
          <h4>{t.jdTailoredCvSectionEducation}</h4>
          <ul className="jd-tcv-edu-list">
            {education.map((item, idx) => (
              <li key={`${item.school}-${idx}`}>
                <strong>{[item.degree, item.school].filter(Boolean).join(" — ")}</strong>
                {item.dates ? <span className="jd-tcv-dates"> {item.dates}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {languages.length ? (
        <section className="jd-tcv-section">
          <h4>{t.jdTailoredCvSectionLanguages}</h4>
          <p>{languages.join(" · ")}</p>
        </section>
      ) : null}
    </article>
  );
}

export function JobDetailTailoredCvPanel({ locale, jobId, returnTo, open, preview = false }) {
  const t = text(locale);
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const pollLeft = useRef(0);

  useEffect(() => {
    if (!open || preview || !jobId) return undefined;
    let cancelled = false;
    let timer = 0;
    setLoading(true);
    setError("");
    setPayload(null);
    pollLeft.current = POLL_MAX;

    async function load(refresh = false) {
      const qs = new URLSearchParams({ lang: locale || "az" });
      if (refresh) qs.set("refresh", "1");
      const res = await fetch(`/api/auth/me/jobs/${jobId}/tailored-cv?${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh: Boolean(refresh) }),
        cache: "no-store",
      });
      if (res.status === 401 || res.status === 403) {
        beginLogin({ intent: "job_candidate", returnTo });
        return null;
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load");
      return data;
    }

    function finish(data) {
      if (cancelled || !data) return;
      setPayload(data);
      setLoading(Boolean(data.ai_pending));
      if (data.ai_pending && pollLeft.current > 0) {
        pollLeft.current -= 1;
        timer = window.setTimeout(() => {
          load(false)
            .then(finish)
            .catch(() => {
              if (!cancelled) {
                setError(t.jdTailoredCvErrorProvider);
                setLoading(false);
              }
            });
        }, POLL_MS);
      } else if (data.ai_pending) {
        setError(t.jdTailoredCvErrorProvider);
        setLoading(false);
      }
    }

    load(false)
      .then(finish)
      .catch(() => {
        if (!cancelled) {
          setError(t.jdTailoredCvErrorProvider);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [open, preview, jobId, locale, returnTo, t.jdTailoredCvErrorProvider]);

  if (!open) return null;

  const status = payload?.status || "";
  const cv = payload?.cv && typeof payload.cv === "object" ? payload.cv : null;
  const aiErr = aiErrorMessage(t, payload?.ai_error || error);

  function onPrint() {
    const root = document.getElementById("jd-tcv-print-root");
    if (!root) return;
    document.body.classList.add("jd-tcv-printing");
    const cleanup = () => {
      document.body.classList.remove("jd-tcv-printing");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.print();
    window.setTimeout(cleanup, 1500);
  }

  return (
    <section className="jd-tailored-cv" id="jd-tailored-cv-panel" aria-labelledby="jd-tailored-cv-title">
      <div className="jd-tailored-cv-head">
        <h2 id="jd-tailored-cv-title">{t.jdTailoredCvTitle}</h2>
        {loading || payload?.ai_pending ? (
          <p className="jd-tailored-cv-status" role="status">
            {t.jdTailoredCvPending}
          </p>
        ) : null}
      </div>

      {preview ? <p className="jd-tailored-cv-gate">{t.jdTailoredCvPreview}</p> : null}

      {!preview && status === "needs_consent" ? (
        <div className="jd-tailored-cv-gate">
          <p>{t.jdTailoredCvConsent}</p>
          <a className="jd-btn jd-btn-outline" href={hrefFor(locale, { mode: "profile" })}>
            {t.jdTailoredCvConsentCta}
          </a>
        </div>
      ) : null}

      {!preview && status === "needs_profile" ? (
        <div className="jd-tailored-cv-gate">
          <p>{t.jdTailoredCvSkills}</p>
          <a className="jd-btn jd-btn-outline" href={hrefFor(locale, { mode: "profileReview" })}>
            {t.jdTailoredCvSkillsCta}
          </a>
        </div>
      ) : null}

      {!preview && !payload && !loading ? (
        <div className="jd-tailored-cv-gate">
          <p>{t.jdTailoredCvGuest}</p>
          <LoginLink intent="job_candidate" returnTo={returnTo} className="btn small">
            {t.jdTailoredCvGuestCta}
          </LoginLink>
        </div>
      ) : null}

      {!preview && status === "ok" && !cv && !loading && !payload?.ai_pending ? (
        <p className="jd-tailored-cv-error" role="alert">
          {aiErr || t.jdTailoredCvErrorProvider}
        </p>
      ) : null}

      {!preview && aiErr && (cv || payload?.ai_pending) ? (
        <p className="jd-tailored-cv-note" role="status">
          {aiErr}
        </p>
      ) : null}

      {!preview && cv ? (
        <div className="jd-tailored-cv-body">
          <TailoredCvDocument t={t} cv={cv} />
          <div className="jd-tailored-cv-actions">
            <button type="button" className="btn small" onClick={onPrint}>
              {t.jdTailoredCvPrint}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
