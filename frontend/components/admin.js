"use client";

import { useEffect, useState } from "react";
import { applyFormFromJob, applyFormPayload, applyFormReady } from "../lib/apply-form";
import { hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  adminActJob,
  adminApproveBulk,
  adminPatchJob,
  adminRejectJob,
  crawledPatchJob,
  fetchAdminJob,
  refreshAdminApplications,
  refreshAdminQueue,
} from "../lib/server/refresh";
import { AdminAiFlags } from "./admin-ai-flags";
import { ApplicationList } from "./application-list";
import { ApplyFormFields } from "./apply-form-fields";
import { CollectedAdmin } from "./collected-admin";
import { ManualAd } from "./manual-ad";
import { PageChrome } from "./page-chrome";
import { Pager } from "./pager";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

function statusLabel(t, status) {
  if (status === "pending") return t.statusPending;
  if (status === "rejected") return t.statusRejected;
  if (status === "closed") return t.statusClosed;
  return t.statusPublished;
}

function statusClass(status) {
  if (status === "published") return "source-pill live";
  if (status === "closed") return "source-pill closed";
  if (status === "rejected") return "source-pill rejected";
  return "source-pill";
}

function sourceLabel(t, job) {
  const name = String(job.source_name || "").trim();
  if (name) return name;
  if (job.owner_subject) return t.adminCompanySource;
  return t.adminCollectedBadge;
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
    language: job.language || locale,
    salary: job.salary || "",
    job_type: job.job_type || "",
    applicationForm: applyFormFromJob(job),
  };
}

export function Admin({
  locale,
  initialJobs = null,
  initialApplications = null,
  initialCrawled = null,
  initialAiFlags = null,
}) {
  const t = text(locale);
  const seededJobs = Array.isArray(initialJobs);
  const seededApps = Array.isArray(initialApplications);
  const seededList = seededJobs && seededApps;
  const [tab, setTab] = useState("queue");
  const [seenCollected, setSeenCollected] = useState(false);
  const [seenAi, setSeenAi] = useState(false);
  const [items, setItems] = useState(() => (seededJobs ? initialJobs : []));
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [applications, setApplications] = useState(() => (seededApps ? initialApplications : []));

  async function load() {
    const data = await refreshAdminQueue();
    setItems(data.jobs);
    setApplications(data.applications);
    setSelected(new Set());
  }

  useEffect(() => {
    if (seededList) return undefined;
    let cancelled = false;
    const boot = seededJobs
      ? refreshAdminApplications().then((apps) => {
          if (!cancelled) setApplications(apps);
        })
      : load();
    boot.catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [seededList, seededJobs, t.loadError]);

  const { pageItems, currentPage, totalPages, pageSize, total, goToPage } = usePagination(items, LIST_PAGE_SIZE);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function cancelEdit() {
    setEditing(null);
    setForm(null);
    setError("");
  }

  function isCollected(jobId) {
    const row = items.find((job) => job.id === jobId);
    return Boolean(row && !row.owner_subject);
  }

  async function onSave(event) {
    event.preventDefault();
    if (!editing || !form) return;
    setError("");
    setNote("");
    const scraped = isCollected(editing);
    if (!form.title.trim() || !form.text.trim() || !(form.remote || form.city.trim())) {
      setError(t.adRequired);
      return;
    }
    if (!scraped && !form.company.trim()) {
      setError(t.adRequired);
      return;
    }
    if (!scraped) {
      const ready = applyFormReady(form.applicationForm);
      if (!ready.any) {
        setError(t.formNeedField);
        return;
      }
      if (ready.blankQuestion) {
        setError(t.formQuestionNeeded);
        return;
      }
    }
    setBusy(true);
    const payload = {
      title: form.title,
      company: form.company,
      city: form.remote ? "" : form.city,
      remote: form.remote,
      text: form.text,
      language: form.language,
      salary: form.salary,
      job_type: form.job_type,
    };
    const res = scraped
      ? await crawledPatchJob(editing, payload)
      : await adminPatchJob(editing, {
          ...payload,
          form: applyFormPayload(form.applicationForm),
        });
    setBusy(false);
    if (!res.ok) {
      setError(res.status === 422 ? t.adRequired : t.adminError);
      return;
    }
    setNote(t.adminSavedNote);
    cancelEdit();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function rejectJob(job) {
    const reason = window.prompt(t.adminRejectAsk);
    if (reason == null) return;
    if (!reason.trim()) {
      setError(t.rejectReasonRequired);
      return;
    }
    setError("");
    setNote("");
    const res = await adminRejectJob(job.id, reason);
    if (!res.ok) {
      setError(res.status === 422 ? t.rejectReasonRequired : t.adminError);
      return;
    }
    setNote(t.adminRejectedNote);
    if (editing === job.id) cancelEdit();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function act(job, action, ask, okNote) {
    if (ask && !window.confirm(ask)) return;
    setError("");
    setNote("");
    const res = await adminActJob(job.id, action);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(okNote);
    if (editing === job.id) cancelEdit();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  function toggleSelected(jobId) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }

  function selectAllPending() {
    setSelected(new Set(items.filter((job) => job.status === "pending").map((job) => job.id)));
  }

  function clearSelection() {
    setSelected(new Set());
  }

  async function approveSelected() {
    const ids = [...selected];
    if (!ids.length) return;
    setError("");
    setNote("");
    setBusy(true);
    const res = await adminApproveBulk(ids);
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    const count = Number(res.data?.approved) || ids.length;
    setNote(t.adminBulkApprovedNote(count));
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  const pendingCount = items.filter((job) => job.status === "pending").length;
  const selectedCount = selected.size;

  return (
    <div className="h2-employer">
      <PageChrome
        backHref={hrefFor(locale)}
        backLabel={t.breadcrumbHome}
      />
      <div className="h2-tabs" role="tablist" aria-label={t.admin}>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "queue"}
          className={tab === "queue" ? "on" : ""}
          onClick={() => setTab("queue")}
        >
          {t.adminQueue}
          {pendingCount ? <span className="h2-tab-count">{pendingCount}</span> : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "collected"}
          className={tab === "collected" ? "on" : ""}
          onClick={() => {
            setTab("collected");
            setSeenCollected(true);
          }}
        >
          {t.collectedTitle}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "manual"}
          className={tab === "manual" ? "on" : ""}
          onClick={() => setTab("manual")}
        >
          {t.manualTitle}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "applications"}
          className={tab === "applications" ? "on" : ""}
          onClick={() => setTab("applications")}
        >
          {t.applicationsTitle}
          {applications.length ? <span className="h2-tab-count">{applications.length}</span> : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ai"}
          className={tab === "ai" ? "on" : ""}
          onClick={() => {
            setTab("ai");
            setSeenAi(true);
          }}
        >
          {t.adminAiTitle}
        </button>
      </div>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}

      {tab === "queue" ? (
        <section className="h2-employer-queue">
          {editing && form ? (
            <form className="h2-panel h2-form cabinet-form" onSubmit={onSave}>
              <h2 className="h2-panel-title">{t.editAd}</h2>
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
                    <label>
                      {t.adTitle}
                      <input value={form.title} maxLength={140} required onChange={(event) => setField("title", event.target.value)} />
                    </label>
                    <label>
                      {t.companyName}
                      <input
                        value={form.company}
                        maxLength={120}
                        required={!(editing && isCollected(editing))}
                        onChange={(event) => setField("company", event.target.value)}
                      />
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
                    <label className="inline cabinet-remote">
                      <input
                        type="checkbox"
                        checked={form.remote}
                        onChange={(event) => setField("remote", event.target.checked)}
                      />
                      <span>{t.placeRemote}</span>
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
                  <label className="cabinet-body">
                    {t.adBody}
                    <textarea value={form.text} maxLength={8000} required rows={8} onChange={(event) => setField("text", event.target.value)} />
                  </label>
                </div>
                {editing && !isCollected(editing) ? (
                  <aside className="cabinet-form-side">
                    <ApplyFormFields locale={locale} value={form.applicationForm} onChange={(applicationForm) => setField("applicationForm", applicationForm)} />
                  </aside>
                ) : null}
              </div>
              <div className="ad-actions">
                <button type="submit" className="btn ink" disabled={busy}>{t.adSave}</button>
                <button type="button" className="btn red" onClick={cancelEdit}>{t.adCancel}</button>
              </div>
            </form>
          ) : null}
          <div className="h2-panel h2-employer-list">
            {items.length === 0 ? <p className="empty-line">{t.adminEmpty}</p> : null}
            {pendingCount ? (
              <div className="ad-actions admin-bulk-bar">
                <button type="button" className="btn" disabled={busy} onClick={selectAllPending}>
                  {t.adminSelectAllPending}
                </button>
                {selectedCount ? (
                  <button type="button" className="btn" disabled={busy} onClick={clearSelection}>
                    {t.adminClearSelection}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="btn ink"
                  disabled={busy || !selectedCount}
                  onClick={approveSelected}
                >
                  {t.adminApproveSelected}
                </button>
                {selectedCount ? <span className="hint">{t.adminSelectedCount(selectedCount)}</span> : null}
              </div>
            ) : null}
            {items.length ? (
            <div className="admin-mod-table-wrap">
              <table className="admin-mod-table">
                <thead>
                  <tr>
                    <th className="admin-mod-check" scope="col">
                      <span className="visually-hidden">{t.adminSelectAllPending}</span>
                    </th>
                    <th scope="col">{t.adminColIngested}</th>
                    <th scope="col">{t.adminColTitle}</th>
                    <th scope="col">{t.adminColSource}</th>
                    <th className="admin-mod-actions" scope="col">{t.adminColActions}</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((job) => {
                    const muted = job.status === "closed" || job.status === "rejected";
                    const ingested = dateCell(job.created_at, locale, t.adminDateUnknown);
                    return (
                      <tr key={job.id} className={muted ? "is-muted" : undefined}>
                        <td className="admin-mod-check">
                          {job.status === "pending" ? (
                            <label className="inline admin-select">
                              <input
                                type="checkbox"
                                checked={selected.has(job.id)}
                                onChange={() => toggleSelected(job.id)}
                              />
                            </label>
                          ) : null}
                        </td>
                        <td className="admin-mod-date">{ingested}</td>
                        <td className="admin-mod-title">
                          <div className="admin-mod-title-row">
                            {job.status === "published" ? (
                              <a className="admin-mod-name" href={hrefFor(locale, { jobId: job.id })}>
                                {job.title}
                              </a>
                            ) : job.status !== "closed" ? (
                              <button
                                type="button"
                                className="admin-mod-name linkish"
                                disabled={busy}
                                onClick={() => {
                                  setError("");
                                  setNote("");
                                  setBusy(true);
                                  fetchAdminJob(job.id)
                                    .then((full) => {
                                      setEditing(job.id);
                                      setForm(fromJob(locale, full));
                                    })
                                    .catch(() => setError(t.loadError))
                                    .finally(() => setBusy(false));
                                }}
                              >
                                {job.title}
                              </button>
                            ) : (
                              <span className="admin-mod-name">{job.title}</span>
                            )}
                            <span className={statusClass(job.status)}>{statusLabel(t, job.status)}</span>
                          </div>
                          {job.company ? <span className="admin-mod-sub">{job.company}</span> : null}
                          {job.reject_reason ? (
                            <span className="admin-mod-sub admin-mod-reject">
                              {t.rejectReason}: {job.reject_reason}
                            </span>
                          ) : null}
                        </td>
                        <td className="admin-mod-source">{sourceLabel(t, job)}</td>
                        <td className="admin-mod-actions">
                          <div className="admin-mod-action-row">
                            {job.status === "pending" ? (
                              <>
                                <button
                                  type="button"
                                  className="btn small ink"
                                  disabled={busy}
                                  onClick={() => act(job, "approve", null, t.adminApprovedNote)}
                                >
                                  {t.adminApprove}
                                </button>
                                <button
                                  type="button"
                                  className="btn small red"
                                  disabled={busy}
                                  onClick={() => rejectJob(job)}
                                >
                                  {t.adminReject}
                                </button>
                              </>
                            ) : null}
                            {job.status !== "closed" && job.owner_subject ? (
                              <button
                                type="button"
                                className="btn small red"
                                disabled={busy}
                                onClick={() => act(job, "close", t.adCloseAsk, t.adClosedNote)}
                              >
                                {t.adClose}
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
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
      ) : null}

      {tab === "collected" || seenCollected ? (
        <div hidden={tab !== "collected"}>
          <CollectedAdmin locale={locale} initialItems={initialCrawled} />
        </div>
      ) : null}
      {tab === "manual" ? <ManualAd locale={locale} onSaved={load} /> : null}
      {tab === "applications" ? (
        <div className="h2-panel h2-candidate-list">
          <ApplicationList locale={locale} items={applications} mode="staff" onChanged={load} />
        </div>
      ) : null}
      {tab === "ai" || seenAi ? (
        <div hidden={tab !== "ai"}>
          <AdminAiFlags locale={locale} initial={initialAiFlags} />
        </div>
      ) : null}
    </div>
  );
}
