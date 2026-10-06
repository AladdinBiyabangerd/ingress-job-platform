"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { saveEmailPrefs } from "../lib/server/refresh";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

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

function applyPrefs(data, setters, fallbackLang) {
  if (!data || typeof data !== "object") return;
  setters.setPrefs(data);
  setters.setFrequency(data.frequency || "none");
  setters.setDigest(data.digest !== false);
  setters.setHighMatch(data.high_match !== false);
  setters.setLanguage(data.language || fallbackLang);
  setters.setSendWeekday(typeof data.send_weekday === "number" ? data.send_weekday : 0);
}

export function EmailSettings({ locale, initialPrefs = null }) {
  const t = text(locale);
  const initialMe = useInitialMe();
  const fallbackLang = locale === "en" || locale === "ru" ? locale : "az";
  const seededPrefs = initialPrefs && typeof initialPrefs === "object";
  const [me, setMe] = useState(() => {
    if (initialMe && typeof initialMe === "object") return initialMe.authenticated ? initialMe : null;
    return undefined;
  });
  const [prefs, setPrefs] = useState(() => (seededPrefs ? initialPrefs : null));
  const [frequency, setFrequency] = useState(() => (seededPrefs ? initialPrefs.frequency || "none" : "none"));
  const [digest, setDigest] = useState(() => (seededPrefs ? initialPrefs.digest !== false : true));
  const [highMatch, setHighMatch] = useState(() => (seededPrefs ? initialPrefs.high_match !== false : true));
  const [language, setLanguage] = useState(() => (seededPrefs ? initialPrefs.language || fallbackLang : fallbackLang));
  const [sendWeekday, setSendWeekday] = useState(() =>
    seededPrefs && typeof initialPrefs.send_weekday === "number" ? initialPrefs.send_weekday : 0,
  );
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const setters = { setPrefs, setFrequency, setDigest, setHighMatch, setLanguage, setSendWeekday };

  useEffect(() => {
    if (initialMe && typeof initialMe === "object") {
      setMe(initialMe.authenticated ? initialMe : null);
      return undefined;
    }
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
  }, [initialMe]);

  useEffect(() => {
    if (!me || !(me.candidate || me.staff)) return undefined;
    if (seededPrefs) return undefined;
    let cancelled = false;
    fetch("/api/auth/email-prefs", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        applyPrefs(data, setters, fallbackLang);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [me, seededPrefs, fallbackLang]);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNote("");
    try {
      const res = await saveEmailPrefs({
        frequency,
        digest,
        high_match: highMatch,
        language,
        send_weekday: sendWeekday,
      });
      if (!res.ok) {
        setError(t.emailSettingsError);
        return;
      }
      applyPrefs(res.data, setters, fallbackLang);
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
