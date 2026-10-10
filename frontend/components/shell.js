"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { loginHref } from "../lib/auth-link";
import { hrefFor, text } from "../lib/copy";
import { ingressUrl } from "../lib/ingress";
import { clearMeCache, fetchMe } from "../lib/me-client";
import { recommendationsEnabled, roadmapEnabled } from "../lib/product-features";
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
          {(me.candidate || me.staff) && recommendationsEnabled() ? (
            <li>
              <a href={hrefFor(locale, { mode: "recommendations" })} aria-current={mode === "recommendations" ? "page" : undefined}>
                {t.recommendationsOpen}
              </a>
            </li>
          ) : null}
          {(me.candidate || me.staff) && roadmapEnabled() ? (
            <li>
              <a href={hrefFor(locale, { mode: "insightsRoadmap" })} aria-current={mode === "insights" ? "page" : undefined}>
                {t.roadmapTitle}
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

function BoardAuthActions({ locale, returnTo, me, onMe }) {
  const t = text(locale);
  const back = returnTo || hrefFor(locale);
  // Signed-in: full account menu. Guest: mockup Sign in / Create account (no RegisterChoice chrome).
  if (me?.authenticated) {
    return <AccountBar locale={locale} returnTo={returnTo} onMe={onMe} />;
  }
  return (
    <div className="board-auth">
      <a className="btn board-auth-signin" href={loginHref({ intent: "job_candidate", returnTo: back })}>
        {t.signIn}
      </a>
      <a className="btn primary board-auth-create" href={loginHref({ intent: "job_candidate", returnTo: back })}>
        {t.createAccount}
      </a>
    </div>
  );
}

const BOARD_SHELL_MODES = new Set(["browse", "saved", "applications", "profile"]);

function BoardBottomNav({ locale, mode }) {
  const t = text(locale);
  return (
    <nav className="board-bottom-nav" aria-label={t.menuLabel}>
      <a
        href={hrefFor(locale)}
        className={mode === "browse" ? "on" : ""}
        aria-current={mode === "browse" ? "page" : undefined}
      >
        <BoardNavIconJobs />
        <span>{t.navJobs}</span>
      </a>
      <a
        href={hrefFor(locale, { mode: "saved" })}
        className={mode === "saved" ? "on" : ""}
        aria-current={mode === "saved" ? "page" : undefined}
      >
        <BoardNavIconSaved />
        <span>{t.navSavedShort}</span>
      </a>
      <a
        href={hrefFor(locale, { mode: "applications" })}
        className={mode === "applications" ? "on" : ""}
        aria-current={mode === "applications" ? "page" : undefined}
      >
        <BoardNavIconApplied />
        <span>{t.navAppliedShort}</span>
      </a>
      <a href={ingressUrl(locale)} rel="noopener noreferrer" target="_blank">
        <BoardNavIconAcademy />
        <span>{t.navAcademy}</span>
      </a>
      <a
        href={hrefFor(locale, { mode: "profile" })}
        className={mode === "profile" ? "on" : ""}
        aria-current={mode === "profile" ? "page" : undefined}
      >
        <BoardNavIconMe />
        <span>{t.navMe}</span>
      </a>
    </nav>
  );
}

function BoardNavIconJobs() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <rect x="3" y="7" width="18" height="13" rx="2" />
      <path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2" />
    </svg>
  );
}

function BoardNavIconSaved() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M7 3.5h10a1 1 0 011 1V21l-6-3.5L6 21V4.5a1 1 0 011-1z" />
    </svg>
  );
}

function BoardNavIconApplied() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M8 4h8a2 2 0 012 2v14l-6-3-6 3V6a2 2 0 012-2z" />
      <path d="M9 10h6M9 14h4" />
    </svg>
  );
}

function BoardNavIconAcademy() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M5 10v5c0 1.5 3 3 7 3s7-1.5 7-3v-5" />
    </svg>
  );
}

function BoardNavIconMe() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 19.5c1.5-3 4-4.5 7-4.5s5.5 1.5 7 4.5" />
    </svg>
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
  const isBoard = BOARD_SHELL_MODES.has(mode);

  useCommandPaletteHotkey(openCmd);

  useEffect(() => {
    document.documentElement.lang = t.lang;
  }, [t.lang]);

  useEffect(() => {
    if (!compact) setMenuOpen(false);
  }, [compact]);

  useEffect(() => {
    if (!isBoard) return undefined;
    if (initialMe != null) {
      setMe(initialMe);
      return undefined;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe({ authenticated: false });
      });
    return () => {
      cancelled = true;
    };
  }, [isBoard, initialMe]);

  const nav = navTabs(me);

  return (
    <>
      <a className="skip-link" href="#main">
        {locale === "ru" ? "К содержанию" : locale === "en" ? "Skip to content" : "Məzmuna keç"}
      </a>
      <header className={`top${isBoard ? " top-board" : ""}`}>
        <div className="top-inner">
          <div className="top-left">
            <a className="brand" href={hrefFor(locale)}>
              <img className="mark" src="/ingress-mark.svg" alt="" aria-hidden="true" />
              <span className="brand-text">Ingress Job</span>
            </a>
            {isBoard ? (
              <nav className="primary-nav board-primary-nav" aria-label={t.navJobs}>
                <a
                  href={hrefFor(locale)}
                  className={mode === "browse" ? "on" : ""}
                  aria-current={mode === "browse" ? "page" : undefined}
                >
                  {t.navJobs}
                </a>
                <a
                  href={hrefFor(locale, { mode: "post" })}
                  className={mode === "post" ? "on" : ""}
                  aria-current={mode === "post" ? "page" : undefined}
                >
                  {t.navForEmployers}
                </a>
                <a href={ingressUrl(locale)} rel="noopener noreferrer" target="_blank">
                  {t.navAcademy}
                </a>
              </nav>
            ) : (
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
            )}
          </div>
          <div className="top-right">
            {!isBoard ? (
              <button type="button" className="cmdk-trigger" onClick={openCmd} aria-label={t.cmdKOpen}>
                <span className="cmdk-trigger-label">{t.cmdKOpen}</span>
                <kbd className="cmdk-trigger-kbd">{t.cmdKHint}</kbd>
              </button>
            ) : null}
            {isBoard ? (
              <BoardAuthActions locale={locale} returnTo={returnTo} me={me} onMe={setMe} />
            ) : (
              <AccountBar locale={locale} returnTo={returnTo} onMe={setMe} />
            )}
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
      <main id="main" className={`wrap${isBoard ? " wrap-board" : ""}`}>
        {children}
      </main>
      {isBoard && compact && !jobId ? <BoardBottomNav locale={locale} mode={mode} /> : null}
      <footer className={`site-footer${isBoard ? " site-footer-board" : ""}`}>
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
