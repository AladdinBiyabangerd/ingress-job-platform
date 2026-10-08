"use client";

import { useEffect, useState } from "react";
import { applyFormFromJob, applyFormPayload, applyFormReady, defaultApplyForm } from "../lib/apply-form";
import { hrefFor, languageLabel, text } from "../lib/copy";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { cabinetCloseJob, cabinetSaveJob, refreshCabinet } from "../lib/server/refresh";
import { ApplicationList } from "./application-list";
import { ApplyFormFields } from "./apply-form-fields";
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

function blank(locale, me) {
  return {
    title: "",
    company: me?.company_profile?.company_name || "",
    city: "",
    remote: false,
    text: "",
    language: locale,
    salary: "",
    job_type: "",
    applicationForm: defaultApplyForm(),
  };
}

function fromJob(locale, me, job) {
  return {
    title: job.title || "",
    company: me.staff ? job.company || "" : me?.company_profile?.company_name || job.company || "",
    city: job.remote ? "" : job.city || "",
    remote: Boolean(job.remote),
    text: job.text || "",
    language: job.language || locale,
    salary: job.salary || "",
    job_type: job.job_type || "",
    applicationForm: applyFormFromJob(job),
  };
}

function canEdit(me, job) {
  if (!job || job.status === "closed") return false;
  if (me.staff) return true;
  return job.status === "pending" || job.status === "published" || job.status === "rejected";
}

export function Cabinet({ locale, me, initialJobs = null, initialApplications = null }) {
  const t = text(locale);
  const seededJobs = Array.isArray(initialJobs);
  const seededApps = Array.isArray(initialApplications);
  const seededList = seededJobs && seededApps;
  const [items, setItems] = useState(() => (seededJobs ? initialJobs : []));
  const [form, setForm] = useState(() => blank(locale, me));
  const [editing, setEditing] = useState(null);
  const [tab, setTab] = useState("create");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [applications, setApplications] = useState(() => (seededApps ? initialApplications : []));
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage, resetPage } = usePagination(items, LIST_PAGE_SIZE);

  async function load() {
    const data = await refreshCabinet();
    setItems(data.jobs);
    setApplications(data.applications);
  }

  useEffect(() => {
    if (seededList) return undefined;
    let cancelled = false;
    load()
      .catch(() => {
        if (!cancelled) setError(t.loadError);
      });
    return () => {
      cancelled = true;
    };
  }, [seededList, t.loadError]);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function reset() {
    setEditing(null);
    setForm(blank(locale, me));
    setError("");
  }

  function openCreate() {
    reset();
    setNote("");
    setTab("create");
  }

  function openMyAds() {
    setTab("ads");
  }

  function openApplications() {
    setTab("applications");
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setNote("");
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
    const res = await cabinetSaveJob(editing, payload);
    const saved = res.data;
    setBusy(false);
    if (!res.ok) {
      setError(res.status === 422 ? t.adRequired : res.status === 409 ? t.cannotChange : res.status === 403 ? t.cannotEdit : t.cabinetError);
      return;
    }
    setNote(saved.status === "published" ? t.adSavedLive : t.adSavedPending);
    reset();
    setTab("ads");
    resetPage();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function closeAd(job) {
    if (!window.confirm(t.adCloseAsk)) return;
    setError("");
    setNote("");
    const res = await cabinetCloseJob(job.id);
    if (!res.ok) {
      setError(t.cabinetError);
      return;
    }
    setNote(t.adClosedNote);
    if (editing === job.id) reset();
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  return (
    <div className="cabinet">
      <div className="cabinet-head">
        <div>
          <h1>{t.postTitle}</h1>
          <p className="lede">{t.cabinetLede}</p>
        </div>
        <div className="cabinet-tabs" role="tablist" aria-label={t.postTitle}>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "create"}
            className={tab === "create" ? "on" : ""}
            onClick={openCreate}
          >
            {editing ? t.editAd : t.post}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "ads"}
            className={tab === "ads" ? "on" : ""}
            onClick={openMyAds}
          >
            {t.myAds}
            {items.length ? <span className="cabinet-tab-count">{items.length}</span> : null}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "applications"}
            className={tab === "applications" ? "on" : ""}
            onClick={openApplications}
          >
            {t.cabinetApplicationsTab}
            {applications.length ? <span className="cabinet-tab-count">{applications.length}</span> : null}
          </button>
        </div>
      </div>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}

      {tab === "create" ? (
        <form className="form-card cabinet-form" onSubmit={onSubmit}>
          <div className="cabinet-form-head">
            <h2>{editing ? t.editAd : t.post}</h2>
            {editing && items.find((job) => job.id === editing)?.status === "rejected" ? <p className="hint">{t.resubmitHint}</p> : null}
            {editing && !me.staff && items.find((job) => job.id === editing)?.status === "published" ? <p className="hint">{t.reviewHint}</p> : null}
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
                  {t.companyName}
                  <input
                    value={form.company}
                    maxLength={120}
                    required
                    readOnly={!me.staff}
                    onChange={(event) => setField("company", event.target.value)}
                  />
                  {!me.staff ? <span className="hint">{t.companyLocked}</span> : null}
                </label>
                <label className="cabinet-span">
                  {t.adTitle}
                  <input value={form.title} maxLength={140} required onChange={(event) => setField("title", event.target.value)} />
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
            {editing ? (
              <button type="button" className="btn red" onClick={reset}>{t.adCancel}</button>
            ) : null}
          </div>
        </form>
      ) : null}

      {tab === "ads" ? (
        <section className="cabinet-ads">
          {items.length === 0 ? <p className="empty-line">{t.cabinetEmpty}</p> : null}
          <div className="list">
            {pageItems.map((job) => (
              <article key={job.id} className={job.status === "closed" || job.status === "rejected" ? "card closed" : "card"}>
                <p className={job.status === "published" ? "source-pill live" : job.status === "closed" ? "source-pill closed" : job.status === "rejected" ? "source-pill rejected" : "source-pill"}>
                  {statusLabel(t, job.status)}
                </p>
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
                {job.status === "rejected" && job.reject_reason ? <p className="note">{t.rejectReason}: {job.reject_reason}</p> : null}
                <ApplicationList
                  locale={locale}
                  title={t.ownerApplications}
                  items={applications.filter((item) => item.job_id === job.id)}
                  hideEmpty
                  mode="owner"
                  onChanged={load}
                />
                <div className="ad-actions">
                  {canEdit(me, job) ? (
                    <button
                      type="button"
                      className="btn primary"
                      onClick={() => {
                        setEditing(job.id);
                        setForm(fromJob(locale, me, job));
                        setError("");
                        setNote("");
                        setTab("create");
                      }}
                    >
                      {t.adEdit}
                    </button>
                  ) : null}
                  {job.status !== "closed" ? (
                    <button type="button" className="btn red" onClick={() => closeAd(job)}>
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

      {tab === "applications" ? (
        <section className="cabinet-apps">
          <ApplicationList
            locale={locale}
            title={t.ownerApplicationsAll}
            items={applications}
            mode="owner"
            onChanged={load}
          />
        </section>
      ) : null}
    </div>
  );
}
