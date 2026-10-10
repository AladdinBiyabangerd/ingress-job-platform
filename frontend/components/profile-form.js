"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { exportMyData, saveConsents } from "../lib/server/refresh";
import { BoardSideNav } from "./board-side-nav";
import { ConsentFields, grantsFromPayload } from "./consent-fields";
import { LoginLink } from "./login-link";
import { useInitialMe } from "./me-seed";
import { Shell } from "./shell";

const EMAIL_OK = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function applyMe(data, setters) {
  if (!data || typeof data !== "object") return;
  const person = data.candidate_profile || {};
  setters.setDisplayName(person.display_name || "");
  setters.setPhone(person.phone || "");
  setters.setEmail(person.email || "");
}

function consentsLang(locale) {
  return locale === "en" || locale === "ru" ? locale : "az";
}

function ProfileHero({ locale, showApplicant, guest }) {
  const t = text(locale);
  const back = hrefFor(locale, { mode: "profile" });
  return (
    <header className="profile-board-head">
      <div className="profile-board-head-copy">
        <h1 id="profile-front-title" className="profile-board-title">
          {t.profileTitle}
        </h1>
        {guest ? <p className="profile-board-gate-hint">{t.profileGateTitle}</p> : null}
      </div>
      {showApplicant ? (
        <a className="btn small ink" href={hrefFor(locale, { mode: "profileReview" })}>
          {t.profileReviewOpen}
        </a>
      ) : null}
      {guest ? (
        <div className="profile-board-gate-actions">
          <LoginLink className="btn small board-auth-signin" intent="job_candidate" returnTo={back}>
            {t.signIn}
          </LoginLink>
          <LoginLink className="btn small primary" intent="job_candidate" returnTo={back}>
            {t.createAccount}
          </LoginLink>
        </div>
      ) : null}
    </header>
  );
}

function ProfileGateEmployer({ locale }) {
  const t = text(locale);
  return (
    <LoginLink
      className="profile-board-gate-employer"
      intent="job_employer"
      returnTo={hrefFor(locale, { mode: "company" })}
    >
      {t.profileGateEmployer}
    </LoginLink>
  );
}

export function ProfileForm({ locale }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe;
    return undefined;
  });
  const [displayName, setDisplayName] = useState(() => initialMe?.candidate_profile?.display_name || "");
  const [phone, setPhone] = useState(() => initialMe?.candidate_profile?.phone || "");
  const [email, setEmail] = useState(() => initialMe?.candidate_profile?.email || "");
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
      applyMe(initialMe, { setDisplayName, setPhone, setEmail });
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        applyMe(data, { setDisplayName, setPhone, setEmail });
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

  const hasPrivacy = Boolean(showApplicant && consentPayload);
  const privacyRights =
    hasPrivacy && Array.isArray(consentPayload.privacy_rights) ? consentPayload.privacy_rights : [];
  const visibilityLevels = Array.isArray(consentPayload?.visibility_levels)
    ? consentPayload.visibility_levels
    : [];
  const visibilityLabel =
    visibilityLevels.find((level) => level.id === visibility)?.label || visibility;
  const layoutClass = [
    "profile-layout",
    showCompany && showApplicant ? "profile-layout-dual" : "",
    !showCompany && hasPrivacy ? "profile-layout-a" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <Shell locale={locale} mode="profile">
      <div className="home home-board profile-board">
        <div className="home-board-shell companies-board-shell profile-board-shell">
          <BoardSideNav locale={locale} active="profile" />
          <div className="home-board-main">
            {me === undefined ? null : showCompany || showApplicant ? (
              <>
                <ProfileHero locale={locale} showApplicant={showApplicant} />
                <div className={`profile-page ${layoutClass}`}>
                  {showCompany ? (
                    <div className="h2-panel profile-panel company-profile-card">
                      <h2 className="h2-panel-title">{t.companyTitle}</h2>
                      <p className="company-profile-card-copy">
                        {me?.company_profile?.company_name
                          ? `${me.company_profile.company_name}${me.company_profile.city ? ` · ${me.company_profile.city}` : ""}`
                          : t.companyLede}
                      </p>
                      <div className="company-profile-card-actions">
                        <a className="btn ink" href={hrefFor(locale, { mode: "company" })}>
                          {t.companyManage}
                        </a>
                      </div>
                    </div>
                  ) : null}
                  {showApplicant ? (
                    <form className="h2-panel h2-form profile-panel profile-applicant" onSubmit={saveApplicant}>
                      <h2 className="h2-panel-title">{t.profileApplicantTitle}</h2>
                      {applicantError ? <p className="note">{applicantError}</p> : null}
                      {applicantNote ? <p className="note">{applicantNote}</p> : null}
                      <div className="profile-grid">
                        <label className="profile-span">
                          <span className="profile-field-label">{t.profileName}</span>
                          <input
                            value={displayName}
                            maxLength={80}
                            required
                            onChange={(event) => setDisplayName(event.target.value)}
                          />
                        </label>
                        <label>
                          <span className="profile-field-label">
                            {t.applyPhone}
                            <span className="hint">{t.adOptional}</span>
                          </span>
                          <input
                            type="tel"
                            value={phone}
                            maxLength={40}
                            onChange={(event) => setPhone(event.target.value)}
                          />
                        </label>
                        <label>
                          <span className="profile-field-label">
                            {t.applyEmail}
                            <span className="hint">{t.adOptional}</span>
                          </span>
                          <input
                            type="email"
                            value={email}
                            maxLength={120}
                            onChange={(event) => setEmail(event.target.value)}
                          />
                        </label>
                      </div>
                      <div className="ad-actions profile-panel-actions">
                        <button type="submit" className="btn ink">
                          {t.companySave}
                        </button>
                      </div>
                    </form>
                  ) : null}
                  {hasPrivacy ? (
                    <form className="h2-panel h2-form profile-panel profile-privacy" onSubmit={savePrivacy}>
                      <div className="profile-privacy-head">
                        <h2 className="h2-panel-title">{t.privacyTitle}</h2>
                        <a className="profile-privacy-link" href={hrefFor(locale, { mode: "emailSettings" })}>
                          {t.emailSettingsOpen}
                        </a>
                      </div>
                      {privacyError ? <p className="note">{privacyError}</p> : null}
                      {privacyNote ? <p className="note">{privacyNote}</p> : null}
                      <ConsentFields
                        payload={consentPayload}
                        grants={grants}
                        visibility={visibility}
                        onGrantChange={(kind, value) => setGrants((current) => ({ ...current, [kind]: value }))}
                        onVisibilityChange={setVisibility}
                        showVisibility={false}
                        showMeta={false}
                        idPrefix="profile-consent"
                      />
                      <div className="ad-actions profile-panel-actions">
                        {visibilityLevels.length ? (
                          <div className="profile-visibility-pill">
                            <span className="profile-visibility-dot" aria-hidden="true" />
                            <span>
                              {t.privacyVisibilityLabel}: {visibilityLabel}
                            </span>
                            <select
                              aria-label={t.privacyVisibilityLabel}
                              value={visibility}
                              onChange={(event) => setVisibility(event.target.value)}
                            >
                              {visibilityLevels.map((level) => (
                                <option key={level.id} value={level.id}>
                                  {level.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        ) : (
                          <span className="profile-visibility-pill">
                            <span className="profile-visibility-dot" aria-hidden="true" />
                            <span>
                              {t.privacyVisibilityLabel}: {visibilityLabel}
                            </span>
                          </span>
                        )}
                        <button type="submit" className="btn ink">
                          {t.companySave}
                        </button>
                      </div>
                    </form>
                  ) : null}
                  {privacyRights.length ? (
                    <div className="profile-rights">
                      <div className="profile-rights-grid">
                        {privacyRights.map((right) => (
                          <div key={right.id} className="profile-right-card">
                            <strong>{right.label}</strong>
                            <div className="profile-right-actions">
                              {right.id === "export" ? (
                                <button
                                  type="button"
                                  className="btn"
                                  disabled={Boolean(privacyBusy)}
                                  onClick={downloadExport}
                                >
                                  {t.privacyExportAction}
                                </button>
                              ) : null}
                              {right.id === "delete" ? (
                                <button
                                  type="button"
                                  className="btn profile-right-danger"
                                  disabled={Boolean(privacyBusy)}
                                  onClick={deleteMyData}
                                >
                                  {t.privacyDeleteAction}
                                </button>
                              ) : null}
                              {right.id === "who_viewed" ? (
                                <span className="profile-right-soon">{t.privacyWhoViewedSoon}</span>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              </>
            ) : (
              <>
                <ProfileHero locale={locale} showApplicant={false} guest />
                <ProfileGateEmployer locale={locale} />
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
}
