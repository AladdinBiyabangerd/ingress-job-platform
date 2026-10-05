"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { Shell } from "./shell";

export function UnsubscribePage({ locale, token }) {
  const t = text(locale);
  const [status, setStatus] = useState("loading");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus("invalid");
      return undefined;
    }
    let cancelled = false;
    fetch(`/api/unsubscribe/${encodeURIComponent(token)}`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        if (!data?.valid) {
          setStatus("invalid");
          return;
        }
        setStatus(data.unsubscribed ? "already" : "ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("invalid");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function confirm() {
    setBusy(true);
    try {
      const res = await fetch(`/api/unsubscribe/${encodeURIComponent(token)}`, { method: "POST" });
      if (!res.ok) {
        setStatus("invalid");
        return;
      }
      setDone(true);
      setStatus("already");
    } catch {
      setStatus("invalid");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell locale={locale} mode="browse">
      <section className="cabinet">
        <div className="cabinet-head">
          <div>
            <h1>{t.unsubscribeTitle}</h1>
            {status === "loading" ? <p className="lede">{t.unsubscribeLoading}</p> : null}
            {status === "invalid" ? <p className="lede">{t.unsubscribeInvalid}</p> : null}
            {status === "already" || done ? <p className="lede">{t.unsubscribeDone}</p> : null}
            {status === "ready" ? <p className="lede">{t.unsubscribeLede}</p> : null}
          </div>
        </div>
        {status === "ready" ? (
          <div className="form-card profile-card">
            <div className="ad-actions">
              <button type="button" className="btn primary" disabled={busy} onClick={confirm}>
                {t.unsubscribeConfirm}
              </button>
              <a className="btn" href={hrefFor(locale, { mode: "emailSettings" })}>
                {t.unsubscribeManage}
              </a>
            </div>
          </div>
        ) : null}
        {status === "already" || done ? (
          <p className="hint">
            <a href={hrefFor(locale, { mode: "emailSettings" })}>{t.unsubscribeManage}</a>
          </p>
        ) : null}
      </section>
    </Shell>
  );
}
