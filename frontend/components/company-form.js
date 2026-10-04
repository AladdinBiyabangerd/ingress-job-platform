"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { Shell } from "./shell";

export function CompanyForm({ locale }) {
  const t = text(locale);
  const [companyName, setCompanyName] = useState("");
  const [city, setCity] = useState("");
  const [about, setAbout] = useState("");
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/me", { cache: "no-store" })
      .then((res) => res.json())
      .then((me) => {
        if (cancelled) return;
        if (!me.authenticated) {
          window.location.href = `/api/auth/login?intent=job_employer&returnTo=${encodeURIComponent(hrefFor(locale, { mode: "company" }))}`;
          return;
        }
        const profile = me.company_profile || {};
        setCompanyName(profile.company_name || "");
        setCity(profile.city || "");
        setAbout(profile.about || "");
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) setError(t.ssoError);
      });
    return () => {
      cancelled = true;
    };
  }, [locale, t.ssoError]);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    const res = await fetch("/api/auth/company", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_name: companyName, city, about }),
    });
    if (!res.ok) {
      setError(t.companyRequired);
      return;
    }
    window.location.href = hrefFor(locale, { mode: "post" });
  }

  return (
    <Shell locale={locale} mode="company">
      <h1>{t.companyTitle}</h1>
      <p className="lede">{t.companyLede}</p>
      {error ? <p className="note">{error}</p> : null}
      {ready ? (
        <form className="form-card" onSubmit={onSubmit}>
          <label>
            {t.companyName}
            <input value={companyName} maxLength={120} required onChange={(event) => setCompanyName(event.target.value)} />
          </label>
          <label>
            {t.companyCity}
            <input value={city} maxLength={80} required onChange={(event) => setCity(event.target.value)} />
          </label>
          <label>
            {t.companyAbout}
            <textarea value={about} maxLength={400} required rows={5} onChange={(event) => setAbout(event.target.value)} />
          </label>
          <button type="submit" className="btn primary">{t.companySave}</button>
        </form>
      ) : null}
    </Shell>
  );
}
