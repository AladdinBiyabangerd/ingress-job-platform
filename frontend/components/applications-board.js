"use client";

import { useEffect, useMemo, useState } from "react";
import { hrefFor, text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { withdrawApplication } from "../lib/server/refresh";
import { ApplicationTimeline, statusClass } from "./application-list";

const STATUSES = ["submitted", "seen", "rejected"];
const COL_PAGE = 8;

function normalizeStatus(status) {
  const s = String(status || "").trim().toLowerCase();
  if (s === "seen" || s === "rejected") return s;
  return "submitted";
}

function titleInitial(title) {
  const s = String(title || "").trim();
  return s ? s.charAt(0).toUpperCase() : "?";
}

function groupByStatus(items) {
  const groups = { submitted: [], seen: [], rejected: [] };
  for (const item of items) {
    groups[normalizeStatus(item.status)].push(item);
  }
  return groups;
}

function colStatusLabel(t, status) {
  if (status === "seen") return t.applicationsColSeen;
  if (status === "rejected") return t.applicationsColRejected;
  return t.applicationsColSubmitted;
}

function AppsBoardCard({ locale, item, selected, onSelect }) {
  const t = text(locale);
  const when = calendarDate(item.created_at, locale);
  const cvLine = item.has_cv ? item.cv_name || t.downloadCv : t.noCv;
  return (
    <button
      type="button"
      className={["apps-e-card", selected ? "is-selected" : ""].filter(Boolean).join(" ")}
      onClick={() => onSelect(item.id)}
      aria-current={selected ? "true" : undefined}
    >
      <span className="apps-e-avatar" aria-hidden="true">
        {titleInitial(item.job_title)}
      </span>
      <span className="apps-e-card-body">
        <span className="apps-e-card-title">{item.job_title || "—"}</span>
        <span className="apps-e-card-meta">
          {when ? <time dateTime={item.created_at}>{when}</time> : null}
          {when ? <span aria-hidden="true"> · </span> : null}
          <span>{cvLine}</span>
        </span>
      </span>
    </button>
  );
}

function AppsBoardColumn({ locale, status, items, selectedId, visibleCount, onSelect, onShowMore }) {
  const t = text(locale);
  const shown = items.slice(0, visibleCount);
  const canMore = items.length > visibleCount;
  return (
    <section className={`apps-e-col apps-e-col-${status}`} aria-label={colStatusLabel(t, status)}>
      <header className="apps-e-col-head">
        <span className={statusClass(status)}>{colStatusLabel(t, status)}</span>
        <span className="apps-e-col-count">{items.length}</span>
      </header>
      <div className="apps-e-col-scroll">
        {items.length === 0 ? <p className="apps-e-col-empty">{t.applicationsColumnEmpty}</p> : null}
        {shown.map((item) => (
          <AppsBoardCard
            key={item.id}
            locale={locale}
            item={item}
            selected={item.id === selectedId}
            onSelect={onSelect}
          />
        ))}
        {canMore ? (
          <button type="button" className="btn small apps-e-more" onClick={onShowMore}>
            {t.applicationsShowMore}
          </button>
        ) : null}
      </div>
    </section>
  );
}

function AppsDetail({ locale, item, busy, onWithdraw, onBack }) {
  const t = text(locale);
  if (!item) {
    return (
      <div className="apps-e-detail apps-e-detail-empty">
        <p>{t.applicationsSelectHint}</p>
      </div>
    );
  }

  const jobHref = item.job_id ? hrefFor(locale, { jobId: item.job_id }) : null;
  const when = calendarDate(item.created_at, locale);

  return (
    <article className="apps-e-detail">
      {onBack ? (
        <button type="button" className="apps-e-detail-back text-btn" onClick={onBack}>
          ← {t.applicationsBackToList}
        </button>
      ) : null}
      <header className="apps-e-detail-head">
        <span className="apps-e-avatar apps-e-avatar-lg" aria-hidden="true">
          {titleInitial(item.job_title)}
        </span>
        <div className="apps-e-detail-head-text">
          <h2 className="apps-e-detail-title">
            {jobHref ? <a href={jobHref}>{item.job_title || "—"}</a> : item.job_title || "—"}
          </h2>
          <div className="apps-e-detail-meta">
            <span className={statusClass(item.status)}>{colStatusLabel(t, normalizeStatus(item.status))}</span>
            {when ? (
              <time dateTime={item.created_at}>
                {when}
              </time>
            ) : null}
          </div>
        </div>
      </header>

      <ApplicationTimeline locale={locale} t={t} item={item} />

      <dl className="apps-e-facts">
        <div>
          <dt>CV</dt>
          <dd>
            {item.has_cv ? (
              <a href={`/api/auth/applications/${item.id}/cv`}>{item.cv_name || t.downloadCv}</a>
            ) : (
              t.noCv
            )}
          </dd>
        </div>
        <div>
          <dt>{t.applicationsJobLabel}</dt>
          <dd>{item.job_id ? `#${item.job_id}` : "—"}</dd>
        </div>
      </dl>

      <div className="apps-e-detail-actions">
        {jobHref ? (
          <a className="btn small primary" href={jobHref}>
            {t.savedJobsViewJob}
          </a>
        ) : null}
        <button
          type="button"
          className="btn small red"
          disabled={busy === item.id}
          onClick={() => onWithdraw(item)}
        >
          {t.appWithdraw}
        </button>
      </div>
    </article>
  );
}

export function ApplicationsBoard({ locale, items, onChanged }) {
  const t = text(locale);
  const rows = Array.isArray(items) ? items : [];
  const groups = useMemo(() => groupByStatus(rows), [rows]);
  const [selectedId, setSelectedId] = useState(() => rows[0]?.id ?? null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [mobileTab, setMobileTab] = useState("submitted");
  const [visible, setVisible] = useState(() => ({
    submitted: COL_PAGE,
    seen: COL_PAGE,
    rejected: COL_PAGE,
  }));
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!rows.length) {
      setSelectedId(null);
      setMobileDetail(false);
      return;
    }
    if (!rows.some((item) => item.id === selectedId)) {
      setSelectedId(rows[0].id);
    }
  }, [rows, selectedId]);

  useEffect(() => {
    setVisible({ submitted: COL_PAGE, seen: COL_PAGE, rejected: COL_PAGE });
  }, [rows.length]);

  const selected = rows.find((item) => item.id === selectedId) || null;

  function selectItem(id) {
    setSelectedId(id);
    setMobileDetail(true);
  }

  function backToList() {
    setMobileDetail(false);
  }

  function showMore(status) {
    setVisible((prev) => ({ ...prev, [status]: (prev[status] || COL_PAGE) + COL_PAGE }));
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
    setMobileDetail(false);
    if (onChanged) onChanged();
  }

  if (rows.length === 0) {
    return (
      <div className="apps-e-empty">
        {error ? <p className="note apps-e-banner">{error}</p> : null}
        {note ? <p className="note apps-e-banner">{note}</p> : null}
        <div className="apps-e-empty-msg">
          <p>{t.applicationsEmpty}</p>
        </div>
      </div>
    );
  }

  const mobileItems = groups[mobileTab] || [];

  return (
    <div className={["apps-e", mobileDetail ? "is-mobile-detail" : ""].filter(Boolean).join(" ")}>
      {error ? <p className="note apps-e-banner">{error}</p> : null}
      {note ? <p className="note apps-e-banner">{note}</p> : null}

      <div className="apps-e-board-pane">
        <div className="apps-e-tabs" role="tablist" aria-label={t.myApplications}>
          {STATUSES.map((status) => (
            <button
              key={status}
              type="button"
              role="tab"
              aria-selected={mobileTab === status}
              className={["apps-e-tab", mobileTab === status ? "is-active" : ""].filter(Boolean).join(" ")}
              onClick={() => setMobileTab(status)}
            >
              <span className="apps-e-tab-label">{colStatusLabel(t, status)}</span>
              <span className="apps-e-tab-count">{groups[status].length}</span>
            </button>
          ))}
        </div>

        <div className="apps-e-board">
          {STATUSES.map((status) => (
            <AppsBoardColumn
              key={status}
              locale={locale}
              status={status}
              items={groups[status]}
              selectedId={selectedId}
              visibleCount={visible[status] || COL_PAGE}
              onSelect={selectItem}
              onShowMore={() => showMore(status)}
            />
          ))}
        </div>

        <div className="apps-e-mobile-list">
          <div className="apps-e-col-scroll apps-e-mobile-scroll">
            {mobileItems.length === 0 ? (
              <p className="apps-e-col-empty">{t.applicationsColumnEmpty}</p>
            ) : (
              mobileItems.slice(0, visible[mobileTab] || COL_PAGE).map((item) => (
                <AppsBoardCard
                  key={item.id}
                  locale={locale}
                  item={item}
                  selected={item.id === selectedId}
                  onSelect={selectItem}
                />
              ))
            )}
            {mobileItems.length > (visible[mobileTab] || COL_PAGE) ? (
              <button type="button" className="btn small apps-e-more" onClick={() => showMore(mobileTab)}>
                {t.applicationsShowMore}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="apps-e-detail-pane">
        <AppsDetail
          locale={locale}
          item={selected}
          busy={busy}
          onWithdraw={withdraw}
          onBack={mobileDetail ? backToList : null}
        />
      </div>
    </div>
  );
}
