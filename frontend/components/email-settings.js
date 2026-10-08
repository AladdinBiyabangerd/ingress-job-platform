"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { fetchMe } from "../lib/me-client";
import { saveEmailPrefs } from "../lib/server/refresh";
import {
  disableBrowserPush,
  enableBrowserPush,
  pushSupported,
} from "../lib/web-push";
import { PageChrome } from "./page-chrome";
import { RegisterChoice } from "./register-choice";
import { Shell } from "./shell";
import { useInitialMe } from "./me-seed";

const FREQUENCIES = ["daily", "weekly", "biweekly", "important_only", "none"];
const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];
const CHANNEL_TOTAL = 6;

function frequencyLabel(t, value) {
  if (value === "daily") return t.emailFreqDaily;
  if (value === "weekly") return t.emailFreqWeekly;
  if (value === "biweekly") return t.emailFreqBiweekly;
  if (value === "important_only") return t.emailFreqImportant;
  return t.emailFreqNone;
}

function showsWeekday(frequency) {
  return frequency === "weekly" || frequency === "biweekly";
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
  setters.setMatchNear(data.match_near !== false);
  setters.setProfileNudge(data.profile_nudge !== false);
  setters.setCoachWeekly(data.coach_weekly !== false);
  setters.setPushEnabled(data.push_enabled !== false);
  setters.setLanguage(data.language || fallbackLang);
  setters.setSendWeekday(typeof data.send_weekday === "number" ? data.send_weekday : 0);
}

function PrefSwitch({ checked, onChange, label }) {
  return (
    <button
      type="button"
      className={`es-switch${checked ? " is-on" : ""}`}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
    />
  );
}

function ChannelCard({ title, hint, checked, onChange }) {
  return (
    <div className="es-channel">
      <div className="es-channel-text">
        <strong>{title}</strong>
        <span>{hint}</span>
      </div>
      <PrefSwitch checked={checked} onChange={onChange} label={title} />
    </div>
  );
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
  const [matchNear, setMatchNear] = useState(() => (seededPrefs ? initialPrefs.match_near !== false : true));
  const [profileNudge, setProfileNudge] = useState(() =>
    seededPrefs ? initialPrefs.profile_nudge !== false : true,
  );
  const [coachWeekly, setCoachWeekly] = useState(() =>
    seededPrefs ? initialPrefs.coach_weekly !== false : true,
  );
  const [pushEnabled, setPushEnabled] = useState(() =>
    seededPrefs ? initialPrefs.push_enabled !== false : true,
  );
  const [language, setLanguage] = useState(() => (seededPrefs ? initialPrefs.language || fallbackLang : fallbackLang));
  const [sendWeekday, setSendWeekday] = useState(() =>
    seededPrefs && typeof initialPrefs.send_weekday === "number" ? initialPrefs.send_weekday : 0,
  );
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushNote, setPushNote] = useState("");
  const [pushSubActive, setPushSubActive] = useState(false);

  const setters = {
    setPrefs,
    setFrequency,
    setDigest,
    setHighMatch,
    setMatchNear,
    setProfileNudge,
    setCoachWeekly,
    setPushEnabled,
    setLanguage,
    setSendWeekday,
  };

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

  useEffect(() => {
    if (!me || !(me.candidate || me.staff) || !pushSupported()) return undefined;
    let cancelled = false;
    navigator.serviceWorker.ready
      .then((reg) => reg.pushManager.getSubscription())
      .then((sub) => {
        if (!cancelled) setPushSubActive(Boolean(sub));
      })
      .catch(() => {
        if (!cancelled) setPushSubActive(false);
      });
    return () => {
      cancelled = true;
    };
  }, [me]);

  function pushReasonMessage(reason) {
    if (reason === "denied" || reason === "permission") return t.emailSettingsPushDenied;
    if (reason === "unsupported") return t.emailSettingsPushUnsupported;
    if (reason === "vapid") return t.emailSettingsPushVapid;
    if (reason === "auth") return t.emailSettingsPushAuth;
    if (reason === "upstream") return t.emailSettingsPushUpstream;
    return t.emailSettingsPushError;
  }

  async function onEnablePush() {
    setPushBusy(true);
    setPushNote("");
    setError("");
    try {
      const result = await enableBrowserPush();
      if (!result.ok) {
        setPushEnabled(false);
        setPushNote(pushReasonMessage(result.reason));
        return;
      }
      setPushSubActive(true);
      setPushEnabled(true);
      setPushNote(t.emailSettingsPushOn);
      const res = await saveEmailPrefs({
        frequency,
        digest,
        high_match: highMatch,
        match_near: matchNear,
        profile_nudge: profileNudge,
        coach_weekly: coachWeekly,
        push_enabled: true,
        language,
        send_weekday: sendWeekday,
      });
      if (res.ok) applyPrefs(res.data, setters, fallbackLang);
    } catch {
      setPushNote(t.emailSettingsPushError);
    } finally {
      setPushBusy(false);
    }
  }

  async function onDisablePush() {
    setPushBusy(true);
    setPushNote("");
    setError("");
    try {
      await disableBrowserPush();
      setPushSubActive(false);
      setPushEnabled(false);
      const res = await saveEmailPrefs({
        frequency,
        digest,
        high_match: highMatch,
        match_near: matchNear,
        profile_nudge: profileNudge,
        coach_weekly: coachWeekly,
        push_enabled: false,
        language,
        send_weekday: sendWeekday,
      });
      if (res.ok) applyPrefs(res.data, setters, fallbackLang);
    } catch {
      setPushNote(t.emailSettingsPushError);
    } finally {
      setPushBusy(false);
    }
  }

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
        match_near: matchNear,
        profile_nudge: profileNudge,
        coach_weekly: coachWeekly,
        push_enabled: pushEnabled,
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
  const activeCount = [digest, highMatch, matchNear, profileNudge, coachWeekly, pushEnabled].filter(
    Boolean,
  ).length;
  const consentOn = !prefs || prefs.emails_consent !== false;
  const langLabel = String(language || fallbackLang).toUpperCase();

  return (
    <Shell locale={locale} mode="emailSettings">
      {allowed ? (
        <div className="h2-candidate email-settings">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.emailSettingsTitle}
            actions={
              <a className="text-btn" href={hrefFor(locale, { mode: "profile" })}>
                {t.emailSettingsPrivacyLink}
              </a>
            }
          >
            <p className="es-lede">{t.emailSettingsLede}</p>
          </PageChrome>

          <form className="es-form" onSubmit={save}>
            {error ? <p className="note">{error}</p> : null}
            {note ? <p className="note">{note}</p> : null}
            {prefs && !prefs.emails_consent ? (
              <p className="hint es-consent-banner">
                {t.emailSettingsConsentOff}{" "}
                <a href={hrefFor(locale, { mode: "profile" })}>{t.emailSettingsPrivacyLink}</a>
              </p>
            ) : null}

            <div className="es-layout">
              <aside className="es-rail" aria-label={t.emailSettingsCurrentPlan}>
                <div className="es-stat">
                  <div className="es-stat-num">
                    {activeCount}/{CHANNEL_TOTAL}
                  </div>
                  <div className="es-stat-lbl">{t.emailSettingsActiveKinds}</div>
                  <span className={`es-pill${pushSubActive ? " is-on" : ""}`}>
                    <i aria-hidden="true" />
                    {pushSubActive ? t.emailSettingsPushSubOn : t.emailSettingsPushSubOff}
                  </span>
                </div>
                <div className="h2-panel es-plan">
                  <p className="h2-panel-title">{t.emailSettingsCurrentPlan}</p>
                  <dl className="es-plan-list">
                    <div>
                      <dt>{t.emailSettingsPlanFrequency}</dt>
                      <dd>{frequencyLabel(t, frequency)}</dd>
                    </div>
                    <div>
                      <dt>{t.emailSettingsPlanLanguage}</dt>
                      <dd>{langLabel}</dd>
                    </div>
                    {showsWeekday(frequency) ? (
                      <div>
                        <dt>{t.emailSettingsPlanWeekday}</dt>
                        <dd>{weekdayLabel(t, sendWeekday)}</dd>
                      </div>
                    ) : null}
                    <div>
                      <dt>{t.emailSettingsPlanConsent}</dt>
                      <dd>{consentOn ? t.emailSettingsConsentOn : t.emailSettingsConsentClosed}</dd>
                    </div>
                  </dl>
                </div>
              </aside>

              <div className="es-board">
                <div className="h2-panel es-panel">
                  <p className="h2-panel-title">{t.emailSettingsDelivery}</p>
                  <p className="es-sub">{t.emailSettingsDeliverySub}</p>
                  <div className="es-delivery">
                    <label className="es-field">
                      {t.emailSettingsFrequency}
                      <select value={frequency} onChange={(event) => setFrequency(event.target.value)}>
                        {FREQUENCIES.map((value) => (
                          <option key={value} value={value}>
                            {frequencyLabel(t, value)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="es-field">
                      {t.emailSettingsLanguage}
                      <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                        <option value="az">AZ</option>
                        <option value="en">EN</option>
                        <option value="ru">RU</option>
                      </select>
                    </label>
                    {showsWeekday(frequency) ? (
                      <label className="es-field">
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
                    ) : null}
                  </div>
                </div>

                <div className="h2-panel es-panel">
                  <p className="h2-panel-title">{t.emailSettingsChannels}</p>
                  <p className="es-sub">{t.emailSettingsChannelsSub}</p>
                  <div className="es-channels">
                    <ChannelCard
                      title={t.emailSettingsDigest}
                      hint={t.emailSettingsDigestHint}
                      checked={digest}
                      onChange={setDigest}
                    />
                    <ChannelCard
                      title={t.emailSettingsHighMatch}
                      hint={t.emailSettingsHighMatchHint}
                      checked={highMatch}
                      onChange={setHighMatch}
                    />
                    <ChannelCard
                      title={t.emailSettingsMatchNear}
                      hint={t.emailSettingsMatchNearHint}
                      checked={matchNear}
                      onChange={setMatchNear}
                    />
                    <ChannelCard
                      title={t.emailSettingsProfileNudge}
                      hint={t.emailSettingsProfileNudgeHint}
                      checked={profileNudge}
                      onChange={setProfileNudge}
                    />
                    <ChannelCard
                      title={t.emailSettingsCoachWeekly}
                      hint={t.emailSettingsCoachWeeklyHint}
                      checked={coachWeekly}
                      onChange={setCoachWeekly}
                    />
                    <ChannelCard
                      title={t.emailSettingsPush}
                      hint={t.emailSettingsPushHintShort}
                      checked={pushEnabled}
                      onChange={setPushEnabled}
                    />
                  </div>
                </div>

                <div className="es-push">
                  <div className="es-push-copy">
                    <strong>{t.emailSettingsPushSubTitle}</strong>
                    <p className="hint">{t.emailSettingsPushHint}</p>
                    {pushNote ? <p className="note">{pushNote}</p> : null}
                  </div>
                  <div className="es-push-actions">
                    <button
                      type="button"
                      className="btn"
                      disabled={pushBusy || !pushSupported()}
                      onClick={onEnablePush}
                    >
                      {t.emailSettingsPushEnable}
                    </button>
                    {pushSubActive || pushEnabled ? (
                      <button type="button" className="btn" disabled={pushBusy} onClick={onDisablePush}>
                        {t.emailSettingsPushDisable}
                      </button>
                    ) : null}
                  </div>
                </div>

                <div className="es-save">
                  <button type="submit" className="btn ink" disabled={busy}>
                    {t.companySave}
                  </button>
                </div>
              </div>
            </div>
          </form>
        </div>
      ) : me === undefined ? null : (
        <div className="h2-candidate">
          <PageChrome
            backHref={hrefFor(locale)}
            backLabel={t.breadcrumbHome}
            title={t.emailSettingsTitle}
          />
          <div className="h2-empty h2-gate">
            <p>{t.emailSettingsGate}</p>
            <RegisterChoice locale={locale} returnTo={hrefFor(locale, { mode: "emailSettings" })} />
          </div>
        </div>
      )}
    </Shell>
  );
}
