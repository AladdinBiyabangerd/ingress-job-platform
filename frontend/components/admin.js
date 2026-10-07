"use client";

import { useEffect, useState } from "react";
import { applyFormFromJob, applyFormPayload, applyFormReady } from "../lib/apply-form";
import { hrefFor, languageLabel, text } from "../lib/copy";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  adminActJob,
  adminPatchJob,
  adminRejectJob,
  fetchAdminJob,
  refreshAdminApplications,
  refreshAdminQueue,
} from "../lib/server/refresh";
import { AdminAiFlags } from "./admin-ai-flags";
import { ApplicationList } from "./application-list";
import { ApplyFormFields } from "./apply-form-fields";
import { CollectedAdmin } from "./collected-admin";
import { ManualAd } from "./manual-ad";
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
  const [applications, setApplications] = useState(() => (seededApps ? initialApplications : []));

  async function load() {
    const data = await refreshAdminQueue();
    setItems(data.jobs);
    setApplications(data.applications);
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

  async function onSave(event) {
    event.preventDefault();
    if (!editing || !form) return;
    setError("");
    setNote("");
    if (!form.title.trim() || !form.company.trim() || !form.text.trim() || !(form.remote || form.city.trim())) {
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
      form: applyFormPayload(form.applicationForm),
    };
    const res = await adminPatchJob(editing, payload);
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

  const pendingCount = items.filter((job) => job.status === "pending").length;

  return (
    <div className="cabinet">
      <div className="cabinet-head">
        <div>
          <h1>{t.adminTitle}</h1>
          <p className="lede">{t.adminLede}</p>
        </div>
        <div className="cabinet-tabs" role="tablist" aria-label={t.adminTitle}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "queue"}
            className={tab === "queue" ? "on" : ""}
            onClick={() => setTab("queue")}
          >
            {t.adminQueue}
            {pendingCount ? <span className="cabinet-tab-count">{pendingCount}</span> : null}
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
            {applications.length ? <span className="cabinet-tab-count">{applications.length}</span> : null}
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
      </div>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}

      {tab === "queue" ? (
        <section className="cabinet-ads">
          {editing && form ? (
            <form className="form-card cabinet-form" onSubmit={onSave}>
              <div className="cabinet-form-head">
                <h2>{t.editAd}</h2>
              </div>
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
                <aside className="cabinet-form-side">
                  <ApplyFormFields locale={locale} value={form.applicationForm} onChange={(applicationForm) => setField("applicationForm", applicationForm)} />
                </aside>
              </div>
              <div className="ad-actions">
                <button type="submit" className="btn primary" disabled={busy}>{t.adSave}</button>
                <button type="button" className="btn red" onClick={cancelEdit}>{t.adCancel}</button>
              </div>
            </form>
          ) : null}
          {items.length === 0 ? <p className="empty-line">{t.adminEmpty}</p> : null}
          <div className="list">
            {pageItems.map((job) => (
              <article key={job.id} className={job.status === "closed" || job.status === "rejected" ? "card closed" : "card"}>
                <p className={statusClass(job.status)}>{statusLabel(t, job.status)}</p>
                <h2>
                  {job.status === "published" ? (
                    <a href={hrefFor(locale, { jobId: job.id })}>{job.title}</a>
                  ) : (
                    job.title
                  )}
                </h2>
                <div className="meta">
                  <span>{job.company || t.noCompany}</span>
                  <span>{job.remote ? t.placeRemote : job.city || t.noCity}</span>
                  <span>{languageLabel(locale, job.language)}</span>
                  {job.job_type ? <span>{typeLabel(t, job.job_type)}</span> : null}
                  {job.salary ? <span>{job.salary}</span> : null}
                </div>
                {job.text ? (
                  <p className="admin-body">
                    {job.text.length > 280 ? `${job.text.slice(0, 280)}…` : job.text}
                  </p>
                ) : null}
                {job.reject_reason ? <p className="note">{t.rejectReason}: {job.reject_reason}</p> : null}
                <div className="ad-actions">
                  {job.status !== "closed" ? (
                    <button
                      type="button"
                      className="btn primary"
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
                      disabled={busy}
                    >
                      {t.adEdit}
                    </button>
                  ) : null}
                  {job.status === "pending" ? (
                    <>
                      <button
                        type="button"
                        className="btn primary"
                        onClick={() => act(job, "approve", null, t.adminApprovedNote)}
                      >
                        {t.adminApprove}
                      </button>
                      <button
                        type="button"
                        className="btn red"
                        onClick={() => rejectJob(job)}
                      >
                        {t.adminReject}
                      </button>
                    </>
                  ) : null}
                  {job.status !== "closed" ? (
                    <button
                      type="button"
                      className="btn red"
                      onClick={() => act(job, "close", t.adCloseAsk, t.adClosedNote)}
                    >
                      {t.adClose}
                    </button>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
          <Pager
            locale={locale}
            currentPage={currentPage}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onPageChange={goToPage}
          />
        </section>
      ) : null}

      {tab === "collected" || seenCollected ? (
        <div hidden={tab !== "collected"}>
          <CollectedAdmin locale={locale} initialItems={initialCrawled} />
        </div>
      ) : null}
      {tab === "manual" ? <ManualAd locale={locale} onSaved={load} /> : null}
      {tab === "applications" ? (
        <ApplicationList locale={locale} items={applications} mode="staff" onChanged={load} />
      ) : null}
      {tab === "ai" || seenAi ? (
        <div hidden={tab !== "ai"}>
          <AdminAiFlags locale={locale} initial={initialAiFlags} />
        </div>
      ) : null}
    </div>
  );
}
