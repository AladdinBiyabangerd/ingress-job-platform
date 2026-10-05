"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";

const FREQUENCIES = ["weekly", "biweekly", "important_only", "none"];
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

function frequencyLabel(t, value) {
  if (value === "weekly") return t.emailFreqWeekly;
  if (value === "biweekly") return t.emailFreqBiweekly;
  if (value === "important_only") return t.emailFreqImportant;
  return t.emailFreqNone;
}

function weekdayLabel(t, value) {
  const labels = [
    t.emailWeekdayMon,
    t.emailWeekdayTue,
    t.emailWeekdayWed,
    t.emailWeekdayThu,
    t.emailWeekdayFri,
    t.emailWeekdaySat,
    t.emailWeekdaySun,
  ];
  return labels[value] || labels[0];
}

export function EmailSettings({ locale }) {
  const t = text(locale);
  const [me, setMe] = useState(undefined);
  const [prefs, setPrefs] = useState(null);
  const [frequency, setFrequency] = useState("none");
  const [digest, setDigest] = useState(true);
  const [highMatch, setHighMatch] = useState(true);
  const [language, setLanguage] = useState(locale === "en" || locale === "ru" ? locale : "az");
  const [sendWeekday, setSendWeekday] = useState(0);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setMe(data?.authenticated ? data : null);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff)) return undefined;
    let cancelled = false;
    fetch("/api/auth/email-prefs", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setPrefs(data);
        setFrequency(data.frequency || "none");
        setDigest(data.digest !== false);
        setHighMatch(data.high_match !== false);
        setLanguage(data.language || language);
        setSendWeekday(typeof data.send_weekday === "number" ? data.send_weekday : 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [me]);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNote("");
    try {
      const res = await fetch("/api/auth/email-prefs", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          frequency,
          digest,
          high_match: highMatch,
          language,
          send_weekday: sendWeekday,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(t.emailSettingsError);
        return;
      }
      setPrefs(data);
      setNote(t.emailSettingsSaved);
    } catch {
      setError(t.emailSettingsError);
    } finally {
      setBusy(false);
    }
  }

  const allowed = Boolean(me?.authenticated && (me.candidate || me.staff));

  return (
    <Shell locale={locale} mode="emailSettings">
      {allowed ? (
        <div className="cabinet">
          <div className="cabinet-head">
            <div>
              <h1>{t.emailSettingsTitle}</h1>
              <p className="lede">{t.emailSettingsLede}</p>
              <p className="hint">
                <a href={hrefFor(locale, { mode: "profile" })}>{t.emailSettingsPrivacyLink}</a>
              </p>
            </div>
          </div>
          <form className="form-card profile-card" onSubmit={save}>
            {error ? <p className="note">{error}</p> : null}
            {note ? <p className="note">{note}</p> : null}
            {prefs && !prefs.emails_consent ? (
              <p className="hint">
                {t.emailSettingsConsentOff}{" "}
                <a href={hrefFor(locale, { mode: "profile" })}>{t.emailSettingsPrivacyLink}</a>
              </p>
            ) : null}
            <div className="profile-grid">
              <label className="profile-span">
                {t.emailSettingsFrequency}
                <select value={frequency} onChange={(event) => setFrequency(event.target.value)}>
                  {FREQUENCIES.map((value) => (
                    <option key={value} value={value}>
                      {frequencyLabel(t, value)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.emailSettingsLanguage}
                <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                  <option value="az">AZ</option>
                  <option value="en">EN</option>
                  <option value="ru">RU</option>
                </select>
              </label>
              <label>
                {t.emailSettingsWeekday}
                <select
                  value={sendWeekday}
                  onChange={(event) => setSendWeekday(Number(event.target.value))}
                >
                  {WEEKDAYS.map((day) => (
                    <option key={day} value={day}>
                      {weekdayLabel(t, day)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="profile-span consent-check">
                <input
                  type="checkbox"
                  checked={digest}
                  onChange={(event) => setDigest(event.target.checked)}
                />
                <span>{t.emailSettingsDigest}</span>
              </label>
              <label className="profile-span consent-check">
                <input
                  type="checkbox"
                  checked={highMatch}
                  onChange={(event) => setHighMatch(event.target.checked)}
                />
                <span>{t.emailSettingsHighMatch}</span>
              </label>
            </div>
            <div className="ad-actions">
              <button type="submit" className="btn primary" disabled={busy}>
                {t.companySave}
              </button>
            </div>
          </form>
        </div>
      ) : me === undefined ? null : (
        <section className="empty profile-gate">
          <h1>{t.emailSettingsTitle}</h1>
          <p className="lede">{t.emailSettingsGate}</p>
          <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "emailSettings" })} />
        </section>
      )}
    </Shell>
  );
}
