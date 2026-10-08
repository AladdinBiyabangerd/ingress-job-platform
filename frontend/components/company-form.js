"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { saveCompanyProfile } from "../lib/server/refresh";
import { useInitialMe } from "./me-seed";
import { PageChrome } from "./page-chrome";
import { Shell } from "./shell";

function fieldsFrom(me, profile) {
  const source = profile && typeof profile === "object" ? profile : me?.company_profile || {};
  return {
    companyName: source.company_name || "",
    city: source.city || "",
    about: source.about || "",
  };
}

function loginHref(locale) {
  // Plain login — do not pass job_employer intent (staff revoke must stick).
  return `/api/auth/login?returnTo=${encodeURIComponent(hrefFor(locale, { mode: "company" }))}`;
}

function profileComplete(me) {
  return Boolean(me?.authenticated && me.company_profile?.complete);
}

export function CompanyForm({ locale, initialMe, initialProfile = null }) {
  const t = text(locale);
  const contextMe = useInitialMe();
  const meSeed = initialMe !== undefined ? initialMe : contextMe;
  const seededMe = meSeed && typeof meSeed === "object";
  const seed = fieldsFrom(meSeed, initialProfile);
  const [companyName, setCompanyName] = useState(() => seed.companyName);
  const [city, setCity] = useState(() => seed.city);
  const [about, setAbout] = useState(() => seed.about);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(() => Boolean(seededMe && meSeed.authenticated && !profileComplete(meSeed)));
  const [done, setDone] = useState(() => Boolean(seededMe && profileComplete(meSeed)));

  useEffect(() => {
    function apply(me) {
      if (!me?.authenticated) {
        window.location.href = loginHref(locale);
        return;
      }
      if (profileComplete(me)) {
        setDone(true);
        setReady(false);
        return;
      }
      const fields = fieldsFrom(me, initialProfile);
      setCompanyName(fields.companyName);
      setCity(fields.city);
      setAbout(fields.about);
      setDone(false);
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

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    const res = await saveCompanyProfile({ company_name: companyName, city, about });
    if (!res.ok) {
      setError(t.companyRequired);
      return;
    }
    clearMeCache();
    window.location.href = hrefFor(locale, { mode: "post" });
  }

  return (
    <Shell locale={locale} mode="company">
      <div className="h2-employer">
        <PageChrome
          backHref={hrefFor(locale)}
          backLabel={t.breadcrumbHome}
          title={t.companyTitle}
        />
        {done ? (
          <div className="h2-panel h2-gate">
            <p>{t.companyEditOnProfile}</p>
            <a className="btn ink" href={hrefFor(locale, { mode: "profile" })}>
              {t.companyGoProfile}
            </a>
          </div>
        ) : (
          <>
            {error ? <p className="note">{error}</p> : null}
            {ready ? (
              <form className="h2-panel h2-form" onSubmit={onSubmit} title={t.companyLede}>
                <p className="hint">{t.companyLede}</p>
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
                  <button type="submit" className="btn ink">{t.companySave}</button>
                </div>
              </form>
            ) : null}
          </>
        )}
      </div>
    </Shell>
  );
}
