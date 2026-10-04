"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
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

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => res.json())
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

  return (
    <Shell locale={locale} mode="profile">
      {me === undefined ? null : showCompany || showApplicant ? (
        <div className="cabinet">
          <div className="cabinet-head">
            <div>
              <h1>{t.profileTitle}</h1>
              <p className="lede">{t.profileLede}</p>
            </div>
          </div>
          <div className={`profile-layout${showCompany && showApplicant ? " profile-layout-dual" : ""}`}>
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
                    <textarea value={about} maxLength={400} required rows={5} onChange={(event) => setAbout(event.target.value)} />
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
