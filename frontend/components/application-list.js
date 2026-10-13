"use client";

import { Fragment, useState } from "react";
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

function dateCell(value, locale, fallback) {
  const label = calendarDate(value, locale);
  if (!label) return fallback;
  return <time dateTime={String(value).slice(0, 10)}>{label}</time>;
}

function StaffApplicationTable({ locale, t, pageItems, busy, decide, openId, setOpenId }) {
  return (
    <div className="admin-mod-table-wrap">
      <table className="admin-mod-table">
        <thead>
          <tr>
            <th className="admin-mod-date" scope="col">{t.adminColIngested}</th>
            <th scope="col">{t.adminColTitle}</th>
            <th className="admin-mod-candidate" scope="col">{t.adminColCandidate}</th>
            <th className="admin-mod-actions" scope="col">{t.adminColActions}</th>
          </tr>
        </thead>
        <tbody>
          {pageItems.map((item) => {
            const isOpen = openId === item.id;
            const muted = item.status === "rejected";
            return (
              <Fragment key={item.id}>
                <tr className={`${muted ? "is-muted" : ""}${isOpen ? " is-editing" : ""}`.trim() || undefined}>
                  <td className="admin-mod-date">{dateCell(item.created_at, locale, t.adminDateUnknown)}</td>
                  <td className="admin-mod-title">
                    <div className="admin-mod-title-row">
                      <button
                        type="button"
                        className={`admin-mod-name linkish${isOpen ? " is-open" : ""}`}
                        aria-expanded={isOpen}
                        onClick={() => setOpenId(isOpen ? null : item.id)}
                      >
                        {item.job_title}
                      </button>
                      <span className={statusClass(item.status)}>{appStatusLabel(t, item.status)}</span>
                      {item.job_id ? (
                        <a className="admin-mod-view" href={hrefFor(locale, { jobId: item.job_id })}>
                          {t.viewJob}
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="admin-mod-candidate">
                    <span className="admin-mod-candidate-label" title={item.candidate_subject || ""}>
                      {item.candidate_subject || t.adminDateUnknown}
                    </span>
                  </td>
                  <td className="admin-mod-actions">
                    <div className="admin-mod-action-row">
                      <button
                        type="button"
                        className="btn small primary"
                        disabled={busy === item.id}
                        onClick={() => decide(item, "seen")}
                      >
                        {t.appSeenAction}
                      </button>
                      <button
                        type="button"
                        className="btn small red"
                        disabled={busy === item.id}
                        onClick={() => decide(item, "rejected")}
                      >
                        {t.appRejectAction}
                      </button>
                    </div>
                  </td>
                </tr>
                {isOpen ? (
                  <tr className="admin-mod-edit-row">
                    <td colSpan={4}>
                      <div className="admin-app-detail">
                        <ApplicationTimeline locale={locale} t={t} item={item} />
                        {item.message ? <p className="admin-app-detail-line">{item.message}</p> : null}
                        {item.phone ? (
                          <p className="admin-app-detail-line">
                            {t.applyPhone}: {item.phone}
                          </p>
                        ) : null}
                        {item.email ? (
                          <p className="admin-app-detail-line">
                            {t.applyEmail}: {item.email}
                          </p>
                        ) : null}
                        {(item.answers || [])
                          .filter((answer) => answer.answer)
                          .map((answer) => (
                            <p key={answer.question} className="admin-app-detail-line">
                              <strong>{answer.question}</strong> {answer.answer}
                            </p>
                          ))}
                        {item.has_cv ? (
                          <a className="btn small primary" href={`/api/auth/applications/${item.id}/cv`}>
                            {t.downloadCv}
                          </a>
                        ) : (
                          <p className="hint">{t.noCv}</p>
                        )}
                      </div>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ApplicationList({ locale, title, items, hideEmpty = false, mode = "candidate", onChanged }) {
  const t = text(locale);
  const rows = Array.isArray(items) ? items : [];
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(0);
  const [openId, setOpenId] = useState(null);
  const { pageItems, currentPage, totalPages, pageSize, total, goToPage: goToPaged } = usePagination(rows, LIST_PAGE_SIZE);
  const candidate = mode === "candidate";
  const staffTable = mode === "staff";

  function goToPage(page) {
    setOpenId(null);
    goToPaged(page);
  }

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
      {staffTable && rows.length ? (
        <StaffApplicationTable
          locale={locale}
          t={t}
          pageItems={pageItems}
          busy={busy}
          decide={decide}
          openId={openId}
          setOpenId={setOpenId}
        />
      ) : null}
      {!staffTable ? (
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
      ) : null}
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
