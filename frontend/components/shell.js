"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { ingressUrl } from "../lib/ingress";
import { clearMeCache } from "../lib/me-client";
import { navTabs } from "../lib/roles";
import { useMediaQuery } from "../lib/use-media-query";
import { lockBodyScroll, trapTab } from "../lib/focus-trap";
import { AccountBar } from "./account-bar";
import { CommandPalette, useCommandPaletteHotkey } from "./command-palette";
import { useInitialMe } from "./me-seed";

const LOCALES = ["az", "en", "ru"];

function LanguageSwitcher({ locale, mode, jobId, companySlug }) {
  const [open, setOpen] = useState(false);
  const switcherRef = useRef(null);

  useEffect(() => {
    function closeOnOutsideClick(event) {
      if (!switcherRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, []);

  return (
    <div className="language-switcher" ref={switcherRef}>
      <button
        type="button"
        className="language-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Language"
        onClick={() => setOpen((current) => !current)}
      >
        {locale.toUpperCase()}
        <span className="language-chevron" aria-hidden="true">⌄</span>
      </button>
      {open ? (
        <div className="language-menu" role="menu">
          {LOCALES.map((code) => (
            <a
              key={code}
              href={hrefFor(code, { mode, jobId, companySlug })}
              className={code === locale ? "on" : ""}
              hrefLang={code}
              aria-current={code === locale ? "true" : undefined}
              role="menuitem"
              onClick={() => setOpen(false)}
            >
              {code.toUpperCase()}
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function MenuIcon({ open }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
    </svg>
  );
}

function tabLabel(t, key) {
  if (key === "companies") return t.navCompanies;
  if (key === "trends") return t.navTrends;
  if (key === "post") return t.post;
  if (key === "admin") return t.admin;
  return t.browse;
}

/** Mobile drawer — account links match desktop AccountBar (incl. profileReview + admin). */
function MobileNav({ locale, mode, me, returnTo, onClose, toggleRef }) {
  const t = text(locale);
  const panelRef = useRef(null);

  useEffect(() => {
    panelRef.current?.querySelector("a, button")?.focus();
    const unlock = lockBodyScroll();
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        toggleRef.current?.focus();
        return;
      }
      trapTab(event, panelRef.current);
    }
    function onPointer(event) {
      if (panelRef.current?.contains(event.target) || toggleRef.current?.contains(event.target)) return;
      onClose();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
      unlock();
    };
  }, [onClose, toggleRef]);

  const back = returnTo || hrefFor(locale);
  const links = navTabs(me).map((key) => ({ key, label: tabLabel(t, key) }));

  return (
    <nav id="mobile-nav" className="mobile-nav" aria-label={t.menuLabel} ref={panelRef}>
      <ul className="mobile-nav-links">
        {links.map((link) => (
          <li key={link.key}>
            <a
              href={hrefFor(locale, { mode: link.key })}
              className={mode === link.key ? "on" : ""}
              aria-current={mode === link.key ? "page" : undefined}
            >
              {link.label}
            </a>
          </li>
        ))}
      </ul>
      {me?.authenticated ? (
        <ul className="mobile-nav-links mobile-nav-account">
          {me.employer || me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "profile" })} aria-current={mode === "profile" ? "page" : undefined}>
                {t.profileOpen}
              </a>
            </li>
          ) : null}
          {me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "profileReview" })} aria-current={mode === "profileReview" ? "page" : undefined}>
                {t.profileReviewOpen}
              </a>
            </li>
          ) : null}
          {me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "recommendations" })} aria-current={mode === "recommendations" ? "page" : undefined}>
                {t.recommendationsOpen}
              </a>
            </li>
          ) : null}
          {me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "insights" })} aria-current={mode === "insights" ? "page" : undefined}>
                {t.insightsOpen}
              </a>
            </li>
          ) : null}
          {me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "emailSettings" })} aria-current={mode === "emailSettings" ? "page" : undefined}>
                {t.emailSettingsOpen}
              </a>
            </li>
          ) : null}
          {me.candidate || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "applications" })} aria-current={mode === "applications" ? "page" : undefined}>
                {t.myApplications}
              </a>
            </li>
          ) : null}
          <li>
            <a href={hrefFor(locale, { mode: "saved" })} aria-current={mode === "saved" ? "page" : undefined}>
              {t.savedJobs}
            </a>
          </li>
          {me.employer || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "talent" })} aria-current={mode === "talent" ? "page" : undefined}>
                {t.talentTitle}
              </a>
            </li>
          ) : null}
          {me.employer || me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "company" })} aria-current={mode === "company" ? "page" : undefined}>
                {t.companyTitle}
              </a>
            </li>
          ) : null}
          <li>
            <a href={hrefFor(locale, { mode: "notifications" })} aria-current={mode === "notifications" ? "page" : undefined}>
              {t.notifications}
            </a>
          </li>
          {me.staff ? (
            <li>
              <a href={hrefFor(locale, { mode: "admin" })} aria-current={mode === "admin" ? "page" : undefined}>
                {t.admin}
              </a>
            </li>
          ) : null}
          <li>
            <form
              method="post"
              action={`/api/auth/logout?returnTo=${encodeURIComponent(back)}`}
              onSubmit={clearMeCache}
            >
              <button type="submit" className="mobile-nav-signout">{t.signOut}</button>
            </form>
          </li>
        </ul>
      ) : me ? (
        <div className="mobile-nav-account">
          <p className="mobile-nav-note">{t.register} · {t.registerAsk}</p>
          <ul className="mobile-nav-links">
            <li>
              <a href={loginHref({ intent: "job_candidate", returnTo: back })}>{t.registerCreator}</a>
            </li>
            <li>
              <a href={loginHref({ intent: "job_employer", returnTo: hrefFor(locale, { mode: "post" }) })}>{t.registerPoster}</a>
            </li>
          </ul>
        </div>
      ) : null}
    </nav>
  );
}

export function Shell({ locale, mode, jobId, companySlug, skillId, children }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const [me, setMe] = useState(initialMe ?? null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const toggleRef = useRef(null);
  const compact = useMediaQuery("(max-width: 767px)");
  const returnTo = hrefFor(locale, { mode, jobId, companySlug, skillId });
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const openCmd = useCallback(() => setCmdOpen(true), []);

  useCommandPaletteHotkey(openCmd);

  useEffect(() => {
    document.documentElement.lang = t.lang;
  }, [t.lang]);

  useEffect(() => {
    if (!compact) setMenuOpen(false);
  }, [compact]);

  const nav = navTabs(me);

  return (
    <>
      <a className="skip-link" href="#main">
        {locale === "ru" ? "К содержанию" : locale === "en" ? "Skip to content" : "Məzmuna keç"}
      </a>
      <header className="top">
        <div className="top-inner">
          <div className="top-left">
            <a className="brand" href={hrefFor(locale)}>
              <img className="mark" src="/ingress-mark.svg" alt="" aria-hidden="true" />
              <span className="brand-text">Ingress Job</span>
            </a>
            <nav className="primary-nav" aria-label={t.browse}>
              {nav.map((key) => (
                <a
                  key={key}
                  className={mode === key ? "on" : ""}
                  href={hrefFor(locale, { mode: key })}
                  aria-current={mode === key ? "page" : undefined}
                >
                  {tabLabel(t, key)}
                </a>
              ))}
            </nav>
          </div>
          <div className="top-right">
            <button type="button" className="cmdk-trigger" onClick={openCmd} aria-label={t.cmdKOpen}>
              <span className="cmdk-trigger-label">{t.cmdKOpen}</span>
              <kbd className="cmdk-trigger-kbd">{t.cmdKHint}</kbd>
            </button>
            <AccountBar locale={locale} returnTo={returnTo} onMe={setMe} />
            <LanguageSwitcher locale={locale} mode={mode} jobId={jobId} companySlug={companySlug} />
            <button
              ref={toggleRef}
              type="button"
              className="nav-toggle"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label={menuOpen ? t.menuClose : t.menuOpen}
              onClick={() => setMenuOpen((value) => !value)}
            >
              <MenuIcon open={menuOpen} />
            </button>
          </div>
        </div>
        {menuOpen && compact ? (
          <MobileNav locale={locale} mode={mode} me={me} returnTo={returnTo} onClose={closeMenu} toggleRef={toggleRef} />
        ) : null}
      </header>
      <CommandPalette locale={locale} me={me} open={cmdOpen} onOpenChange={setCmdOpen} />
      <main id="main" className="wrap">{children}</main>
      <footer className="site-footer">
        <div className="site-footer-inner">
          <p className="site-footer-eco">
            <span>{t.ecosystemLine}</span>
            <span aria-hidden="true"> · </span>
            <a href={ingressUrl(locale)} rel="noopener noreferrer" target="_blank">
              {t.ecosystemLinkLabel}
            </a>
          </p>
        </div>
      </footer>
    </>
  );
}
