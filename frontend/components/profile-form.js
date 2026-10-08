"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { exportMyData, saveCompanyProfile, saveConsents } from "../lib/server/refresh";
import { ConsentFields, grantsFromPayload } from "./consent-fields";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function applyMe(data, setters) {
  if (!data || typeof data !== "object") return;
  const company = data.company_profile || {};
  const person = data.candidate_profile || {};
  setters.setCompanyName(company.company_name || "");
  setters.setCity(company.city || "");
  setters.setAbout(company.about || "");
  setters.setDisplayName(person.display_name || "");
  setters.setPhone(person.phone || "");
  setters.setEmail(person.email || "");
}

function consentsLang(locale) {
  return locale === "en" || locale === "ru" ? locale : "az";
}

export function ProfileForm({ locale }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [companyName, setCompanyName] = useState(() => initialMe?.company_profile?.company_name || "");
  const [city, setCity] = useState(() => initialMe?.company_profile?.city || "");
  const [about, setAbout] = useState(() => initialMe?.company_profile?.about || "");
  const [displayName, setDisplayName] = useState(() => initialMe?.candidate_profile?.display_name || "");
  const [phone, setPhone] = useState(() => initialMe?.candidate_profile?.phone || "");
  const [email, setEmail] = useState(() => initialMe?.candidate_profile?.email || "");
  const [companyError, setCompanyError] = useState("");
  const [companyNote, setCompanyNote] = useState("");
  const [applicantError, setApplicantError] = useState("");
  const [applicantNote, setApplicantNote] = useState("");
  const seededConsents =
    initialMe?.consents && initialMe.consents.lang === consentsLang(locale) ? initialMe.consents : null;
  const [consentPayload, setConsentPayload] = useState(seededConsents);
  const [grants, setGrants] = useState(() => grantsFromPayload(seededConsents));
  const [visibility, setVisibility] = useState(() => seededConsents?.visibility || "anonymous");
  const [privacyError, setPrivacyError] = useState("");
  const [privacyNote, setPrivacyNote] = useState("");
  const [privacyBusy, setPrivacyBusy] = useState("");

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe);
      applyMe(initialMe, { setCompanyName, setCity, setAbout, setDisplayName, setPhone, setEmail });
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        applyMe(data, { setCompanyName, setCity, setAbout, setDisplayName, setPhone, setEmail });
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  const showCompany = Boolean(me?.authenticated && (me.employer || me.staff));
  const showApplicant = Boolean(me?.authenticated && (me.candidate || me.staff));

  useEffect(() => {
    if (!showApplicant) return undefined;
    const seeded = me?.consents;
    if (seeded && seeded.lang === consentsLang(locale)) {
      setConsentPayload(seeded);
      setGrants(grantsFromPayload(seeded));
      setVisibility(seeded.visibility || "anonymous");
      return undefined;
    }
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
  }, [showApplicant, locale, me]);

  async function saveCompany(event) {
    event.preventDefault();
    setCompanyError("");
    setCompanyNote("");
    const res = await saveCompanyProfile({ company_name: companyName, city, about });
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
    const res = await saveConsents(locale, { ...grants, visibility });
    const payload = res.data || {};
    if (!res.ok) {
      setPrivacyError(t.privacyError);
      return;
    }
    setConsentPayload(payload);
    setGrants(grantsFromPayload(payload));
    setVisibility(payload.visibility || visibility);
    setPrivacyNote(t.privacySaved);
  }

  async function downloadExport() {
    setPrivacyError("");
    setPrivacyNote("");
    setPrivacyBusy("export");
    try {
      const res = await exportMyData();
      if (!res.ok || !res.base64) {
        setPrivacyError(t.privacyExportError);
        return;
      }
      const binary = atob(res.base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: res.contentType || "application/zip" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = res.filename || "ingress-job-export.zip";
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
        <div className="h2-candidate profile-page">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.profileTitle}
            actions={
              showApplicant ? (
                <a className="btn small ink" href={hrefFor(locale, { mode: "profileReview" })}>
                  {t.profileReviewOpen}
                </a>
              ) : null
            }
          />
          <div className={layoutClass}>
            {showCompany ? (
              <form className="h2-panel h2-form" onSubmit={saveCompany}>
                <h2 className="h2-panel-title">{t.companyTitle}</h2>
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
                  <button type="submit" className="btn ink">{t.companySave}</button>
                </div>
              </form>
            ) : null}
            {showApplicant ? (
              <form className="h2-panel h2-form" onSubmit={saveApplicant}>
                <h2 className="h2-panel-title">{t.profileApplicantTitle}</h2>
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
                  <button type="submit" className="btn ink">{t.companySave}</button>
                </div>
              </form>
            ) : null}
            {showApplicant && consentPayload ? (
              <form className="h2-panel h2-form profile-privacy" onSubmit={savePrivacy}>
                <h2 className="h2-panel-title">{t.privacyTitle}</h2>
                <p className="hint">
                  <a href={hrefFor(locale, { mode: "emailSettings" })}>{t.emailSettingsOpen}</a>
                </p>
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
                  <button type="submit" className="btn ink">{t.companySave}</button>
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
                            onClick={downloadExport}
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
        <div className="h2-candidate">
          <PageChrome backHref={hrefFor(locale)} backLabel={t.breadcrumbHome} title={t.profileTitle} />
          <div className="h2-empty h2-gate">
            <p>{t.profileGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "profile" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
