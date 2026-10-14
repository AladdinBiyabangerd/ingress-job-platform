"use client";

import { useEffect, useMemo, useState } from "react";
import {
  adminListFilterActive,
  emptyAdminListFilter,
  filterAdminList,
} from "../lib/admin-list-filter";
import { text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import {
  forgetTidyJob,
  pollTidyJob,
  progressFromTidy,
  rememberTidyJob,
  storedTidyJob,
} from "../lib/job-tidy-run";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  adminCancelJobTidy,
  adminStartJobTidy,
  refreshJobTidy,
} from "../lib/server/refresh";
import { AdminListFilterBar } from "./admin-list-filter-bar";
import { AdminRecheckProgress } from "./admin-recheck-progress";
import { Pager } from "./pager";

function dateCell(value, locale, fallback) {
  const label = calendarDate(value, locale);
  if (!label) return fallback;
  return <time dateTime={String(value).slice(0, 10)}>{label}</time>;
}

export function AdminJobTidy({ locale }) {
  const t = text(locale);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [tidyProgress, setTidyProgress] = useState(null);
  const [tidyJobId, setTidyJobId] = useState("");
  const [tidyStopping, setTidyStopping] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const [listFilter, setListFilter] = useState(emptyAdminListFilter);

  const viewItems = useMemo(() => filterAdminList(items, listFilter), [items, listFilter]);
  const { currentPage, pageSize, total, totalPages, pageItems, goToPage, resetPage } = usePagination(
    viewItems,
    LIST_PAGE_SIZE,
  );

  function updateListFilter(next) {
    setListFilter(next);
    resetPage();
  }

  function load() {
    return refreshJobTidy()
      .then((list) => {
        setItems(list);
        setError("");
      })
      .catch(() => setError(t.loadError));
  }

  useEffect(() => {
    let alive = true;
    refreshJobTidy()
      .then((list) => {
        if (alive) {
          setItems(list);
          setError("");
        }
      })
      .catch(() => {
        if (alive) setError(t.loadError);
      });
    return () => {
      alive = false;
    };
  }, [t.loadError]);

  useEffect(() => {
    const jobId = storedTidyJob();
    if (!jobId) return undefined;
    let alive = true;
    setBusy(true);
    setTidyJobId(jobId);
    setTidyStopping(false);
    pollTidyJob(jobId, {
      isActive: () => alive,
      onProgress: (p) => {
        if (alive) setTidyProgress(p);
      },
    })
      .then(async ({ ok, last, cancelled }) => {
        if (!alive || cancelled) return;
        forgetTidyJob();
        setTidyProgress(null);
        setTidyJobId("");
        setTidyStopping(false);
        if (!ok) {
          setError(t.adminError);
          return;
        }
        if (last.status === "failed") {
          setError(last.error || t.adminError);
        } else if (last.status === "cancelled") {
          setNote(
            t.adminTidyStoppedNote(
              Number(last.saved) || 0,
              Number(last.failed) || 0,
              Number(last.skipped) || 0,
            ),
          );
        } else {
          setNote(
            t.adminTidyNote(
              Number(last.saved) || 0,
              Number(last.failed) || 0,
              Number(last.skipped) || 0,
            ),
          );
        }
        await load();
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resume once on mount
  }, []);

  async function stopTidy() {
    if (!tidyJobId || tidyStopping) return;
    setTidyStopping(true);
    await adminCancelJobTidy(tidyJobId);
  }

  async function startTidy(ids) {
    if (!ids.length) {
      setError(t.adminTidyNone);
      return;
    }
    setBusy(true);
    setError("");
    setNote("");
    setTidyStopping(false);
    const started = await adminStartJobTidy(ids);
    if (!started.ok || !started.data?.job_id) {
      setBusy(false);
      setError(t.adminError);
      return;
    }
    const jobId = String(started.data.job_id);
    rememberTidyJob(jobId);
    setTidyJobId(jobId);
    setTidyProgress(progressFromTidy(started.data, ids.length));
    const { ok, last } = await pollTidyJob(jobId, {
      fallbackTotal: ids.length,
      onProgress: setTidyProgress,
    });
    forgetTidyJob();
    setTidyProgress(null);
    setTidyJobId("");
    setTidyStopping(false);
    setBusy(false);
    if (!ok) {
      setError(t.adminError);
      return;
    }
    if (last.status === "failed") {
      setError(last.error || t.adminError);
    } else if (last.status === "cancelled") {
      setNote(
        t.adminTidyStoppedNote(
          Number(last.saved) || 0,
          Number(last.failed) || 0,
          Number(last.skipped) || 0,
        ),
      );
    } else {
      setNote(
        t.adminTidyNote(
          Number(last.saved) || 0,
          Number(last.failed) || 0,
          Number(last.skipped) || 0,
        ),
      );
    }
    setSelected(new Set());
    await load();
  }

  function toggleSelected(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const allPageSelected =
    pageItems.length > 0 && pageItems.every((item) => selected.has(item.id));
  const somePageSelected = pageItems.some((item) => selected.has(item.id));
  const selectedIds = [...selected].filter((id) => items.some((item) => item.id === id));

  return (
    <section className="h2-employer-queue">
      <div className="h2-panel h2-employer-list">
        {error ? <p className="note">{error}</p> : null}
        {note ? <p className="note">{note}</p> : null}
        <AdminRecheckProgress
          t={t}
          progress={tidyProgress}
          onStop={stopTidy}
          stopping={tidyStopping}
          formatProgress={t.adminTidyProgress}
        />
        {items.length === 0 ? <p className="empty-line">{t.adminTidyEmpty}</p> : null}
        {items.length ? (
          <div className="admin-mod-table-wrap">
            <AdminListFilterBar
              t={t}
              filter={listFilter}
              onChange={updateListFilter}
              disabled={busy}
            />
            {adminListFilterActive(listFilter) && viewItems.length === 0 ? (
              <p className="empty-line">{t.adminListFilterEmpty}</p>
            ) : null}
            <div className="admin-mod-threshold">
              <button
                type="button"
                className="btn small primary"
                disabled={busy || !items.length}
                onClick={() => startTidy(items.map((item) => item.id))}
              >
                {t.adminTidyStartAll}
              </button>
              <button
                type="button"
                className="btn small"
                disabled={busy || !selectedIds.length}
                onClick={() => startTidy(selectedIds)}
              >
                {t.adminTidyStartSelected}
              </button>
            </div>
            {selected.size ? (
              <div className="admin-mod-bulk">
                <span className="admin-mod-bulk-count">{t.adminSelectedCount(selected.size)}</span>
                <button
                  type="button"
                  className="btn small"
                  disabled={busy}
                  onClick={() => setSelected(new Set())}
                >
                  {t.adminClearSelection}
                </button>
              </div>
            ) : null}
            <table className="admin-mod-table">
              <thead>
                <tr>
                  <th scope="col" className="admin-mod-check-col">
                    <input
                      type="checkbox"
                      checked={allPageSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = !allPageSelected && somePageSelected;
                      }}
                      disabled={busy || !pageItems.length}
                      onChange={() => {
                        setSelected((prev) => {
                          const next = new Set(prev);
                          if (allPageSelected) {
                            for (const item of pageItems) next.delete(item.id);
                          } else {
                            for (const item of pageItems) next.add(item.id);
                          }
                          return next;
                        });
                      }}
                      aria-label={t.adminTidySelectPage}
                    />
                  </th>
                  <th scope="col">{t.adminColIngested}</th>
                  <th scope="col">{t.adminColTitle}</th>
                  <th scope="col">{t.adminColSource}</th>
                  <th scope="col">{t.adminTidyColChars}</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => (
                  <tr key={item.id}>
                    <td className="admin-mod-check-col">
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        disabled={busy}
                        onChange={() => toggleSelected(item.id)}
                        aria-label={item.title || String(item.id)}
                      />
                    </td>
                    <td>{dateCell(item.created_at, locale, t.adminDateUnknown)}</td>
                    <td>
                      <div className="admin-mod-title">{item.title || "—"}</div>
                      <div className="admin-mod-sub">
                        {[item.company, item.city].filter(Boolean).join(" · ") || "—"}
                      </div>
                    </td>
                    <td>{item.source_name || "—"}</td>
                    <td>{Number(item.text_chars) || 0}</td>
                  </tr>
                ))}
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
