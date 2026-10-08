"use client";

import { useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { patchApplicationStatus, withdrawApplication } from "../lib/server/refresh";
import { Pager } from "./pager";

export function appStatusLabel(t, status) {
  if (status === "seen") return t.appSeen;
  if (status === "rejected") return t.appRejected;
  return t.appSubmitted;
}

export function statusClass(status) {
  if (status === "seen") return "app-status live";
  if (status === "rejected") return "app-status rejected";
  return "app-status";
}

export function buildTimeline(item) {
  if (Array.isArray(item.timeline) && item.timeline.length) return item.timeline;
  const steps = [{ status: "submitted", at: item.created_at || "" }];
  if (item.status === "seen" || item.status === "rejected") {
    const step = { status: item.status, at: "" };
    if (item.status === "rejected" && item.reason) step.note = item.reason;
    steps.push(step);
  }
  return steps;
}

export function ApplicationTimeline({ locale, t, item }) {
  const steps = buildTimeline(item);
  const note = [...steps].reverse().find((step) => step.note)?.note || "";
  return (
    <div className="app-timeline-wrap">
      <ol className="app-timeline" aria-label={t.appTimelineLabel}>
        {steps.map((step, index) => {
          const when = calendarDate(step.at, locale);
          const current = index === steps.length - 1;
          return (
            <li key={`${step.status}-${index}`} className={current ? "app-step current" : "app-step"}>
              <span className={`app-step-dot ${step.status}`} aria-hidden="true" />
              <span className="app-step-label">{appStatusLabel(t, step.status)}</span>
              {when ? <time dateTime={step.at}>{when}</time> : <span className="app-step-when-empty" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
      {note ? (
        <p className="app-step-note">
          <span className="app-step-note-label">{t.appEmployerNote}</span>
          {note}
        </p>
      ) : null}
    </div>
  );
}

export function ApplicationList({ locale, title, items, hideEmpty = false, mode = "candidate", onChanged }) {
  const t = text(locale);
  const rows = Array.isArray(items) ? items : [];
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(0);
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage } = usePagination(rows, LIST_PAGE_SIZE);
  const candidate = mode === "candidate";

  async function withdraw(item) {
    if (!window.confirm(t.appWithdrawAsk)) return;
    setError("");
    setNote("");
    setBusy(item.id);
    const res = await withdrawApplication(item.id);
    setBusy(0);
    if (!res.ok) {
      setError(t.appStatusError);
      return;
    }
    setNote(t.appWithdrawn);
    if (onChanged) onChanged();
  }

  async function decide(item, status) {
    let reason = "";
    if (status === "rejected") {
      const typed = window.prompt(t.appRejectAsk);
      if (typed == null) return;
      reason = typed;
    }
    setError("");
    setNote("");
    setBusy(item.id);
    const res = await patchApplicationStatus(mode, item.id, status, reason);
    setBusy(0);
    if (!res.ok) {
      setError(t.appStatusError);
      return;
    }
    setNote(t.appUpdated);
    if (onChanged) onChanged();
  }

  if (hideEmpty && rows.length === 0) return null;

  return (
    <section className={candidate ? "app-list" : undefined}>
      {title ? <h2 className="section-label">{title}</h2> : null}
      {error ? <p className="note">{error}</p> : null}
      {note ? <p className="note">{note}</p> : null}
      {rows.length === 0 ? <p className="empty-line">{t.applicationsEmpty}</p> : null}
      <div className={candidate ? "app-list-items" : "list"}>
        {pageItems.map((item) => (
          <article key={item.id} className={candidate ? "app-card" : "card"}>
            <div className="app-card-top">
              <div className="app-card-title">
                {item.job_id ? (
                  <h2>
                    <a href={hrefFor(locale, { jobId: item.job_id })}>{item.job_title}</a>
                  </h2>
                ) : (
                  <h2>{item.job_title}</h2>
                )}
                {!candidate && item.candidate_subject ? (
                  <p className="app-card-meta">{item.candidate_subject}</p>
                ) : null}
              </div>
              <p className={statusClass(item.status)}>{appStatusLabel(t, item.status)}</p>
            </div>

            <ApplicationTimeline locale={locale} t={t} item={item} />

            {!candidate ? (
              <div className="app-card-details">
                {item.message ? <p className="admin-body">{item.message}</p> : null}
                {item.phone ? (
                  <p className="admin-body">
                    {t.applyPhone}: {item.phone}
                  </p>
                ) : null}
                {item.email ? (
                  <p className="admin-body">
                    {t.applyEmail}: {item.email}
                  </p>
                ) : null}
                {(item.answers || [])
                  .filter((answer) => answer.answer)
                  .map((answer) => (
                    <p key={answer.question} className="admin-body">
                      <strong>{answer.question}</strong> {answer.answer}
                    </p>
                  ))}
                {item.has_cv ? (
                  <a className="btn primary" href={`/api/auth/applications/${item.id}/cv`}>
                    {t.downloadCv}
                  </a>
                ) : (
                  <p className="hint">{t.noCv}</p>
                )}
              </div>
            ) : null}

            <div className="app-card-actions">
              {candidate ? (
                <button type="button" className="btn red" disabled={busy === item.id} onClick={() => withdraw(item)}>
                  {t.appWithdraw}
                </button>
              ) : (
                <>
                  <button type="button" className="btn primary" disabled={busy === item.id} onClick={() => decide(item, "seen")}>
                    {t.appSeenAction}
                  </button>
                  <button type="button" className="btn red" disabled={busy === item.id} onClick={() => decide(item, "rejected")}>
                    {t.appRejectAction}
                  </button>
                </>
              )}
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
  );
}
