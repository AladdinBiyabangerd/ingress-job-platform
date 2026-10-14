"use client";

import { Fragment, useEffect, useState } from "react";
import { applyFormFromJob, applyFormPayload, applyFormReady } from "../lib/apply-form";
import { hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  adminActJob,
  adminApproveBulk,
  adminApproveThreshold,
  adminBackfillConfidence,
  adminPatchJob,
  adminRecheckMarketFit,
  adminRejectJob,
  crawledPatchJob,
  fetchAdminJob,
  refreshAdminQueue,
} from "../lib/server/refresh";
import { AdminAiFlags } from "./admin-ai-flags";
import { AdminCategories } from "./admin-categories";
import { AdminOpsStatus } from "./admin-ops-status";
import { ApplyFormFields } from "./apply-form-fields";
import { CollectedAdmin } from "./collected-admin";
import { ManualAd } from "./manual-ad";
import { PageChrome } from "./page-chrome";
import { Pager } from "./pager";

const TYPES = ["", "ofis", "hibrid", "uzaqdan"];
const ADMIN_TABS = new Set(["queue", "rejected", "collected", "manual", "categories", "ai", "ops"]);

function normalizeAdminTab(value) {
  const tab = String(value || "").trim();
  return ADMIN_TABS.has(tab) ? tab : "queue";
}

function adminTabHref(locale, tab) {
  const base = hrefFor(locale, { mode: "admin" });
  const next = normalizeAdminTab(tab);
  return next === "queue" ? base : `${base}?tab=${encodeURIComponent(next)}`;
}

function typeLabel(t, value) {
  if (value === "ofis") return t.jobOffice;
  if (value === "hibrid") return t.jobHybrid;
  if (value === "uzaqdan") return t.jobRemoteType;
  return "";
}

function confidenceCell(value, reason) {
  if (value == null || value === "") {
    return <span className="admin-mod-pct-empty">—</span>;
  }
  const label = `${value}%`;
  if (reason) {
    return (
      <span className="admin-mod-pct" title={reason}>
        {label}
      </span>
    );
  }
  return <span className="admin-mod-pct">{label}</span>;
}

function jobScore(job, score) {
  const raw = score === "rule" ? job.rule_confidence : job.ai_confidence;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function countThresholdMatches(items, score, op, threshold) {
  const cut = Number(threshold);
  if (!Number.isFinite(cut)) return 0;
  return items.filter((job) => {
    if (job.status !== "pending") return false;
    const value = jobScore(job, score);
    if (value == null) return false;
    return op === "lte" ? value <= cut : value >= cut;
  }).length;
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
    language: job.language || locale,
    salary: job.salary || "",
    job_type: job.job_type || "",
    applicationForm: applyFormFromJob(job),
  };
}

export function Admin({
  locale,
  initialTab = "queue",
  initialJobs = null,
  initialCrawled = null,
  initialAiFlags = null,
}) {
  const t = text(locale);
  const seededJobs = Array.isArray(initialJobs);
  const startTab = normalizeAdminTab(initialTab);
  const [tab, setTab] = useState(startTab);
  const [seenCollected, setSeenCollected] = useState(startTab === "collected");
  const [seenAi, setSeenAi] = useState(startTab === "ai");
  const [seenOps, setSeenOps] = useState(startTab === "ops");
  const [items, setItems] = useState(() => (seededJobs ? initialJobs : []));
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [scoreKind, setScoreKind] = useState("ai");
  const [scoreOp, setScoreOp] = useState("gte");
  const [scoreThreshold, setScoreThreshold] = useState("70");

  async function load() {
    const data = await refreshAdminQueue();
    setItems(data.jobs);
    setSelected(new Set());
  }

  const queueItems = items.filter((job) => job.status !== "rejected");
  const rejectedItems = items.filter((job) => job.status === "rejected");
  const listItems = tab === "rejected" ? rejectedItems : queueItems;
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage: goToPaged, resetPage } = usePagination(
    listItems,
    LIST_PAGE_SIZE,
  );

  function cancelEdit() {
    setEditing(null);
    setForm(null);
    setError("");
  }

  function selectTab(next, { push = true } = {}) {
    const value = normalizeAdminTab(next);
    if (editing) cancelEdit();
    setTab(value);
    resetPage();
    if (value === "collected") setSeenCollected(true);
    if (value === "ai") setSeenAi(true);
    if (value === "ops") setSeenOps(true);
    if (typeof window === "undefined") return;
    const url = adminTabHref(locale, value);
    const current = `${window.location.pathname}${window.location.search}`;
    if (current === url) return;
    if (push) window.history.pushState(null, "", url);
    else window.history.replaceState(null, "", url);
  }

  function goToPage(page) {
    if (editing) cancelEdit();
    goToPaged(page);
  }

  useEffect(() => {
    if (seededJobs) return undefined;
    let cancelled = false;
    load().catch(() => {
      if (!cancelled) setError(t.loadError);
    });
    return () => {
      cancelled = true;
    };
  }, [seededJobs, t.loadError]);

  useEffect(() => {
    function onPopState() {
      const value = normalizeAdminTab(new URLSearchParams(window.location.search).get("tab"));
      setTab(value);
      resetPage();
      if (value === "collected") setSeenCollected(true);
      if (value === "ai") setSeenAi(true);
      if (value === "ops") setSeenOps(true);
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function setField(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
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

  async function approveByThreshold({ quick = false } = {}) {
    const matchCount = countThresholdMatches(items, scoreKind, scoreOp, scoreThreshold);
    if (!matchCount) {
      setNote(t.adminThresholdNone);
      return;
    }
    if (!quick && !window.confirm(t.adminThresholdConfirm(matchCount))) return;
    setError("");
    setNote("");
    setBusy(true);
    const res = await adminApproveThreshold({
      score: scoreKind,
      op: scoreOp,
      threshold: Number(scoreThreshold),
    });
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    const count = Number(res.data?.approved) || 0;
    setNote(count ? t.adminBulkApprovedNote(count) : t.adminThresholdNone);
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function recheckByThreshold() {
    const matchCount = countThresholdMatches(items, scoreKind, scoreOp, scoreThreshold);
    if (!matchCount) {
      setNote(t.adminThresholdNone);
      return;
    }
    setError("");
    setNote("");
    setBusy(true);
    const res = await adminRecheckMarketFit({
      score: scoreKind,
      op: scoreOp,
      threshold: Number(scoreThreshold),
      limit: 30,
    });
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(
      t.adminRecheckNote(
        Number(res.data?.checked) || 0,
        Number(res.data?.rejected) || 0,
        Number(res.data?.failed) || 0,
      ),
    );
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  async function backfillConfidence() {
    setError("");
    setNote("");
    setBusy(true);
    const res = await adminBackfillConfidence({ aiLimit: 40 });
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(
      t.adminBackfillNote(
        Number(res.data?.rule_filled) || 0,
        Number(res.data?.ai_checked) || 0,
        Number(res.data?.ai_rejected) || 0,
        Number(res.data?.ai_failed) || 0,
        Number(res.data?.still_unscored) || 0,
      ),
    );
    try {
      await load();
    } catch {
      setError(t.loadError);
    }
  }

  const pendingIds = items.filter((job) => job.status === "pending").map((job) => job.id);
  const pendingCount = pendingIds.length;
  const selectedCount = selected.size;
  const allPendingSelected = pendingCount > 0 && pendingIds.every((id) => selected.has(id));
  const somePendingSelected = pendingIds.some((id) => selected.has(id));

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
          onClick={() => selectTab("queue")}
        >
          {t.adminQueue}
          {pendingCount ? <span className="h2-tab-count">{pendingCount}</span> : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "rejected"}
          className={tab === "rejected" ? "on" : ""}
          onClick={() => selectTab("rejected")}
        >
          {t.adminRejectedTab}
          {rejectedItems.length ? <span className="h2-tab-count">{rejectedItems.length}</span> : null}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "collected"}
          className={tab === "collected" ? "on" : ""}
          onClick={() => selectTab("collected")}
        >
          {t.collectedTitle}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "manual"}
          className={tab === "manual" ? "on" : ""}
          onClick={() => selectTab("manual")}
        >
          {t.manualTitle}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "categories"}
          className={tab === "categories" ? "on" : ""}
          onClick={() => selectTab("categories")}
        >
          Kateqoriyalar
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ai"}
          className={tab === "ai" ? "on" : ""}
          onClick={() => selectTab("ai")}
        >
          {t.adminAiTitle}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ops"}
          className={tab === "ops" ? "on" : ""}
          onClick={() => selectTab("ops")}
        >
          {t.opsTab}
        </button>
      </div>
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}

      {tab === "queue" || tab === "rejected" ? (
        <section className="h2-employer-queue">
          <div className="h2-panel h2-employer-list">
            {listItems.length === 0 ? (
              <p className="empty-line">{tab === "rejected" ? t.adminRejectedEmpty : t.adminEmpty}</p>
            ) : null}
            {listItems.length ? (
            <div className="admin-mod-table-wrap">
              {tab === "queue" ? (
                <div className="admin-mod-threshold">
                  <label className="admin-mod-threshold-field">
                    <span className="visually-hidden">{t.adminScoreAi}</span>
                    <select
                      value={scoreKind}
                      disabled={busy}
                      onChange={(event) => setScoreKind(event.target.value === "rule" ? "rule" : "ai")}
                    >
                      <option value="ai">{t.adminScoreAi}</option>
                      <option value="rule">{t.adminScoreRule}</option>
                    </select>
                  </label>
                  <label className="admin-mod-threshold-field">
                    <span className="visually-hidden">{t.adminOpGte}</span>
                    <select
                      value={scoreOp}
                      disabled={busy}
                      onChange={(event) => setScoreOp(event.target.value === "lte" ? "lte" : "gte")}
                    >
                      <option value="gte">{t.adminOpGte}</option>
                      <option value="lte">{t.adminOpLte}</option>
                    </select>
                  </label>
                  <label className="admin-mod-threshold-field">
                    <span className="visually-hidden">{t.adminThresholdLabel}</span>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={scoreThreshold}
                      disabled={busy}
                      onChange={(event) => setScoreThreshold(event.target.value)}
                      aria-label={t.adminThresholdLabel}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn small primary"
                    disabled={busy}
                    onClick={() => approveByThreshold({ quick: false })}
                  >
                    {t.adminThresholdPublish}
                  </button>
                  <button
                    type="button"
                    className="btn small"
                    disabled={busy}
                    onClick={() => approveByThreshold({ quick: true })}
                  >
                    {t.adminThresholdPublishQuick}
                  </button>
                  <button
                    type="button"
                    className="btn small"
                    disabled={busy}
                    onClick={recheckByThreshold}
                  >
                    {t.adminThresholdRecheck}
                  </button>
                  <button
                    type="button"
                    className="btn small"
                    disabled={busy}
                    onClick={backfillConfidence}
                  >
                    {t.adminBackfillConfidence}
                  </button>
                </div>
              ) : null}
              {tab === "queue" && selectedCount ? (
                <div className="admin-mod-bulk">
                  <span className="admin-mod-bulk-count">{t.adminSelectedCount(selectedCount)}</span>
                  <button
                    type="button"
                    className="btn small primary"
                    disabled={busy}
                    onClick={approveSelected}
                  >
                    {t.adminApprove}
                  </button>
                  <button
                    type="button"
                    className="btn small"
                    disabled={busy}
                    onClick={clearSelection}
                  >
                    {t.adminClearSelection}
                  </button>
                </div>
              ) : null}
              <table className="admin-mod-table">
                <thead>
                  <tr>
                    {tab === "queue" ? (
                      <th className="admin-mod-check" scope="col">
                        {pendingCount ? (
                          <label className="inline admin-select">
                            <input
                              type="checkbox"
                              checked={allPendingSelected}
                              ref={(el) => {
                                if (el) el.indeterminate = somePendingSelected && !allPendingSelected;
                              }}
                              onChange={() => {
                                if (allPendingSelected) clearSelection();
                                else selectAllPending();
                              }}
                              aria-label={t.adminSelectAllPending}
                            />
                          </label>
                        ) : (
                          <span className="visually-hidden">{t.adminSelectAllPending}</span>
                        )}
                      </th>
                    ) : null}
                    <th className="admin-mod-date" scope="col">{t.adminColIngested}</th>
                    <th scope="col">{t.adminColTitle}</th>
                    <th className="admin-mod-pct-col" scope="col">{t.adminColRulePct}</th>
                    <th className="admin-mod-pct-col" scope="col">{t.adminColAiPct}</th>
                    <th className="admin-mod-source" scope="col">{t.adminColSource}</th>
                    <th className="admin-mod-actions" scope="col">{t.adminColActions}</th>
                  </tr>
                </thead>
                <tbody>
                  {pageItems.map((job) => {
                    const muted = job.status === "closed" || job.status === "rejected";
                    const ingested = dateCell(
                      tab === "rejected" ? (job.updated_at || job.created_at) : job.created_at,
                      locale,
                      t.adminDateUnknown,
                    );
                    const isOpen = editing === job.id;
                    const colSpan = tab === "rejected" ? 6 : 7;
                    return (
                      <Fragment key={job.id}>
                      <tr className={`${muted ? "is-muted" : ""}${isOpen ? " is-editing" : ""}`.trim() || undefined}>
                        {tab === "queue" ? (
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
                        ) : null}
                        <td className="admin-mod-date">{ingested}</td>
                        <td className="admin-mod-title">
                          <div className="admin-mod-title-row">
                            {job.status !== "closed" ? (
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
                                  fetchAdminJob(job.id)
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
                            ) : (
                              <span className="admin-mod-name">{job.title}</span>
                            )}
                            {job.status !== "pending" && tab !== "rejected" ? (
                              <span className={statusClass(job.status)}>{statusLabel(t, job.status)}</span>
                            ) : null}
                            {job.status === "published" ? (
                              <a className="admin-mod-view" href={hrefFor(locale, { jobId: job.id })}>
                                {t.viewJob}
                              </a>
                            ) : null}
                          </div>
                          {job.company ? <span className="admin-mod-sub">{job.company}</span> : null}
                          {job.reject_reason ? (
                            <span className="admin-mod-sub admin-mod-reject">
                              {t.rejectReason}: {job.reject_reason}
                            </span>
                          ) : null}
                        </td>
                        <td className="admin-mod-pct-col">
                          {confidenceCell(job.rule_confidence, job.market_fit_reason)}
                        </td>
                        <td className="admin-mod-pct-col">
                          {confidenceCell(job.ai_confidence, job.market_fit_reason)}
                        </td>
                        <td className="admin-mod-source">{sourceCell(t, job)}</td>
                        <td className="admin-mod-actions">
                          <div className="admin-mod-action-row">
                            {job.status === "pending" ? (
                              <>
                                <button
                                  type="button"
                                  className="btn small primary"
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
                            {job.status !== "closed" && job.status !== "rejected" && job.owner_subject ? (
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
                      {isOpen ? (
                        <tr className="admin-mod-edit-row">
                          <td colSpan={colSpan}>
                            {form ? (
                              <form className="admin-mod-edit-form cabinet-form staff-compose-form" onSubmit={onSave}>
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
                                          required={!isCollected(editing)}
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
                                    {!isCollected(editing) ? (
                                      <div className="staff-compose-apply">
                                        <ApplyFormFields
                                          locale={locale}
                                          value={form.applicationForm}
                                          onChange={(applicationForm) => setField("applicationForm", applicationForm)}
                                        />
                                      </div>
                                    ) : null}
                                  </div>
                                  <label className="cabinet-body staff-compose-body">
                                    {t.adBody}
                                    <textarea
                                      value={form.text}
                                      maxLength={8000}
                                      required
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
      ) : null}

      {tab === "collected" || seenCollected ? (
        <div hidden={tab !== "collected"}>
          <CollectedAdmin locale={locale} initialItems={initialCrawled} />
        </div>
      ) : null}
      {tab === "manual" ? <ManualAd locale={locale} onSaved={load} /> : null}
      {tab === "categories" ? <AdminCategories /> : null}
      {tab === "ai" || seenAi ? (
        <div hidden={tab !== "ai"}>
          <AdminAiFlags locale={locale} initial={initialAiFlags} />
        </div>
      ) : null}
      {tab === "ops" || seenOps ? (
        <div hidden={tab !== "ops"}>
          <AdminOpsStatus locale={locale} />
        </div>
      ) : null}
    </div>
  );
}
