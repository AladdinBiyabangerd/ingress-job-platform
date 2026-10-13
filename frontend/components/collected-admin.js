"use client";

import { Fragment, useEffect, useState } from "react";
import { text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  crawledMerge,
  crawledPatchJob,
  crawledVisibility,
  fetchCrawledJob,
  refreshCrawled,
} from "../lib/server/refresh";
import { Pager } from "./pager";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

function statusLabel(t, job) {
  if (job.hidden) return t.collectedHidden;
  if (job.status === "pending") return t.statusPending;
  if (job.status === "rejected") return t.statusRejected;
  return t.statusPublished;
}

function statusClass(job) {
  if (job.hidden) return "source-pill closed";
  if (job.status === "pending") return "source-pill";
  if (job.status === "rejected") return "source-pill rejected";
  return "source-pill live";
}

function sourceCell(t, job) {
  const url = String(job.source_url || "").trim();
  const name = String(job.source_name || "").trim();
  if (!url && !name) {
    return <span className="admin-mod-source-empty">{t.adminDateUnknown}</span>;
  }
  const label = name || t.adminColSource;
  if (!url) {
    return <span className="admin-mod-source-empty" title={label}>{label}</span>;
  }
  return (
    <a
      className="admin-mod-source-link"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title={url}
    >
      {label}
    </a>
  );
}

function dateCell(value, locale, fallback) {
  const label = calendarDate(value, locale);
  if (!label) return fallback;
  return <time dateTime={String(value).slice(0, 10)}>{label}</time>;
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

export function CollectedAdmin({ locale, initialItems = null }) {
  const t = text(locale);
  const seeded = Array.isArray(initialItems);
  const [items, setItems] = useState(() => (seeded ? initialItems : []));
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(null);
  const [keepId, setKeepId] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setItems(await refreshCrawled());
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

  const { pageItems, currentPage, totalPages, pageSize, total, goToPage: goToPaged } = usePagination(items, LIST_PAGE_SIZE);

  function cancelEdit() {
    setEditing(null);
    setForm(null);
  }

  function goToPage(page) {
    if (editing) cancelEdit();
    goToPaged(page);
  }

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
    setBusy(true);
    const res = await crawledPatchJob(editing, {
      ...form,
      city: form.remote ? "" : form.city,
    });
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    cancelEdit();
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
    const res = await crawledVisibility(job.id, action);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(action === "hide" ? t.collectedHideNote : t.collectedShowNote);
    if (editing === job.id) cancelEdit();
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
    const res = await crawledMerge(keepId, job.id);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(t.collectedMergeNote);
    setKeepId(null);
    if (editing === job.id) cancelEdit();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  return (
    <section className="h2-employer-queue">
      <p className="hint h2-employer-hint" title={t.collectedLede}>{t.collectedLede}</p>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}
      <div className="h2-panel h2-employer-list">
        {items.length === 0 ? <p className="empty-line">{t.collectedEmpty}</p> : null}
        {items.length ? (
          <div className="admin-mod-table-wrap">
            <table className="admin-mod-table">
              <thead>
                <tr>
                  <th className="admin-mod-check" scope="col">
                    <span className="visually-hidden">{t.collectedKeep}</span>
                  </th>
                  <th className="admin-mod-date" scope="col">{t.adminColIngested}</th>
                  <th scope="col">{t.adminColTitle}</th>
                  <th className="admin-mod-source" scope="col">{t.adminColSource}</th>
                  <th className="admin-mod-actions" scope="col">{t.adminColActions}</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((job) => {
                  const isOpen = editing === job.id;
                  const muted = Boolean(job.hidden);
                  return (
                    <Fragment key={job.id}>
                      <tr className={`${muted ? "is-muted" : ""}${isOpen ? " is-editing" : ""}`.trim() || undefined}>
                        <td className="admin-mod-check">
                          {!job.hidden ? (
                            <label className="inline admin-select">
                              <input
                                type="radio"
                                name="collected-keep"
                                checked={keepId === job.id}
                                onChange={() => setKeepId(job.id)}
                                aria-label={t.collectedKeep}
                              />
                            </label>
                          ) : null}
                        </td>
                        <td className="admin-mod-date">
                          {dateCell(job.created_at, locale, t.adminDateUnknown)}
                        </td>
                        <td className="admin-mod-title">
                          <div className="admin-mod-title-row">
                            <button
                              type="button"
                              className={`admin-mod-name linkish${isOpen ? " is-open" : ""}`}
                              aria-expanded={isOpen}
                              disabled={busy && !isOpen}
                              onClick={() => {
                                if (isOpen) {
                                  cancelEdit();
                                  return;
                                }
                                setError("");
                                setNote("");
                                setEditing(job.id);
                                setForm(null);
                                setBusy(true);
                                fetchCrawledJob(job.id)
                                  .then((full) => {
                                    setEditing(job.id);
                                    setForm(fromJob(locale, full));
                                  })
                                  .catch(() => {
                                    setError(t.loadError);
                                    cancelEdit();
                                  })
                                  .finally(() => setBusy(false));
                              }}
                            >
                              {job.title}
                            </button>
                            {job.hidden || job.status === "rejected" || job.status === "published" ? (
                              <span className={statusClass(job)}>{statusLabel(t, job)}</span>
                            ) : null}
                            {job.merged_into ? (
                              <span className="admin-mod-view">#{job.merged_into}</span>
                            ) : null}
                          </div>
                          {job.company ? <span className="admin-mod-sub">{job.company}</span> : null}
                        </td>
                        <td className="admin-mod-source">{sourceCell(t, job)}</td>
                        <td className="admin-mod-actions">
                          <div className="admin-mod-action-row">
                            {job.hidden && !job.merged_into ? (
                              <button type="button" className="btn small primary" disabled={busy} onClick={() => visibility(job, "show")}>
                                {t.collectedShow}
                              </button>
                            ) : null}
                            {!job.hidden ? (
                              <button type="button" className="btn small red" disabled={busy} onClick={() => visibility(job, "hide")}>
                                {t.collectedHide}
                              </button>
                            ) : null}
                            {keepId && keepId !== job.id && !job.merged_into ? (
                              <button type="button" className="btn small red" disabled={busy} onClick={() => merge(job)}>
                                {t.collectedMerge}
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                      {isOpen ? (
                        <tr className="admin-mod-edit-row">
                          <td colSpan={5}>
                            {form ? (
                              <form className="admin-mod-edit-form cabinet-form staff-compose-form" onSubmit={save}>
                                <div className="staff-compose-layout">
                                  <div className="staff-compose-main">
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
                                          onChange={(event) => setField("company", event.target.value)}
                                        />
                                      </label>
                                      <label>
                                        {t.language}
                                        <select value={form.language} onChange={(event) => setField("language", event.target.value)}>
                                          <option value="">{t.languageAuto}</option>
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
                                  </div>
                                  <label className="cabinet-body staff-compose-body">
                                    {t.adBody}
                                    <textarea
                                      value={form.text}
                                      maxLength={8000}
                                      rows={10}
                                      onChange={(event) => setField("text", event.target.value)}
                                    />
                                  </label>
                                </div>
                                <div className="ad-actions staff-compose-actions">
                                  <button type="button" className="btn" onClick={cancelEdit}>{t.adCancel}</button>
                                  <button type="submit" className="btn primary" disabled={busy} aria-busy={busy}>{t.adSave}</button>
                                </div>
                              </form>
                            ) : (
                              <p className="admin-mod-edit-loading hint" aria-busy="true">…</p>
                            )}
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
        <Pager
          locale={locale}
          currentPage={currentPage}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={goToPage}
        />
      </div>
    </section>
  );
}
