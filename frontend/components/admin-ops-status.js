"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { text } from "../lib/copy";
import { LIST_PAGE_SIZE, usePagination } from "../lib/pagination";
import { Pager } from "./pager";

const PERIODS = [
  ["1", "opsPeriod1"],
  ["7", "opsPeriod7"],
  ["30", "opsPeriod30"],
];

/** Same flow ids as admin AI tab — locale labels win over API AZ defaults. */
const AI_FLOW_COPY = [
  ["gateway", "adminAiGateway"],
  ["cv_fallback", "adminAiCv"],
  ["job_tidy", "adminAiTidy"],
  ["market_fit", "adminAiMarketFit"],
  ["embeddings", "adminAiEmbeddings"],
  ["rerank", "adminAiRerank"],
  ["llm_rerank", "adminAiLlmRerank"],
  ["match_why", "adminAiWhy"],
  ["role_coach", "adminAiRoleCoach"],
  ["learning_roadmap", "adminAiLearningRoadmap"],
  ["job_analyze", "adminAiJobAnalyze"],
  ["job_apply_draft", "adminAiJobApplyDraft"],
  ["job_tailored_cv", "adminAiJobTailoredCv"],
  ["digest_intro", "adminAiDigest"],
  ["engagement_copy", "adminAiEngagement"],
];

const AI_FLOW_LABEL_KEYS = Object.fromEntries(AI_FLOW_COPY);

function todayIso() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDaysIso(iso, delta) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + delta);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function StatusPill({ running, runningLabel, stoppedLabel }) {
  return (
    <span className={`ops-status-pill${running ? " is-running" : " is-stopped"}`}>
      {running ? runningLabel : stoppedLabel}
    </span>
  );
}

function KpiCard({ label, value, hint, hintOk }) {
  return (
    <div className="ops-kpi">
      <p className="ops-kpi-label">{label}</p>
      <p className="ops-kpi-value">{value}</p>
      {hint ? (
        <p className={`ops-kpi-hint${hintOk === false ? " is-warn" : hintOk === true ? " is-ok" : ""}`}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function AdminOpsStatus({ locale }) {
  const t = text(locale);
  const [period, setPeriod] = useState("7");
  const [days, setDays] = useState(7);
  const [dateFrom, setDateFrom] = useState(() => addDaysIso(todayIso(), -6));
  const [dateTo, setDateTo] = useState(() => todayIso());
  const [panel, setPanel] = useState("");
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (windowDays) => {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/auth/admin/ops-status?days=${windowDays}`, { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error("load");
      setPayload(data);
    } catch {
      setError(t.loadError);
      setPayload(null);
    } finally {
      setBusy(false);
    }
  }, [t.loadError]);

  useEffect(() => {
    load(days);
  }, [days, load]);

  function pickPeriod(next) {
    setPeriod(next);
    const n = Number(next);
    setDays(n);
    const to = todayIso();
    setDateTo(to);
    setDateFrom(n === 1 ? to : addDaysIso(to, -(n - 1)));
  }

  function applyCustom(event) {
    event.preventDefault();
    let from = dateFrom || todayIso();
    let to = dateTo || todayIso();
    if (from > to) [from, to] = [to, from];
    const span = Math.max(
      1,
      Math.min(90, Math.round((new Date(`${to}T12:00:00`) - new Date(`${from}T12:00:00`)) / 86400000) + 1),
    );
    const alignedTo = todayIso();
    const alignedFrom = addDaysIso(alignedTo, -(span - 1));
    setPeriod("custom");
    setDays(span);
    setDateFrom(alignedFrom);
    setDateTo(alignedTo);
  }

  const ai = payload?.ai || {};
  const crawl = payload?.crawl || {};
  const totals = crawl.totals || {};
  const sources = Array.isArray(crawl.sources) ? crawl.sources : [];
  const features = Array.isArray(ai.features) ? ai.features : [];
  const chatProviders = Array.isArray(ai.chat_providers) ? ai.chat_providers : [];
  const embedProviders = Array.isArray(ai.embed_providers) ? ai.embed_providers : [];
  const usageToday = Array.isArray(ai.usage_today) ? ai.usage_today : [];
  const rejects = Array.isArray(crawl.rejects_by_reason) ? crawl.rejects_by_reason : [];
  const rejectTotal = rejects.reduce((sum, row) => sum + (Number(row.count) || 0), 0);
  const li = crawl.linkedin_extension || {};
  const featStopped = features.filter((row) => row.status !== "running");
  const featRunning = features.filter((row) => row.status === "running");

  function featureLabel(row) {
    const key = AI_FLOW_LABEL_KEYS[row?.id];
    return (key && t[key]) || row?.label || row?.id || "—";
  }

  function providerModel(row) {
    if (Array.isArray(row?.models) && row.models.length) {
      return row.models.join(" → ");
    }
    return row?.model || "";
  }

  const {
    pageItems: sourcesPage,
    currentPage,
    totalPages,
    pageSize,
    total: sourcesTotal,
    goToPage,
  } = usePagination(sources, LIST_PAGE_SIZE);

  const dailyLimit = ai.daily_limit == null || ai.daily_limit === "" ? "—" : ai.daily_limit;

  const periodHint = useMemo(() => {
    if (period !== "custom") return null;
    return t.opsCustomRange(dateFrom, dateTo, days);
  }, [period, dateFrom, dateTo, days, t]);

  return (
    <div className="ops-status">
      <div className="ops-period">
        {PERIODS.map(([value, key]) => (
          <button
            key={value}
            type="button"
            className={`ops-chip${period === value ? " on" : ""}`}
            onClick={() => pickPeriod(value)}
            disabled={busy}
          >
            {t[key]}
          </button>
        ))}
        <span className="ops-period-sep" aria-hidden="true">
          |
        </span>
        <form className="ops-period-custom" onSubmit={applyCustom}>
          <label className="visually-hidden" htmlFor="ops-from">
            {t.opsFrom}
          </label>
          <input
            id="ops-from"
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <span className="ops-period-arrow" aria-hidden="true">
            →
          </span>
          <label className="visually-hidden" htmlFor="ops-to">
            {t.opsTo}
          </label>
          <input
            id="ops-to"
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
          <button type="submit" className="ops-chip on" disabled={busy}>
            {t.opsApply}
          </button>
        </form>
        <button
          type="button"
          className="ops-chip ops-chip-refresh"
          onClick={() => load(days)}
          disabled={busy}
        >
          {t.opsRefresh}
        </button>
        {periodHint ? <span className="ops-period-hint">{periodHint}</span> : null}
      </div>

      {error ? <p className="note ops-error">{error}</p> : null}

      {!error && payload ? (
        <>
          <div className="ops-kpi-grid">
            <KpiCard
              label={t.opsFetched}
              value={Number(totals.fetched) || 0}
              hint={t.opsFetchedHint}
            />
            <KpiCard
              label={t.opsKept}
              value={Number(totals.selected) || 0}
              hint={t.opsKeptNew(Number(totals.selected_new) || 0)}
            />
            <KpiCard
              label={t.opsLive}
              value={Number(totals.published_live) || 0}
              hint={t.opsLiveHint}
            />
            <KpiCard label={t.opsRejected} value={rejectTotal} hint={t.opsRejectedHint} />
            <KpiCard
              label={t.opsAiToday}
              value={
                <>
                  {Number(ai.daily_calls) || 0}
                  <span className="ops-kpi-limit"> / {dailyLimit}</span>
                </>
              }
              hint={ai.budget_ok ? t.opsBudgetOk : t.opsBudgetHit}
              hintOk={Boolean(ai.budget_ok)}
            />
          </div>

          <section className="ops-li">
            <div className="ops-li-head">
              <h2 className="ops-section-title">{t.opsLinkedIn}</h2>
              <p className="ops-section-hint">{t.opsLinkedInHint}</p>
            </div>
            <div className="ops-li-grid">
              <div>
                <p className="ops-kpi-label">{t.opsCreated}</p>
                <p className="ops-kpi-value ops-kpi-value-sm">{Number(li.created) || 0}</p>
                <p className="ops-kpi-hint">{t.opsCreatedHint}</p>
              </div>
              <div>
                <p className="ops-kpi-label">{t.opsLive}</p>
                <p className="ops-kpi-value ops-kpi-value-sm">{Number(li.published_live) || 0}</p>
                <p className="ops-kpi-hint">{t.opsLiLiveHint}</p>
              </div>
              <div>
                <p className="ops-kpi-label">{t.opsNotFit}</p>
                <p className="ops-kpi-value ops-kpi-value-sm">{Number(li.rejected) || 0}</p>
                <p className="ops-kpi-hint">{t.opsNotFitHint}</p>
              </div>
            </div>
          </section>

          <div className="ops-panels">
            <button
              type="button"
              className={`ops-panel-btn${panel === "sources" ? " on" : ""}`}
              onClick={() => setPanel(panel === "sources" ? "" : "sources")}
            >
              {t.opsSources}
              <span className="ops-panel-count">{sources.length}</span>
            </button>
            <button
              type="button"
              className={`ops-panel-btn${panel === "ai" ? " on" : ""}`}
              onClick={() => setPanel(panel === "ai" ? "" : "ai")}
            >
              {t.opsAiPanel}
              {featStopped.length ? (
                <span className="ops-panel-badge">{featStopped.length}</span>
              ) : null}
            </button>
            {panel ? (
              <button type="button" className="ops-hide" onClick={() => setPanel("")}>
                {t.opsHideDetails}
              </button>
            ) : null}
          </div>

          {panel === "sources" ? (
            <section className="ops-detail">
              <div className="ops-detail-head">
                <h2 className="ops-section-title">{t.opsSources}</h2>
                <p className="ops-section-hint">{t.opsSourcesHint}</p>
              </div>
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th scope="col">{t.opsColSource}</th>
                      <th scope="col">{t.opsColStatus}</th>
                      <th className="num" scope="col">
                        {t.opsFetched}
                      </th>
                      <th className="num" scope="col">
                        {t.opsKept}
                      </th>
                      <th className="num" scope="col">
                        {t.opsNew}
                      </th>
                      <th className="num" scope="col">
                        {t.opsLive}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sourcesPage.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="ops-empty">
                          {t.opsSourcesEmpty}
                        </td>
                      </tr>
                    ) : (
                      sourcesPage.map((row) => {
                        const running = row.status === "running";
                        return (
                          <tr key={row.name}>
                            <td>
                              <span className="ops-name">{row.name}</span>
                              {row.homepage ? (
                                <a
                                  className="ops-home"
                                  href={row.homepage}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {row.homepage}
                                </a>
                              ) : null}
                              {!running && row.reason ? (
                                <p className="ops-reason">{row.reason}</p>
                              ) : null}
                            </td>
                            <td>
                              <StatusPill
                                running={running}
                                runningLabel={t.opsActive}
                                stoppedLabel={t.opsStopped}
                              />
                            </td>
                            <td className="num">{Number(row.fetched) || 0}</td>
                            <td className="num">{Number(row.selected) || 0}</td>
                            <td className="num">{Number(row.selected_new) || 0}</td>
                            <td className="num ops-num-strong">{Number(row.published_live) || 0}</td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
              <Pager
                locale={locale}
                currentPage={currentPage}
                totalPages={totalPages}
                total={sourcesTotal}
                pageSize={pageSize}
                onPageChange={goToPage}
              />
            </section>
          ) : null}

          {panel === "ai" ? (
            <section className="ops-detail ops-ai-detail">
              <div>
                <h2 className="ops-section-title">{t.opsAiUsage}</h2>
                <p className="ops-section-hint">{t.opsAiUsageHint}</p>
                <div className="ops-table-wrap">
                  <table className="ops-table">
                    <thead>
                      <tr>
                        <th scope="col">{t.opsColPurpose}</th>
                        <th className="num" scope="col">
                          {t.opsColCalls}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageToday.length === 0 ? (
                        <tr>
                          <td colSpan={2} className="ops-empty">
                            {t.opsAiUsageEmpty}
                          </td>
                        </tr>
                      ) : (
                        usageToday.map((row) => (
                          <tr key={row.purpose || row.label}>
                            <td className="ops-name">{row.label || row.purpose || "—"}</td>
                            <td className="num ops-num-strong">{Number(row.calls) || 0}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h2 className="ops-section-title">{t.opsAiFlows}</h2>
                <p className="ops-section-hint">
                  {t.opsAiFlowSummary(featRunning.length, featStopped.length)}
                </p>
                <div className="ops-table-wrap">
                  <table className="ops-table">
                    <thead>
                      <tr>
                        <th scope="col">{t.opsColFlow}</th>
                        <th scope="col">{t.opsColStatus}</th>
                        <th scope="col">{t.opsColNote}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {features.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="ops-empty">
                            {t.opsAiEmpty}
                          </td>
                        </tr>
                      ) : (
                        features.map((row) => {
                          const running = row.status === "running";
                          return (
                            <tr key={row.id || row.label}>
                              <td className="ops-name">{featureLabel(row)}</td>
                              <td>
                                <StatusPill
                                  running={running}
                                  runningLabel={t.opsRunning}
                                  stoppedLabel={t.opsStopped}
                                />
                              </td>
                              <td className="ops-note-cell">{running ? "—" : row.reason || "—"}</td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="ops-providers">
                <div>
                  <h2 className="ops-section-title">{t.opsChatProviders}</h2>
                  <div className="ops-table-wrap">
                    <table className="ops-table">
                      <thead>
                        <tr>
                          <th scope="col">{t.opsColProvider}</th>
                          <th scope="col">{t.opsColStatus}</th>
                          <th scope="col">{t.opsColNote}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {chatProviders.length === 0 ? (
                          <tr>
                            <td colSpan={3} className="ops-empty">
                              {t.opsChatEmpty}
                            </td>
                          </tr>
                        ) : (
                          chatProviders.map((row) => {
                            const running = row.status === "running";
                            const model = providerModel(row);
                            return (
                              <tr key={`chat-${row.id || row.label}`}>
                                <td>
                                  <span className="ops-name">{row.label}</span>
                                  {model ? <span className="ops-model">{model}</span> : null}
                                </td>
                                <td>
                                  <StatusPill
                                    running={running}
                                    runningLabel={t.opsRunning}
                                    stoppedLabel={t.opsStopped}
                                  />
                                </td>
                                <td className="ops-note-cell">{row.reason || "—"}</td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div>
                  <h2 className="ops-section-title">{t.opsEmbedProviders}</h2>
                  <div className="ops-table-wrap">
                    <table className="ops-table">
                      <thead>
                        <tr>
                          <th scope="col">{t.opsColProvider}</th>
                          <th scope="col">{t.opsColStatus}</th>
                          <th scope="col">{t.opsColNote}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {embedProviders.length === 0 ? (
                          <tr>
                            <td colSpan={3} className="ops-empty">
                              {t.opsEmbedEmpty}
                            </td>
                          </tr>
                        ) : (
                          embedProviders.map((row) => {
                            const running = row.status === "running";
                            const model = providerModel(row);
                            return (
                              <tr key={`embed-${row.id || row.label}`}>
                                <td>
                                  <span className="ops-name">{row.label}</span>
                                  {model ? <span className="ops-model">{model}</span> : null}
                                </td>
                                <td>
                                  <StatusPill
                                    running={running}
                                    runningLabel={t.opsRunning}
                                    stoppedLabel={t.opsStopped}
                                  />
                                </td>
                                <td className="ops-note-cell">{row.reason || "—"}</td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </section>
          ) : null}
        </>
      ) : null}

      {!error && !payload && busy ? <p className="hint">{t.opsLoading}</p> : null}
    </div>
  );
}
