"use client";

import { useEffect, useState } from "react";
import { text } from "../lib/copy";
import { saveAdminAiFlags } from "../lib/server/refresh";

const FLOWS = [
  ["gateway", "adminAiGateway"],
  ["cv_fallback", "adminAiCv"],
  ["job_tidy", "adminAiTidy"],
  ["embeddings", "adminAiEmbeddings"],
  ["rerank", "adminAiRerank"],
  ["llm_rerank", "adminAiLlmRerank"],
  ["match_why", "adminAiWhy"],
  ["role_coach", "adminAiRoleCoach"],
  ["digest_intro", "adminAiDigest"],
  ["engagement_copy", "adminAiEngagement"],
];

function flagsFromPayload(data) {
  const next = {};
  for (const [key] of FLOWS) {
    next[key] = Boolean(data?.flags && data.flags[key]);
  }
  return next;
}

export function AdminAiFlags({ locale, initial = null }) {
  const t = text(locale);
  const seeded = Boolean(initial && typeof initial === "object" && initial.flags && typeof initial.flags === "object");
  const [flags, setFlags] = useState(() => (seeded ? flagsFromPayload(initial) : null));
  const [keyConfigured, setKeyConfigured] = useState(() => (seeded ? Boolean(initial.key_configured) : true));
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await fetch("/api/auth/admin/ai-flags", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("load");
    setFlags(flagsFromPayload(data));
    setKeyConfigured(Boolean(data.key_configured));
  }

  useEffect(() => {
    if (seeded) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [seeded, t.loadError]);

  function setFlow(key, value) {
    setFlags((current) => (current ? { ...current, [key]: value } : current));
  }

  async function onSave(event) {
    event.preventDefault();
    if (!flags) return;
    setError("");
    setNote("");
    setBusy(true);
    try {
      const data = await saveAdminAiFlags(flags);
      if (!data.ok) {
        setError(t.adminError);
        return;
      }
      setFlags(flagsFromPayload(data));
      setKeyConfigured(Boolean(data.key_configured));
      setNote(t.adminAiSaved);
    } catch {
      setError(t.adminError);
    } finally {
      setBusy(false);
    }
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
