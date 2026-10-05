"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { ConsentFields, grantsFromPayload } from "./consent-fields";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ProfileForm({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);
  const [companyName, setCompanyName] = useState("");
  const [city, setCity] = useState("");
  const [about, setAbout] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [companyError, setCompanyError] = useState("");
  const [companyNote, setCompanyNote] = useState("");
  const [applicantError, setApplicantError] = useState("");
  const [applicantNote, setApplicantNote] = useState("");
  const [consentPayload, setConsentPayload] = useState(null);
  const [grants, setGrants] = useState({ matching: false, emails: false, recruiter_visibility: false });
  const [visibility, setVisibility] = useState("anonymous");
  const [privacyError, setPrivacyError] = useState("");
  const [privacyNote, setPrivacyNote] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        const company = data.company_profile || {};
        const person = data.candidate_profile || {};
        setCompanyName(company.company_name || "");
        setCity(company.city || "");
        setAbout(company.about || "");
        setDisplayName(person.display_name || "");
        setPhone(person.phone || "");
        setEmail(person.email || "");
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const showCompany = Boolean(me?.authenticated && (me.employer || me.staff));
  const showApplicant = Boolean(me?.authenticated && (me.candidate || me.staff));

  useEffect(() => {
    if (!showApplicant) return undefined;
    let cancelled = false;
    fetch(`/api/auth/consents?lang=${encodeURIComponent(locale)}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setConsentPayload(data);
        setGrants(grantsFromPayload(data));
        setVisibility(data.visibility || "anonymous");
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [showApplicant, locale]);

  async function saveCompany(event) {
    event.preventDefault();
    setCompanyError("");
    setCompanyNote("");
    const res = await fetch("/api/auth/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_name: companyName, city, about }),
    });
    if (!res.ok) {
      setCompanyError(t.companyRequired);
      return;
    }
    setCompanyNote(t.companySaved);
  }

  function applicantProblem() {
    if (!displayName.trim()) return t.profileNameRequired;
    const digits = phone.replace(/\D/g, "");
    if (phone.trim() && (digits.length < 5 || phone.trim().length > 40)) return t.applyPhoneInvalid;
    if (email.trim() && !EMAIL_OK.test(email.trim())) return t.applyEmailInvalid;
    return "";
  }

  async function saveApplicant(event) {
    event.preventDefault();
    setApplicantError("");
    setApplicantNote("");
    const problem = applicantProblem();
    if (problem) {
      setApplicantError(problem);
      return;
    }
    const res = await fetch("/api/auth/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: displayName, phone, email }),
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof payload.detail === "string" ? payload.detail : "";
      if (detail.includes("Telefon")) setApplicantError(t.applyPhoneInvalid);
      else if (detail.includes("E-poçt") || detail.toLowerCase().includes("email")) setApplicantError(t.applyEmailInvalid);
      else setApplicantError(t.profileNameRequired);
      return;
    }
    const person = payload.candidate_profile || {};
    setDisplayName(person.display_name || displayName);
    setPhone(person.phone || "");
    setEmail(person.email || "");
    setApplicantNote(t.profileSaved);
  }

  async function savePrivacy(event) {
    event.preventDefault();
    setPrivacyError("");
    setPrivacyNote("");
    const res = await fetch(`/api/auth/consents?lang=${encodeURIComponent(locale)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...grants, visibility }),
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      setPrivacyError(t.privacyError);
      return;
    }
    setConsentPayload(payload);
    setGrants(grantsFromPayload(payload));
    setVisibility(payload.visibility || visibility);
    setPrivacyNote(t.privacySaved);
  }

  async function exportMyData() {
    setPrivacyError("");
    setPrivacyNote("");
    setPrivacyBusy("export");
    try {
      const res = await fetch("/api/auth/me/export", { cache: "no-store" });
      if (!res.ok) {
        setPrivacyError(t.privacyExportError);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "ingress-job-export.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setPrivacyError(t.privacyExportError);
    } finally {
      setPrivacyBusy("");
    }
  }

  async function deleteMyData() {
    if (!window.confirm(t.privacyDeleteConfirm)) return;
    setPrivacyError("");
    setPrivacyNote("");
    setPrivacyBusy("delete");
    try {
      const res = await fetch("/api/auth/me", { method: "DELETE" });
      if (!res.ok) {
        setPrivacyError(t.privacyDeleteError);
        return;
      }
      clearMeCache();
      setConsentPayload(null);
      setDisplayName("");
      setPhone("");
      setEmail("");
      setPrivacyNote(t.privacyDeleteDone);
    } catch {
      setPrivacyError(t.privacyDeleteError);
    } finally {
      setPrivacyBusy("");
    }
  }

  const layoutClass = [
    "profile-layout",
    showCompany && showApplicant ? "profile-layout-dual" : "",
    !showCompany && showApplicant && consentPayload ? "profile-layout-split" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Shell locale={locale} mode="profile">
      {me === undefined ? null : showCompany || showApplicant ? (
        <div className="cabinet profile-page">
          <div className="cabinet-head">
            <div>
              <h1>{t.profileTitle}</h1>
              <p className="lede">{t.profileLede}</p>
            </div>
          </div>
          <div className={layoutClass}>
            {showCompany ? (
              <form className="form-card profile-card" onSubmit={saveCompany}>
                <div className="cabinet-form-head">
                  <h2>{t.companyTitle}</h2>
                  <p className="hint">{t.profileCompanyLede}</p>
                </div>
                {companyError ? <p className="note">{companyError}</p> : null}
                {companyNote ? <p className="note">{companyNote}</p> : null}
                <div className="profile-grid">
                  <label>
                    {t.companyName}
                    <input value={companyName} maxLength={120} required onChange={(event) => setCompanyName(event.target.value)} />
                  </label>
                  <label>
                    {t.companyCity}
                    <input value={city} maxLength={80} required onChange={(event) => setCity(event.target.value)} />
                  </label>
                  <label className="profile-span">
                    {t.companyAbout}
                    <textarea value={about} maxLength={400} required rows={3} onChange={(event) => setAbout(event.target.value)} />
                  </label>
                </div>
                <div className="ad-actions">
                  <button type="submit" className="btn primary">{t.companySave}</button>
                </div>
              </form>
            ) : null}
            {showApplicant ? (
              <form className="form-card profile-card" onSubmit={saveApplicant}>
                <div className="cabinet-form-head">
                  <h2>{t.profileApplicantTitle}</h2>
                  <p className="hint">{t.profileApplicantLede}</p>
                  <p className="hint">
                    <a href={hrefFor(locale, { mode: "profileReview" })}>{t.profileReviewOpen}</a>
                  </p>
                </div>
                {applicantError ? <p className="note">{applicantError}</p> : null}
                {applicantNote ? <p className="note">{applicantNote}</p> : null}
                <div className="profile-grid">
                  <label className="profile-span">
                    {t.profileName}
                    <input value={displayName} maxLength={80} required onChange={(event) => setDisplayName(event.target.value)} />
                  </label>
                  <label>
                    {t.applyPhone}
                    <span className="hint">{t.adOptional}</span>
                    <input type="tel" value={phone} maxLength={40} onChange={(event) => setPhone(event.target.value)} />
                  </label>
                  <label>
                    {t.applyEmail}
                    <span className="hint">{t.adOptional}</span>
                    <input type="email" value={email} maxLength={120} onChange={(event) => setEmail(event.target.value)} />
                  </label>
                </div>
                <div className="ad-actions">
                  <button type="submit" className="btn primary">{t.companySave}</button>
                </div>
              </form>
            ) : null}
            {showApplicant && consentPayload ? (
              <form className="form-card profile-card profile-privacy" onSubmit={savePrivacy}>
                <div className="cabinet-form-head">
                  <h2>{t.privacyTitle}</h2>
                  <p className="hint">{t.privacyLede}</p>
                  <p className="hint">
                    <a href={hrefFor(locale, { mode: "emailSettings" })}>{t.emailSettingsOpen}</a>
                  </p>
                </div>
                {privacyError ? <p className="note">{privacyError}</p> : null}
                {privacyNote ? <p className="note">{privacyNote}</p> : null}
                <ConsentFields
                  payload={consentPayload}
                  grants={grants}
                  visibility={visibility}
                  onGrantChange={(kind, value) => setGrants((current) => ({ ...current, [kind]: value }))}
                  onVisibilityChange={setVisibility}
                  idPrefix="profile-consent"
                />
                <div className="ad-actions">
                  <button type="submit" className="btn primary">{t.companySave}</button>
                </div>
                {Array.isArray(consentPayload.privacy_rights) && consentPayload.privacy_rights.length ? (
                  <div className="privacy-rights">
                    {consentPayload.retention_stub ? (
                      <p className="hint">{consentPayload.retention_stub}</p>
                    ) : null}
                    {consentPayload.privacy_rights.map((right) => (
                      <div key={right.id} className="privacy-right-item">
                        <div>
                          <strong>{right.label}</strong>
                          {right.description ? <p className="hint">{right.description}</p> : null}
                        </div>
                        {right.id === "export" ? (
                          <button
                            type="button"
                            className="btn"
                            disabled={Boolean(privacyBusy)}
                            onClick={exportMyData}
                          >
                            {right.label}
                          </button>
                        ) : null}
                        {right.id === "delete" ? (
                          <button
                            type="button"
                            className="btn"
                            disabled={Boolean(privacyBusy)}
                            onClick={deleteMyData}
                          >
                            {right.label}
                          </button>
                        ) : null}
                        {right.id === "who_viewed" ? (
                          <p className="hint">{t.privacyWhoViewedSoon}</p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </form>
            ) : null}
          </div>
        </div>
      ) : (
        <section className="empty profile-gate">
          <h1>{t.profileTitle}</h1>
          <p className="lede">{t.profileGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "profile" })} />
        </section>
      )}
    </Shell>
  );
}
