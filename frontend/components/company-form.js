"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { saveCompanyProfile } from "../lib/server/refresh";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";

const ABOUT_MAX = 400;
const SIZE_OPTIONS = ["1-10", "11-50", "51-200", "201-1000", "1000+"];

function fieldsFrom(me, profile) {
  const source = profile && typeof profile === "object" ? profile : me?.company_profile || {};
  return {
    companyName: source.company_name || "",
    city: source.city || "",
    about: source.about || "",
    address: source.address || "",
    website: source.website || "",
    industry: source.industry || "",
    size: source.size || "",
    complete: Boolean(source.complete),
  };
}

function loginHref(locale) {
  // Plain login — do not pass job_employer intent (staff revoke must stick).
  return `/api/auth/login?returnTo=${encodeURIComponent(hrefFor(locale, { mode: "company" }))}`;
}

function trimmed(value) {
  return String(value || "").trim();
}

function sizeLabel(t, value) {
  if (value === "1-10") return t.companySize1;
  if (value === "11-50") return t.companySize2;
  if (value === "51-200") return t.companySize3;
  if (value === "201-1000") return t.companySize4;
  if (value === "1000+") return t.companySize5;
  return t.companySizeNone;
}

export function CompanyForm({ locale, initialMe, initialProfile = null }) {
  const t = text(locale);
  const contextMe = useInitialMe();
  const meSeed = initialMe !== undefined ? initialMe : contextMe;
  const seededMe = meSeed && typeof meSeed === "object";
  const seed = fieldsFrom(meSeed, initialProfile);
  const nameRef = useRef(null);
  const focusedRef = useRef(false);
  const [companyName, setCompanyName] = useState(() => seed.companyName);
  const [city, setCity] = useState(() => seed.city);
  const [about, setAbout] = useState(() => seed.about);
  const [address, setAddress] = useState(() => seed.address);
  const [website, setWebsite] = useState(() => seed.website);
  const [industry, setIndustry] = useState(() => seed.industry);
  const [size, setSize] = useState(() => seed.size);
  const [complete, setComplete] = useState(() => Boolean(seededMe && seed.complete));
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [ready, setReady] = useState(() => Boolean(seededMe && meSeed.authenticated));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    function apply(me) {
      if (!me?.authenticated) {
        window.location.href = loginHref(locale);
        return;
      }
      const fields = fieldsFrom(me, initialProfile);
      setCompanyName(fields.companyName);
      setCity(fields.city);
      setAbout(fields.about);
      setAddress(fields.address);
      setWebsite(fields.website);
      setIndustry(fields.industry);
      setSize(fields.size);
      setComplete(fields.complete);
      setReady(true);
    }
    if (seededMe) {
      apply(meSeed);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((me) => {
        if (cancelled) return;
        apply(me);
      })
      .catch(() => {
        if (!cancelled) setError(t.ssoError);
      });
    return () => {
      cancelled = true;
    };
  }, [initialProfile, meSeed, seededMe, locale, t.ssoError]);

  useEffect(() => {
    if (!ready || saving || complete || focusedRef.current) return;
    focusedRef.current = true;
    nameRef.current?.focus();
  }, [ready, saving, complete]);

  const canSubmit = useMemo(() => {
    return Boolean(trimmed(companyName) && trimmed(city) && trimmed(about)) && !saving;
  }, [about, city, companyName, saving]);

  function clearNote() {
    setNote("");
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    const wasComplete = complete;
    setError("");
    setNote("");
    setSaving(true);
    const res = await saveCompanyProfile({
      company_name: trimmed(companyName),
      city: trimmed(city),
      about: trimmed(about),
      address: trimmed(address),
      website: trimmed(website),
      industry: trimmed(industry),
      size: trimmed(size),
    });
    if (!res.ok) {
      const detail = typeof res.data?.detail === "string" ? res.data.detail : "";
      setError(detail.includes("Vebsayt") || detail.toLowerCase().includes("website") || detail.includes("сайт")
        ? t.companyWebsiteInvalid
        : t.companyRequired);
      setSaving(false);
      return;
    }
    clearMeCache();
    if (!wasComplete) {
      window.location.href = hrefFor(locale, { mode: "post" });
      return;
    }
    setComplete(true);
    setNote(t.companySaved);
    setSaving(false);
  }

  return (
    <Shell locale={locale} mode="company">
      <div className="h2-employer company-profile">
        <PageChrome
          className="company-profile-chrome"
          backHref={hrefFor(locale, { mode: "post" })}
          backLabel={t.postTitle}
          title={t.companyTitle}
        />
        {error ? (
          <p className="note company-profile-banner" role="alert">
            {error}
          </p>
        ) : null}
        {note ? (
          <p className="note company-profile-banner" role="status">
            {note}
          </p>
        ) : null}
        {ready ? (
          <form className="h2-panel h2-form company-profile-form" onSubmit={onSubmit} noValidate>
            <section className="company-profile-section" aria-labelledby="company-basics-title">
              <h2 id="company-basics-title" className="company-profile-section-title">
                {t.companySectionBasics}
              </h2>
              <div className="company-profile-fields">
                <label className="company-profile-field company-profile-field-name">
                  <span className="company-profile-label">{t.companyName}</span>
                  <input
                    ref={nameRef}
                    name="company_name"
                    autoComplete="organization"
                    value={companyName}
                    maxLength={120}
                    required
                    disabled={saving}
                    onChange={(event) => {
                      setCompanyName(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
                <label className="company-profile-field">
                  <span className="company-profile-label-row">
                    <span className="company-profile-label">{t.companyIndustry}</span>
                    <span className="company-profile-optional">{t.companyOptional}</span>
                  </span>
                  <input
                    name="industry"
                    value={industry}
                    maxLength={80}
                    disabled={saving}
                    onChange={(event) => {
                      setIndustry(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
                <label className="company-profile-field company-profile-field-about">
                  <span className="company-profile-label-row">
                    <span className="company-profile-label">{t.companyAbout}</span>
                    <span className="company-profile-count" aria-live="polite">
                      {about.length}/{ABOUT_MAX}
                    </span>
                  </span>
                  <textarea
                    name="about"
                    value={about}
                    maxLength={ABOUT_MAX}
                    required
                    rows={3}
                    disabled={saving}
                    onChange={(event) => {
                      setAbout(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
              </div>
            </section>

            <section className="company-profile-section" aria-labelledby="company-location-title">
              <h2 id="company-location-title" className="company-profile-section-title">
                {t.companySectionLocation}
              </h2>
              <div className="company-profile-fields">
                <label className="company-profile-field">
                  <span className="company-profile-label">{t.companyCity}</span>
                  <input
                    name="city"
                    autoComplete="address-level2"
                    value={city}
                    maxLength={80}
                    required
                    disabled={saving}
                    onChange={(event) => {
                      setCity(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
                <label className="company-profile-field">
                  <span className="company-profile-label-row">
                    <span className="company-profile-label">{t.companyAddress}</span>
                    <span className="company-profile-optional">{t.companyOptional}</span>
                  </span>
                  <input
                    name="address"
                    autoComplete="street-address"
                    value={address}
                    maxLength={160}
                    disabled={saving}
                    onChange={(event) => {
                      setAddress(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
              </div>
            </section>

            <section className="company-profile-section" aria-labelledby="company-presence-title">
              <h2 id="company-presence-title" className="company-profile-section-title">
                {t.companySectionPresence}
              </h2>
              <div className="company-profile-fields">
                <label className="company-profile-field">
                  <span className="company-profile-label-row">
                    <span className="company-profile-label">{t.companyWebsite}</span>
                    <span className="company-profile-optional">{t.companyOptional}</span>
                  </span>
                  <input
                    name="website"
                    type="url"
                    inputMode="url"
                    autoComplete="url"
                    placeholder="https://"
                    value={website}
                    maxLength={200}
                    disabled={saving}
                    onChange={(event) => {
                      setWebsite(event.target.value);
                      clearNote();
                    }}
                  />
                </label>
                <label className="company-profile-field">
                  <span className="company-profile-label-row">
                    <span className="company-profile-label">{t.companySize}</span>
                    <span className="company-profile-optional">{t.companyOptional}</span>
                  </span>
                  <select
                    name="size"
                    value={size}
                    disabled={saving}
                    onChange={(event) => {
                      setSize(event.target.value);
                      clearNote();
                    }}
                  >
                    <option value="">{t.companySizeNone}</option>
                    {SIZE_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {sizeLabel(t, value)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <div className="company-profile-actions">
              <button type="submit" className="btn ink" disabled={!canSubmit} aria-busy={saving || undefined}>
                {saving ? t.companySaving : complete ? t.companySave : t.companyContinue}
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </Shell>
  );
}
