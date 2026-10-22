"use client";

import { useEffect, useMemo, useState } from "react";
import {
  adminListFilterActive,
  emptyAdminListFilter,
  filterAdminList,
} from "../lib/admin-list-filter";
import { text } from "../lib/copy";
import { calendarDate } from "../lib/dates";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import {
  forgetRecheckJob,
  pollRecheckJob,
  progressFromRecheck,
  rememberRecheckJob,
  storedRecheckJob,
} from "../lib/recheck-market-fit";
import {
  adminCancelRecheckMarketFit,
  adminClearCrawlRejects,
  adminPublishCrawlRejectsThreshold,
  adminStartRecheckMarketFit,
  refreshCrawlRejects,
} from "../lib/server/refresh";
import { AdminListFilterBar } from "./admin-list-filter-bar";
import { AdminRecheckProgress } from "./admin-recheck-progress";
import { Pager } from "./pager";
import tableStyles from "./admin-mod-table.module.css";

const SCOPE = "crawl_rejects";

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

function jobScore(item, score) {
  const raw = score === "rule" ? item.rule_confidence : item.ai_confidence;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function thresholdMatchJobIds(items, score, op, threshold) {
  const cut = Number(threshold);
  if (!Number.isFinite(cut)) return [];
  const ids = [];
  const seen = new Set();
  for (const item of items) {
    if (!item.job_id) continue;
    const value = jobScore(item, score);
    if (value == null) continue;
    const ok = op === "lte" ? value <= cut : value >= cut;
    if (!ok || seen.has(item.job_id)) continue;
    seen.add(item.job_id);
    ids.push(item.job_id);
  }
  return ids;
}

function missingAiScoreIds(items) {
  return items
    .filter((item) => item.job_id && jobScore(item, "ai") == null)
    .map((item) => item.job_id)
    .filter((id, i, arr) => arr.indexOf(id) === i)
    .sort((a, b) => a - b);
}

function dateCell(value, locale, fallback) {
  const label = calendarDate(value, locale);
  if (!label) return fallback;
  return <time dateTime={String(value).slice(0, 10)}>{label}</time>;
}

function clipLabel(text, max = 72) {
  const s = String(text || "").trim();
  if (!s) return "";
  if (s.length <= max) return s;
  return `${s.slice(0, Math.max(1, max - 1))}…`;
}

function hostFromUrl(url) {
  try {
    const host = new URL(url).hostname || "";
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function titleCell(item) {
  const title = String(item.title || "").trim();
  if (title) return clipLabel(title, 80);
  const url = String(item.source_url || "").trim();
  if (!url) return "—";
  try {
    const u = new URL(url);
    const host = u.hostname.startsWith("www.") ? u.hostname.slice(4) : u.hostname;
    const path = u.pathname.length > 1 ? u.pathname : "";
    return clipLabel(`${host}${path}`, 64);
  } catch {
    return clipLabel(url, 64);
  }
}

function sourceLabel(item, fallback) {
  const name = String(item.source_name || "").trim();
  if (name) return name;
  const host = hostFromUrl(item.source_url || "");
  return host || fallback;
}

export function AdminCrawlRejects({ locale }) {
  const t = text(locale);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [scoreKind, setScoreKind] = useState("ai");
  const [scoreOp, setScoreOp] = useState("gte");
  const [scoreThreshold, setScoreThreshold] = useState("70");
  const [recheckProgress, setRecheckProgress] = useState(null);
  const [recheckJobId, setRecheckJobId] = useState("");
  const [recheckStopping, setRecheckStopping] = useState(false);
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
    return refreshCrawlRejects()
      .then((list) => {
        setItems(list);
        setError("");
      })
      .catch(() => setError(t.loadError));
  }

  useEffect(() => {
    let alive = true;
    refreshCrawlRejects()
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
    const jobId = storedRecheckJob(SCOPE);
    if (!jobId) return undefined;
    let alive = true;
    setBusy(true);
    setRecheckJobId(jobId);
    setRecheckStopping(false);
    pollRecheckJob(jobId, {
      isActive: () => alive,
      onProgress: (p) => {
        if (alive) setRecheckProgress(p);
      },
      onStatus: (status) => {
        if (alive && status === "cancelling") setRecheckStopping(true);
      },
    })
      .then(async ({ ok, last, cancelled }) => {
        if (!alive || cancelled) return;
        forgetRecheckJob(SCOPE);
        setRecheckProgress(null);
        setRecheckJobId("");
        setRecheckStopping(false);
        if (!ok) {
          setError(t.adminError);
          return;
        }
        if (last.status === "failed") {
          setError(last.error || t.adminError);
        } else if (last.status === "cancelled") {
          setNote(
            t.adminRecheckStoppedNote(
              Number(last.checked) || 0,
              Number(last.rejected) || 0,
              Number(last.failed) || 0,
            ),
          );
        } else {
          setNote(
            t.adminRecheckNote(
              Number(last.checked) || 0,
              Number(last.rejected) || 0,
              Number(last.failed) || 0,
            ),
          );
        }
        await load();
      })
      .finally(() => {
        if (alive) {
          setBusy(false);
          setRecheckJobId("");
          setRecheckStopping(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- resume once on mount
  }, []);

  async function publishByThreshold({ quick }) {
    const ids = thresholdMatchJobIds(items, scoreKind, scoreOp, scoreThreshold);
    if (!ids.length) {
      setNote("");
      setError(t.crawlRejectsThresholdNone);
      return;
    }
    if (!quick && !window.confirm(t.adminThresholdConfirm(ids.length))) return;
    setBusy(true);
    setError("");
    setNote("");
    const res = await adminPublishCrawlRejectsThreshold({
      score: scoreKind,
      op: scoreOp,
      threshold: scoreThreshold,
    });
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(t.crawlRejectsPublishedNote(Number(res.data?.published) || 0));
    setSelected(new Set());
    await load();
  }

  async function stopRecheck() {
    if (!recheckJobId || recheckStopping) return;
    setRecheckStopping(true);
    const res = await adminCancelRecheckMarketFit(recheckJobId);
    if (!res.ok) setRecheckStopping(false);
  }

  async function recheckMissingAi() {
    const ids = missingAiScoreIds(items);
    if (!ids.length) {
      setNote("");
      setError(t.crawlRejectsRecheckNone);
      return;
    }
    setBusy(true);
    setError("");
    setNote("");
    setRecheckStopping(false);
    setRecheckProgress({ total: ids.length, done: 0, remaining: ids.length });
    const started = await adminStartRecheckMarketFit(ids, { scope: SCOPE });
    if (!started.ok || !started.data?.job_id) {
      setBusy(false);
      setRecheckProgress(null);
      setError(t.adminError);
      return;
    }
    const jobId = started.data.job_id;
    setRecheckJobId(jobId);
    rememberRecheckJob(SCOPE, jobId);
    const { ok, last } = await pollRecheckJob(jobId, {
      fallbackTotal: ids.length,
      onProgress: setRecheckProgress,
      onStatus: (status) => {
        if (status === "cancelling") setRecheckStopping(true);
      },
    });
    forgetRecheckJob(SCOPE);
    setRecheckProgress(null);
    setBusy(false);
    setRecheckJobId("");
    setRecheckStopping(false);
    if (!ok) {
      setError(t.adminError);
      return;
    }
    if (last.status === "failed") {
      setError(last.error || t.adminError);
    } else if (last.status === "cancelled") {
      setNote(
        t.adminRecheckStoppedNote(
          Number(last.checked) || 0,
          Number(last.rejected) || 0,
          Number(last.failed) || 0,
        ),
      );
    } else {
      setNote(
        t.adminRecheckNote(
          Number(last.checked) || 0,
          Number(last.rejected) || 0,
          Number(last.failed) || 0,
        ),
      );
    }
    await load();
  }

  async function clearSelected() {
    const urls = [...selected];
    if (!urls.length) return;
    if (!window.confirm(t.crawlRejectsClearConfirm(urls.length))) return;
    setBusy(true);
    setError("");
    setNote("");
    const res = await adminClearCrawlRejects(urls);
    setBusy(false);
    if (!res.ok) {
      setError(t.adminError);
      return;
    }
    setNote(t.crawlRejectsClearedNote(Number(res.data?.cleared) || 0));
    setSelected(new Set());
    await load();
  }

  function toggleSelected(url) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return next;
    });
  }

  const allPageSelected =
    pageItems.length > 0 && pageItems.every((item) => selected.has(item.source_url));
  const somePageSelected = pageItems.some((item) => selected.has(item.source_url));

  return (
    <section className="h2-employer-queue">
      <div className="h2-panel h2-employer-list">
        {error ? <p className="note">{error}</p> : null}
        {note ? <p className="note">{note}</p> : null}
        <AdminRecheckProgress
          t={t}
          progress={recheckProgress}
          onStop={stopRecheck}
          stopping={recheckStopping}
        />
        {items.length === 0 ? <p className="empty-line">{t.crawlRejectsEmpty}</p> : null}
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
            <div className="admin-mod-threshold" title={t.crawlRejectsThresholdHintTitle}>
              <span className="admin-mod-filter-label">{t.crawlRejectsThresholdHint}</span>
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
                onClick={() => publishByThreshold({ quick: false })}
              >
                {t.adminThresholdPublish}
              </button>
              <button
                type="button"
                className="btn small"
                disabled={busy}
                onClick={() => publishByThreshold({ quick: true })}
              >
                {t.adminThresholdPublishQuick}
              </button>
              <button type="button" className="btn small" disabled={busy} onClick={recheckMissingAi}>
                {t.adminThresholdRecheck}
              </button>
            </div>
            {selected.size ? (
              <div className="admin-mod-bulk">
                <span className="admin-mod-bulk-count">{t.crawlRejectsSelectedCount(selected.size)}</span>
                <button type="button" className="btn small" disabled={busy} onClick={clearSelected}>
                  {t.crawlRejectsClear}
                </button>
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
                  <th className="admin-mod-check" scope="col">
                    <label className="inline admin-select">
                      <input
                        type="checkbox"
                        checked={allPageSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = somePageSelected && !allPageSelected;
                        }}
                        onChange={() => {
                          setSelected((prev) => {
                            const next = new Set(prev);
                            if (allPageSelected) {
                              for (const item of pageItems) next.delete(item.source_url);
                            } else {
                              for (const item of pageItems) next.add(item.source_url);
                            }
                            return next;
                          });
                        }}
                        aria-label={t.crawlRejectsSelectPage}
                      />
                    </label>
                  </th>
                  <th className="admin-mod-date" scope="col">
                    {t.adminColIngested}
                  </th>
                  <th scope="col">{t.adminColTitle}</th>
                  <th className={`admin-mod-pct-col ${tableStyles.pctHead}`} scope="col" title={t.adminColRulePctTitle}>
                    {t.adminColRulePct}
                  </th>
                  <th className={`admin-mod-pct-col ${tableStyles.pctHead}`} scope="col" title={t.adminColAiPctTitle}>
                    {t.adminColAiPct}
                  </th>
                  <th className="admin-mod-source" scope="col">
                    {t.adminColSource}
                  </th>
                  <th scope="col">{t.crawlRejectsColReason}</th>
                </tr>
              </thead>
              <tbody>
                {pageItems.map((item) => {
                  const url = item.source_url;
                  const linked = Boolean(item.job_id);
                  const name = sourceLabel(item, t.adminColSource);
                  return (
                    <tr key={url} className={!linked ? "is-muted" : undefined}>
                      <td className="admin-mod-check">
                        <label className="inline admin-select">
                          <input
                            type="checkbox"
                            checked={selected.has(url)}
                            onChange={() => toggleSelected(url)}
                          />
                        </label>
                      </td>
                      <td className="admin-mod-date">
                        {dateCell(item.decided_at, locale, t.adminDateUnknown)}
                      </td>
                      <td className="admin-mod-title">
                        <div className="admin-mod-title-row">
                          <span className="admin-mod-name" title={url || titleCell(item)}>
                            {titleCell(item)}
                          </span>
                          {item.via_ai ? (
                            <span className="source-pill" title="AI">
                              AI
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="admin-mod-pct-col">
                        {linked ? confidenceCell(item.rule_confidence, "") : (
                          <span className="admin-mod-pct-empty" title={t.crawlRejectsUrlOnly}>
                            —
                          </span>
                        )}
                      </td>
                      <td className="admin-mod-pct-col">
                        {linked ? (
                          confidenceCell(item.ai_confidence, item.market_fit_reason)
                        ) : (
                          <span className="admin-mod-pct-empty" title={t.crawlRejectsUrlOnly}>
                            —
                          </span>
                        )}
                      </td>
                      <td className="admin-mod-source">
                        {url ? (
                          <a
                            className="admin-mod-source-link"
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={url}
                          >
                            {name}
                          </a>
                        ) : (
                          <span className="admin-mod-source-empty">{t.adminDateUnknown}</span>
                        )}
                      </td>
                      <td className="admin-mod-reason" title={item.reason || ""}>
                        {item.reason || t.adminDateUnknown}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <Pager
              locale={locale}
              currentPage={currentPage}
              totalPages={totalPages}
              total={total}
              pageSize={pageSize}
              onPageChange={goToPage}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
