"use client";

import { useEffect, useState } from "react";
import { text } from "../lib/copy";

const FLOWS = [
  ["gateway", "adminAiGateway"],
  ["cv_fallback", "adminAiCv"],
  ["job_tidy", "adminAiTidy"],
  ["embeddings", "adminAiEmbeddings"],
  ["rerank", "adminAiRerank"],
  ["match_why", "adminAiWhy"],
  ["digest_intro", "adminAiDigest"],
];

export function AdminAiFlags({ locale }) {
  const t = text(locale);
  const [flags, setFlags] = useState(null);
  const [keyConfigured, setKeyConfigured] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await fetch("/api/auth/admin/ai-flags", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("load");
    const next = {};
    for (const [key] of FLOWS) {
      next[key] = Boolean(data.flags && data.flags[key]);
    }
    setFlags(next);
    setKeyConfigured(Boolean(data.key_configured));
  }

  useEffect(() => {
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [t.loadError]);

  function setFlow(key, value) {
    setFlags((current) => (current ? { ...current, [key]: value } : current));
  }

  async function onSave(event) {
    event.preventDefault();
    if (!flags) return;
    setError("");
    setNote("");
    setBusy(true);
    const res = await fetch("/api/auth/admin/ai-flags", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flags }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    const next = {};
    for (const [key] of FLOWS) {
      next[key] = Boolean(data.flags && data.flags[key]);
    }
    setFlags(next);
    setKeyConfigured(Boolean(data.key_configured));
    setNote(t.adminAiSaved);
  }

  return (
    <section className="cabinet-ads">
      <form className="form-card cabinet-form" onSubmit={onSave}>
        <div className="cabinet-form-head">
          <h2>{t.adminAiTitle}</h2>
          <p className="lede">{t.adminAiLede}</p>
        </div>
        {error ? <p className="note">{error}</p> : null}
        {note ? <p className="note">{note}</p> : null}
        {!keyConfigured ? <p className="note">{t.adminAiNoKey}</p> : null}
        {flags ? (
          <div className="cabinet-grid">
            {FLOWS.map(([key, copyKey]) => (
              <label key={key} className="profile-span consent-check">
                <input
                  type="checkbox"
                  checked={Boolean(flags[key])}
                  onChange={(event) => setFlow(key, event.target.checked)}
                />
                <span>{t[copyKey]}</span>
              </label>
            ))}
          </div>
        ) : null}
        <div className="ad-actions">
          <button type="submit" className="btn primary" disabled={busy || !flags}>
            {t.adSave}
          </button>
        </div>
      </form>
    </section>
  );
}
