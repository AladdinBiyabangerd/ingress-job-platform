"use client";

import { useEffect, useState } from "react";
import { text } from "../lib/copy";
import {
  NOTIF_LOG_DAYS,
  notifKindLabel,
  notifReasonLabel,
  notificationLogQuery,
  statusTone,
  weekdayLabel,
} from "../lib/admin-notification-log";
import styles from "./admin-notification-log.module.css";

function when(value) {
  const raw = String(value || "");
  return raw ? raw.replace("T", " ").slice(0, 16) : "";
}

function Pill({ status, label }) {
  const tone = statusTone(status);
  return <span className={`${styles.pill} ${styles[tone]}`}>{label || status}</span>;
}

function yesNo(t, value) {
  return value ? t.notifLogYes : t.notifLogNo;
}

export function AdminNotificationLog({ locale }) {
  const t = text(locale);
  const [user, setUser] = useState("");
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load(nextUser = user, nextDays = days) {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/auth/admin/notification-log?${notificationLogQuery({ user: nextUser, days: nextDays })}`, {
        cache: "no-store",
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load");
      setData(payload);
    } catch {
      setError(t.loadError);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load("", 30);
  }, []); // first load only; later loads come from the form

  function onSubmit(event) {
    event.preventDefault();
    load(user, days);
  }

  const profile = data?.user || null;
  const prefs = profile?.prefs || {};
  const totals = data?.totals || {};
  const emails = Array.isArray(data?.emails) ? data.emails : [];
  const engagement = Array.isArray(data?.engagement) ? data.engagement : [];
  const skips = Array.isArray(data?.skips) ? data.skips : [];
  const showUserCol = !profile;

  return (
    <section className="h2-panel">
      <h2 className="h2-panel-title">{t.notifLogTitle}</h2>
      <p className="hint">{t.notifLogLede}</p>
      <form className={styles.form} onSubmit={onSubmit}>
        <input
          type="search"
          value={user}
          onChange={(event) => setUser(event.target.value)}
          placeholder={t.notifLogUserPlaceholder}
          aria-label={t.notifLogUserPlaceholder}
        />
        <select value={days} onChange={(event) => setDays(Number(event.target.value))} aria-label={t.notifLogDays}>
          {NOTIF_LOG_DAYS.map((d) => (
            <option key={d} value={d}>
              {t.notifLogDaysOption(d)}
            </option>
          ))}
        </select>
        <button type="submit" className="btn ink" disabled={busy}>
          {t.notifLogSearch}
        </button>
      </form>
      {error ? <p className="note">{error}</p> : null}
      {data?.not_found ? <p className="note">{t.notifLogNotFound}</p> : null}

      {profile ? (
        <dl className={styles.summary}>
          <div>
            <dt>{t.notifLogUser}</dt>
            <dd>{profile.email || profile.user_id}</dd>
          </div>
          <div>
            <dt>{t.notifLogProfile}</dt>
            <dd>{profile.profile_status || "—"}</dd>
          </div>
          <div>
            <dt>{t.notifLogFrequency}</dt>
            <dd>
              {prefs.frequency} · {weekdayLabel(t, prefs.send_weekday)} · {String(prefs.language || "").toUpperCase()}
            </dd>
          </div>
          <div>
            <dt>{t.notifLogConsent}</dt>
            <dd>
              {yesNo(t, prefs.emails_consent)}
              {prefs.unsubscribed ? ` · ${t.notifLogUnsubscribed}` : ""}
            </dd>
          </div>
          <div>
            <dt>{t.notifLogPush}</dt>
            <dd>{profile.push_subscriptions || 0}</dd>
          </div>
        </dl>
      ) : null}

      {data ? (
        <div className={styles.totals}>
          <Pill status="sent" label={`${t.notifLogSent}: ${totals.sent || 0}`} />
          <Pill status="failed" label={`${t.notifLogFailed}: ${totals.failed || 0}`} />
          <Pill status="sending" label={`${t.notifLogSending}: ${totals.sending || 0}`} />
          <Pill status="skipped" label={`${t.notifLogSkipped}: ${totals.skipped || 0}`} />
        </div>
      ) : null}

      <h3 className={styles.sectionTitle}>{t.notifLogEmails}</h3>
      {emails.length ? (
        <div className={styles.wrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t.notifLogWhen}</th>
                {showUserCol ? <th scope="col">{t.notifLogUser}</th> : null}
                <th scope="col">{t.notifLogKind}</th>
                <th scope="col">{t.notifLogPeriod}</th>
                <th scope="col">{t.notifLogStatus}</th>
                <th scope="col">{t.notifLogAttempts}</th>
                <th scope="col">{t.notifLogReason}</th>
              </tr>
            </thead>
            <tbody>
              {emails.map((row) => (
                <tr key={`${row.user_id}-${row.kind}-${row.period_key}`}>
                  <td>{when(row.created_at)}</td>
                  {showUserCol ? <td>{row.to_email || row.user_id}</td> : null}
                  <td>{notifKindLabel(t, row.kind)}</td>
                  <td>{row.period_key}</td>
                  <td>
                    <Pill status={row.status} label={t.notifLogStatusLabels?.[row.status] || row.status} />
                  </td>
                  <td>{row.attempts}</td>
                  <td className={styles.wide}>{notifReasonLabel(t, row.reason)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-line">{t.notifLogEmpty}</p>
      )}

      <h3 className={styles.sectionTitle}>{t.notifLogEngagement}</h3>
      {engagement.length ? (
        <div className={styles.wrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t.notifLogWhen}</th>
                {showUserCol ? <th scope="col">{t.notifLogUser}</th> : null}
                <th scope="col">{t.notifLogKind}</th>
                <th scope="col">{t.notifLogPeriod}</th>
                <th scope="col">{t.notifLogJob}</th>
                <th scope="col">{t.notifLogChannels}</th>
              </tr>
            </thead>
            <tbody>
              {engagement.map((row) => (
                <tr key={`${row.user_id}-${row.kind}-${row.period_key}-${row.job_id}`}>
                  <td>{when(row.created_at)}</td>
                  {showUserCol ? <td>{row.user_id}</td> : null}
                  <td>{notifKindLabel(t, row.kind)}</td>
                  <td>{row.period_key}</td>
                  <td>{row.job_id ? `#${row.job_id}` : "—"}</td>
                  <td>{(row.channels || []).map((c) => t.notifLogChannelLabels?.[c] || c).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-line">{t.notifLogEmpty}</p>
      )}

      <h3 className={styles.sectionTitle}>{t.notifLogSkips}</h3>
      {skips.length ? (
        <div className={styles.wrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t.notifLogDay}</th>
                {showUserCol ? <th scope="col">{t.notifLogUser}</th> : null}
                <th scope="col">{t.notifLogKind}</th>
                <th scope="col">{t.notifLogReason}</th>
                <th scope="col">{t.notifLogHits}</th>
                <th scope="col">{t.notifLogLast}</th>
              </tr>
            </thead>
            <tbody>
              {skips.map((row) => (
                <tr key={`${row.user_id}-${row.kind}-${row.day}-${row.reason}`}>
                  <td>{row.day}</td>
                  {showUserCol ? <td>{row.user_id}</td> : null}
                  <td>{notifKindLabel(t, row.kind)}</td>
                  <td className={styles.wide}>{notifReasonLabel(t, row.reason)}</td>
                  <td>{row.hits}</td>
                  <td>{when(row.last_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-line">{t.notifLogEmpty}</p>
      )}
      <p className="hint">{t.notifLogUtcNote}</p>
    </section>
  );
}
