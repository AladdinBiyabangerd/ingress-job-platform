"use client";

import { useEffect, useRef, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { NotificationsBell } from "./notifications-bell";
import { RegisterChoice } from "./register-choice";
import { useInitialMe } from "./me-seed";

export function AccountBar({ locale, returnTo, onMe }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(initialMe ?? null);
  const [ssoError, setSsoError] = useState(false);
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);
  const onMeRef = useRef(onMe);
  onMeRef.current = onMe;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSsoError(params.has("sso_error"));
    if (initialMe != null) {
      onMeRef.current?.(initialMe);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (cancelled) return;
        setMe(data);
        onMeRef.current?.(data);
      })
      .catch(() => {
        if (cancelled) return;
        setMe({ authenticated: false });
        onMeRef.current?.({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [initialMe]);

  useEffect(() => {
    if (!open) return undefined;
    function closeOnOutsideClick(event) {
      if (!menuRef.current?.contains(event.target)) setOpen(false);
    }
    function closeOnEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const role = me?.staff ? t.roleStaff : me?.employer ? t.roleEmployer : me?.candidate ? t.roleCandidate : "";
  const profileName = typeof me?.candidate_profile?.display_name === "string"
    ? me.candidate_profile.display_name.trim()
    : "";
  const academyName = typeof me?.name === "string" ? me.name.trim() : "";
  const email = typeof me?.email === "string"
    ? me.email.trim()
    : typeof me?.candidate_profile?.email === "string"
      ? me.candidate_profile.email.trim()
      : "";
  // Never fall back to bare "Hesab" while signed in — that looks like a guest.
  const displayName = profileName || academyName || email || role || t.accountSignedIn;
  const identityHint = email && email !== displayName ? email : role && role !== displayName ? role : "";
  const canOpenProfile = Boolean(me?.employer || me?.candidate || me?.staff);
  // Already a candidate: only offer employer upgrade, not a second "login as applicant".
  const showEmployerUpgrade = Boolean(me?.authenticated && me.candidate && !me.employer && !me.staff);
  const showRegister = Boolean(me?.authenticated && !me.candidate && !me.employer && !me.staff);
  const back = returnTo || hrefFor(locale);

  return (
    <div className="account-bar">
      {ssoError ? <span className="account-error">{t.ssoError}</span> : null}
      {me?.authenticated ? (
        <>
          <NotificationsBell locale={locale} initialUnread={me?.unread_notifications} />
          <div className="account-menu" ref={menuRef}>
            <button
              type="button"
              className="account-trigger"
              aria-haspopup="menu"
              aria-expanded={open}
              aria-label={displayName}
              onClick={() => setOpen((value) => !value)}
            >
              <span className="account-avatar" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="12" cy="8" r="3.2" fill="currentColor" />
                  <path d="M5.5 18.5c1.4-3 3.6-4.5 6.5-4.5s5.1 1.5 6.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </span>
              <span className="account-trigger-text">
                <span className="account-trigger-name">{displayName}</span>
                {identityHint ? <span className="account-trigger-role">{identityHint}</span> : null}
              </span>
              <span className="account-chevron" aria-hidden="true">⌄</span>
            </button>
            {open ? (
              <div className="account-dropdown" role="menu">
                <div className="account-dropdown-head">
                  <strong>{displayName}</strong>
                  {identityHint ? <span>{identityHint}</span> : null}
                </div>
                {canOpenProfile ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "profile" })} onClick={() => setOpen(false)}>
                    {t.profileOpen}
                  </a>
                ) : null}
                {me.candidate || me.staff ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "profileReview" })} onClick={() => setOpen(false)}>
                    {t.profileReviewOpen}
                  </a>
                ) : null}
                {me.candidate || me.staff ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "recommendations" })} onClick={() => setOpen(false)}>
                    {t.recommendationsOpen}
                  </a>
                ) : null}
                {me.candidate || me.staff ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "emailSettings" })} onClick={() => setOpen(false)}>
                    {t.emailSettingsOpen}
                  </a>
                ) : null}
                {me.candidate || me.staff ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "applications" })} onClick={() => setOpen(false)}>
                    {t.myApplications}
                  </a>
                ) : null}
                {me.staff ? (
                  <a role="menuitem" href={hrefFor(locale, { mode: "admin" })} onClick={() => setOpen(false)}>
                    {t.admin}
                  </a>
                ) : null}
                {showEmployerUpgrade ? (
                  <div className="account-dropdown-group" role="group" aria-label={t.registerEmployerUpgrade}>
                    <p>{t.registerEmployerUpgrade}</p>
                    <a href={loginHref({ intent: "job_employer", returnTo: hrefFor(locale, { mode: "post" }) })}>
                      {t.registerPoster}
                    </a>
                  </div>
                ) : null}
                {showRegister ? (
                  <div className="account-dropdown-group" role="group" aria-label={t.registerAsk}>
                    <p>{t.registerAsk}</p>
                    <a href={loginHref({ intent: "job_employer", returnTo: hrefFor(locale, { mode: "post" }) })}>
                      {t.registerPoster}
                    </a>
                    <a href={loginHref({ intent: "job_candidate", returnTo: back })}>
                      {t.registerCreator}
                    </a>
                  </div>
                ) : null}
                <form
                  className="account-signout"
                  method="post"
                  action={`/api/auth/logout?returnTo=${encodeURIComponent(returnTo || "/")}`}
                  onSubmit={clearMeCache}
                >
                  <button type="submit" className="account-signout-btn" role="menuitem">
                    {t.signOut}
                  </button>
                </form>
              </div>
            ) : null}
          </div>
        </>
      ) : me ? (
        <RegisterChoice locale={locale} returnTo={returnTo} />
      ) : null}
    </div>
  );
}
