"use client";

import { useEffect, useState } from "react";
import { text } from "../lib/copy";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

function fromJob(locale, job) {
  return {
    title: job.title || "",
    company: job.company || "",
    city: job.remote ? "" : job.city || "",
    remote: Boolean(job.remote),
    text: job.text || "",
    language: job.language || "",
    salary: job.salary || "",
    job_type: job.job_type || "",
  };
}

export function CollectedAdmin({ locale }) {
  const t = text(locale);
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(null);
  const [keepId, setKeepId] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  async function load() {
    const res = await fetch("/api/auth/admin/crawled", { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error("load");
    setItems(Array.isArray(data.items) ? data.items : []);
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

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function save(event) {
    event.preventDefault();
    if (!editing || !form || !form.title.trim()) {
      setError(t.adRequired);
      return;
    }
    setError("");
    setNote("");
    const res = await fetch(`/api/auth/admin/crawled/${editing}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        city: form.remote ? "" : form.city,
      }),
    });
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setEditing(null);
    setForm(null);
    setNote(t.adminSavedNote);
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function visibility(job, action) {
    setError("");
    setNote("");
    const res = await fetch(`/api/auth/admin/crawled/${job.id}/${action}`, { method: "POST" });
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(action === "hide" ? t.collectedHideNote : t.collectedShowNote);
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function merge(job) {
    if (!keepId || keepId === job.id) return;
    setError("");
    setNote("");
    const res = await fetch("/api/auth/admin/crawled/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keep_id: keepId, hide_id: job.id }),
    });
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(t.collectedMergeNote);
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  return (
    <section>
      <h2 className="section-label">{t.collectedTitle}</h2>
      <p className="lede">{t.collectedLede}</p>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}
      {editing && form ? (
        <form className="form-card" onSubmit={save}>
          <h2>{t.editAd}</h2>
          <label>
            {t.language}
            <select value={form.language} onChange={(event) => setField("language", event.target.value)}>
              <option value="">{t.languageAuto}</option>
              <option value="az">{t.langAz}</option>
              <option value="en">{t.langEn}</option>
              <option value="ru">{t.langRu}</option>
            </select>
          </label>
          <label>
            {t.adTitle}
            <input value={form.title} maxLength={140} required onChange={(event) => setField("title", event.target.value)} />
          </label>
          <label>
            {t.companyName}
            <input value={form.company} maxLength={120} onChange={(event) => setField("company", event.target.value)} />
          </label>
          <label>
            {t.adCityOrRemote}
            <input
              value={form.city}
              maxLength={80}
              disabled={form.remote}
              onChange={(event) => setField("city", event.target.value)}
            />
          </label>
          <label className="inline">
            <input type="checkbox" checked={form.remote} onChange={(event) => setField("remote", event.target.checked)} />
            <span>{t.placeRemote}</span>
          </label>
          <label>
            {t.adBody}
            <textarea value={form.text} maxLength={8000} rows={8} onChange={(event) => setField("text", event.target.value)} />
          </label>
          <div className="split">
            <label>
              {t.adSalary}
              <input value={form.salary} maxLength={120} onChange={(event) => setField("salary", event.target.value)} />
            </label>
            <label>
              {t.adJobType}
              <select value={form.job_type} onChange={(event) => setField("job_type", event.target.value)}>
                {TYPES.map((value) => (
                  <option key={value || "none"} value={value}>
                    {value ? typeLabel(t, value) : t.adJobTypeNone}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="ad-actions">
            <button type="submit" className="btn primary">{t.adSave}</button>
            <button type="button" className="btn red" onClick={() => { setEditing(null); setForm(null); }}>{t.adCancel}</button>
          </div>
        </form>
      ) : null}
      {items.length === 0 ? <p className="empty-line">{t.collectedEmpty}</p> : null}
      <div className="list">
        {items.map((job) => (
          <article key={job.id} className={job.hidden ? "card closed" : "card"}>
            <p className={job.hidden ? "source-pill closed" : "source-pill live"}>
              {job.hidden ? t.collectedHidden : t.statusPublished}
              {job.merged_into ? ` · ${t.collectedMerged}` : ""}
            </p>
            <h2>{job.title}</h2>
            <div className="meta">
              <span>{job.company || t.noCompany}</span>
              <span>{job.remote ? t.placeRemote : job.city || t.noCity}</span>
              {job.source_name ? <span>{job.source_name}</span> : null}
              {job.merged_into ? <span>#{job.merged_into}</span> : null}
            </div>
            {job.text ? <p className="admin-body">{job.text.length > 280 ? `${job.text.slice(0, 280)}…` : job.text}</p> : null}
            <div className="ad-actions">
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  setEditing(job.id);
                  setForm(fromJob(locale, job));
                  setError("");
                  setNote("");
                }}
              >
                {t.adEdit}
              </button>
              {job.hidden && !job.merged_into ? (
                <button type="button" className="btn primary" onClick={() => visibility(job, "show")}>{t.collectedShow}</button>
              ) : null}
              {!job.hidden ? (
                <button type="button" className="btn red" onClick={() => visibility(job, "hide")}>{t.collectedHide}</button>
              ) : null}
              {!job.hidden ? (
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => {
                    setKeepId(job.id);
                    setNote(t.collectedKept);
                  }}
                >
                  {t.collectedKeep}
                </button>
              ) : null}
              {keepId && keepId !== job.id && !job.merged_into ? (
                <button type="button" className="btn red" onClick={() => merge(job)}>{t.collectedMerge}</button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
