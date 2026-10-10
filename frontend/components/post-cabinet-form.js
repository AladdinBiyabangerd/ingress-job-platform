"use client";

import { useState } from "react";
import { applyFormReady } from "../lib/apply-form";
import { text } from "../lib/copy";
import { ApplyFormFields } from "./apply-form-fields";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

export function PostCabinetForm({
  locale,
  me,
  initialForm,
  editStatus = "",
  busy = false,
  editing = null,
  onSave,
  onCancel,
}) {
  const t = text(locale);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    if (!form.title.trim() || !form.text.trim() || !(form.remote || form.city.trim()) || (me.staff && !form.company.trim())) {
      setError(t.adRequired);
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
    const result = await onSave(form);
    if (result?.error) setError(result.error);
  }

  return (
    <form
      className="h2-panel h2-form cabinet-form post-cabinet-form"
      onSubmit={onSubmit}
      title={t.cabinetLede}
    >
      {error ? <p className="note post-cabinet-flash" role="alert">{error}</p> : null}
      {editStatus === "rejected" ? <p className="post-cabinet-banner">{t.resubmitHint}</p> : null}
      {editStatus === "published" && !me.staff ? <p className="post-cabinet-banner">{t.reviewHint}</p> : null}

      <div className="post-cabinet-layout">
        <div className="post-cabinet-main">
          <div className="cabinet-grid">
            <label className="cabinet-span">
              {t.adTitle}
              <input
                value={form.title}
                maxLength={140}
                required
                autoComplete="off"
                onChange={(event) => setField("title", event.target.value)}
              />
            </label>
            <label>
              {t.companyName}
              <input
                value={form.company}
                maxLength={120}
                required
                readOnly={!me.staff}
                title={!me.staff ? t.companyLocked : undefined}
                onChange={(event) => setField("company", event.target.value)}
              />
            </label>
            <label>
              {t.language}
              <select value={form.language} onChange={(event) => setField("language", event.target.value)}>
                <option value="az">{t.langAz}</option>
                <option value="en">{t.langEn}</option>
                <option value="ru">{t.langRu}</option>
              </select>
            </label>
            <div className="cabinet-span cabinet-place">
              <span className="cabinet-place-label">{t.adCityOrRemote}</span>
              <div className="cabinet-place-mode" role="group" aria-label={t.adCityOrRemote}>
                <button
                  type="button"
                  className={!form.remote ? "on" : ""}
                  aria-pressed={!form.remote}
                  onClick={() => setField("remote", false)}
                >
                  {t.companyCity}
                </button>
                <button
                  type="button"
                  className={form.remote ? "on" : ""}
                  aria-pressed={form.remote}
                  onClick={() => {
                    setForm((current) => ({ ...current, remote: true, city: "" }));
                  }}
                >
                  {t.placeRemote}
                </button>
              </div>
              {!form.remote ? (
                <input
                  value={form.city}
                  maxLength={80}
                  required
                  autoComplete="address-level2"
                  placeholder={t.companyCity}
                  onChange={(event) => setField("city", event.target.value)}
                />
              ) : null}
            </div>
            <label>
              <span className="cabinet-label-row">
                {t.adSalary}
                <span className="cabinet-optional">{t.adOptional}</span>
              </span>
              <input value={form.salary} maxLength={120} onChange={(event) => setField("salary", event.target.value)} />
            </label>
            <label>
              <span className="cabinet-label-row">
                {t.adJobType}
                <span className="cabinet-optional">{t.adOptional}</span>
              </span>
              <select value={form.job_type} onChange={(event) => setField("job_type", event.target.value)}>
                {TYPES.map((value) => (
                  <option key={value || "none"} value={value}>
                    {value ? typeLabel(t, value) : t.adJobTypeNone}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="post-cabinet-apply">
            <ApplyFormFields
              locale={locale}
              value={form.applicationForm}
              onChange={(applicationForm) => setField("applicationForm", applicationForm)}
            />
          </div>
        </div>

        <label className="cabinet-body post-cabinet-body">
          {t.adBody}
          <textarea
            value={form.text}
            maxLength={8000}
            required
            rows={16}
            onChange={(event) => setField("text", event.target.value)}
          />
        </label>
      </div>

      <div className="ad-actions post-cabinet-actions">
        {editing ? (
          <button type="button" className="btn" onClick={onCancel}>{t.adCancel}</button>
        ) : null}
        <button type="submit" className="btn ink" disabled={busy} aria-busy={busy}>
          {t.adSave}
        </button>
      </div>
    </form>
  );
}
