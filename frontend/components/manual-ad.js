"use client";

import { useState } from "react";
import { applyFormPayload, applyFormReady, defaultApplyForm } from "../lib/apply-form";
import { text } from "../lib/copy";
import { createManualAd } from "../lib/server/refresh";
import { ApplyFormFields } from "./apply-form-fields";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

function blank(locale) {
  return {
    title: "",
    company: "",
    city: "",
    remote: false,
    text: "",
    language: locale,
    salary: "",
    job_type: "",
    source_url: "",
    applicationForm: defaultApplyForm(),
  };
}

export function ManualAd({ locale, onSaved }) {
  const t = text(locale);
  const [form, setForm] = useState(() => blank(locale));
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setNote("");
    if (!form.title.trim() || !form.company.trim() || !form.text.trim() || !(form.remote || form.city.trim())) {
      setError(t.adRequired);
      return;
    }
    if (!/^https?:\/\//i.test(form.source_url.trim())) {
      setError(t.manualUrlInvalid);
      return;
    }
    const ready = applyFormReady(form.applicationForm);
    if (!ready.any) {
      setError(t.formNeedField);
      return;
    }
    if (ready.blankQuestion) {
      setError(t.formQuestionNeeded);
      return;
    }
    setBusy(true);
    const res = await createManualAd({
      title: form.title,
      company: form.company,
      city: form.remote ? "" : form.city,
      remote: form.remote,
      text: form.text,
      language: form.language,
      salary: form.salary,
      job_type: form.job_type,
      source_url: form.source_url.trim(),
      form: applyFormPayload(form.applicationForm),
    });
    setBusy(false);
    if (!res.ok) {
      setError(res.status === 422 ? t.manualUrlInvalid : t.adminError);
      return;
    }
    setForm(blank(locale));
    setNote(t.manualSaved);
    if (onSaved) await onSaved();
  }

  return (
    <form className="h2-panel h2-form cabinet-form" onSubmit={onSubmit}>
      <h2 className="h2-panel-title">{t.manualTitle}</h2>
      <p className="hint">{t.manualLede}</p>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}
      <div className="cabinet-form-layout">
        <div className="cabinet-form-main">
          <div className="cabinet-grid">
            <label>
              {t.language}
              <select value={form.language} onChange={(event) => setField("language", event.target.value)}>
                <option value="az">{t.langAz}</option>
                <option value="en">{t.langEn}</option>
                <option value="ru">{t.langRu}</option>
              </select>
            </label>
            <label className="cabinet-span">
              {t.adTitle}
              <input value={form.title} maxLength={140} required onChange={(event) => setField("title", event.target.value)} />
            </label>
            <label>
              {t.companyName}
              <input value={form.company} maxLength={120} required onChange={(event) => setField("company", event.target.value)} />
            </label>
            <label>
              {t.adCityOrRemote}
              <input
                value={form.city}
                maxLength={80}
                required={!form.remote}
                disabled={form.remote}
                onChange={(event) => setField("city", event.target.value)}
              />
            </label>
            <label className="inline">
              <input type="checkbox" checked={form.remote} onChange={(event) => setField("remote", event.target.checked)} />
              <span>{t.placeRemote}</span>
            </label>
            <label className="cabinet-span">
              {t.adBody}
              <textarea value={form.text} maxLength={8000} required rows={6} onChange={(event) => setField("text", event.target.value)} />
            </label>
            <label className="cabinet-span">
              {t.manualUrl}
              <input
                value={form.source_url}
                maxLength={500}
                required
                inputMode="url"
                placeholder="https://"
                onChange={(event) => setField("source_url", event.target.value)}
              />
            </label>
            <label>
              {t.adSalary}
              <span className="hint">{t.adOptional}</span>
              <input value={form.salary} maxLength={120} onChange={(event) => setField("salary", event.target.value)} />
            </label>
            <label>
              {t.adJobType}
              <span className="hint">{t.adOptional}</span>
              <select value={form.job_type} onChange={(event) => setField("job_type", event.target.value)}>
                {TYPES.map((value) => (
                  <option key={value || "none"} value={value}>
                    {value ? typeLabel(t, value) : t.adJobTypeNone}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <aside className="cabinet-form-side">
          <ApplyFormFields locale={locale} value={form.applicationForm} onChange={(applicationForm) => setField("applicationForm", applicationForm)} />
        </aside>
      </div>
      <div className="ad-actions">
        <button type="submit" className="btn ink" disabled={busy}>{t.adSave}</button>
      </div>
    </form>
  );
}
