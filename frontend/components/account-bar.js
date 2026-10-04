"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { NotificationsBell } from "./notifications-bell";
import { RegisterChoice } from "./register-choice";

export function AccountBar({ locale, returnTo }) {
  const t = text(locale);
  const [me, setMe] = useState(null);
  const [ssoError, setSsoError] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSsoError(params.has("sso_error"));
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

  const role = me?.staff ? t.roleStaff : me?.employer ? t.roleEmployer : me?.candidate ? t.roleCandidate : "";
  const profileName = typeof me?.candidate_profile?.display_name === "string"
    ? me.candidate_profile.display_name.trim()
    : "";
  const academyName = typeof me?.name === "string" ? me.name.trim() : "";
  const accountLabel = [profileName || academyName, role || t.account].filter(Boolean).join(" · ");

  return (
    <div className="account-bar">
      {ssoError ? <span className="account-error">{t.ssoError}</span> : null}
      {me?.authenticated ? (
        <>
          <NotificationsBell locale={locale} />
          {me.employer || me.candidate || me.staff ? (
            <a className="profile-btn" href={hrefFor(locale, { mode: "profile" })} aria-label={t.profileOpen} title={t.profileOpen}>
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="12" cy="8" r="3.2" fill="currentColor" />
                <path d="M5.5 18.5c1.4-3 3.6-4.5 6.5-4.5s5.1 1.5 6.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </a>
          ) : null}
          <span className="who">{accountLabel}</span>
          {me.staff ? (
            <a className="text-btn" href={hrefFor(locale, { mode: "admin" })}>
              {t.admin}
            </a>
          ) : null}
          {me.candidate || me.staff ? (
            <a className="text-btn" href={hrefFor(locale, { mode: "applications" })}>
              {t.myApplications}
            </a>
          ) : null}
          {!me.employer && !me.staff ? <RegisterChoice locale={locale} returnTo={returnTo} /> : null}
          <form method="post" action={`/api/auth/logout?returnTo=${encodeURIComponent(returnTo || "/")}`}>
            <button type="submit" className="text-btn">{t.signOut}</button>
          </form>
        </>
      ) : (
        <RegisterChoice locale={locale} returnTo={returnTo} />
      )}
    </div>
  );
}
