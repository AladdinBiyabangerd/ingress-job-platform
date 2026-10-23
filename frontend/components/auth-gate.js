"use client";

import { text } from "../lib/copy";
import { LoginLink } from "./login-link";
import styles from "./auth-gate.module.css";

const ICONS = {
  applications: (
    <>
      <path d="M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1Z" />
      <path d="M8 6H6.5A1.5 1.5 0 0 0 5 7.5v11A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5v-11A1.5 1.5 0 0 0 17.5 6H16" />
      <path d="m9 13 2 2 4-4" />
    </>
  ),
  saved: <path d="M7 4h10a1 1 0 0 1 1 1v15l-6-4-6 4V5a1 1 0 0 1 1-1Z" />,
  notifications: (
    <>
      <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16Z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </>
  ),
};

/**
 * Signed-out empty state for candidate pages (applications, saved, settings…):
 * centred card with icon, title, helper text and Daxil ol / Hesab yarat.
 */
export function AuthGate({ locale, icon = "profile", title, message, returnTo, intent = "job_candidate" }) {
  const t = text(locale);
  return (
    <section className={styles.wrap} aria-labelledby="auth-gate-title">
      <div className={styles.card}>
        <span className={styles.icon} aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            width="28"
            height="28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {ICONS[icon] || ICONS.profile}
          </svg>
        </span>
        <h2 id="auth-gate-title" className={styles.title}>
          {title}
        </h2>
        {message ? <p className={styles.text}>{message}</p> : null}
        <div className={styles.actions}>
          <LoginLink className={styles.primary} intent={intent} returnTo={returnTo}>
            {t.signIn}
          </LoginLink>
          <LoginLink className={styles.secondary} intent={intent} returnTo={returnTo}>
            {t.createAccount}
          </LoginLink>
        </div>
      </div>
    </section>
  );
}
