"use client";

import { useEffect, useRef, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { ingressUrl } from "../lib/ingress";
import { AccountBar } from "./account-bar";

const LOCALES = ["az", "en", "ru"];

function LanguageSwitcher({ locale, mode, jobId }) {
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
      {open && (
        <div className="language-menu" role="menu">
          {LOCALES.map((code) => (
            <a
              key={code}
              href={hrefFor(code, { mode, jobId })}
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
      )}
    </div>
  );
}

export function Shell({ locale, mode, jobId, children }) {
  const t = text(locale);

  useEffect(() => {
    document.documentElement.lang = t.lang;
  }, [t.lang]);

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
              Ingress Job
            </a>
          </div>
          <div className="mode" role="tablist" aria-label={t.browse}>
            <a
              role="tab"
              aria-selected={mode === "browse"}
              className={mode === "browse" ? "on" : ""}
              href={hrefFor(locale, { mode: "browse" })}
            >
              {t.browse}
            </a>
            <a
              role="tab"
              aria-selected={mode === "post"}
              className={mode === "post" ? "on" : ""}
              href={hrefFor(locale, { mode: "post" })}
            >
              {t.post}
            </a>
            <a
              role="tab"
              aria-selected={mode === "admin"}
              className={mode === "admin" ? "on" : ""}
              href={hrefFor(locale, { mode: "admin" })}
            >
              {t.admin}
            </a>
          </div>
          <div className="top-right">
            <AccountBar locale={locale} returnTo={hrefFor(locale, { mode, jobId })} />
            <LanguageSwitcher locale={locale} mode={mode} jobId={jobId} />
          </div>
        </div>
      </header>
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
          <p className="site-footer-note">{t.ecosystemFooter}</p>
        </div>
      </footer>
    </>
  );
}
