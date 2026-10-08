import { LinkPager } from "./companies";
import { PageHeader } from "./page-header";
import { Shell } from "./shell";
import { hrefFor, text } from "../lib/copy";

/** Cap absurd ratios so a cold-start prior never paints millions %. */
const MAX_DISPLAY_GROWTH = 5;
export const TRENDS_PAGE_SIZE = 10;
export const TRENDS_WINDOWS = [7, 14, 28, 56];
export const DEFAULT_TRENDS_WINDOW = 7;
export const MIN_TRENDS_WINDOW = 1;
export const MAX_TRENDS_WINDOW = 56;

export function clampTrendsWindow(value) {
  const n = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(n)) return DEFAULT_TRENDS_WINDOW;
  return Math.min(MAX_TRENDS_WINDOW, Math.max(MIN_TRENDS_WINDOW, n));
}

function listHref(locale, { page, windowDays } = {}) {
  const params = new URLSearchParams();
  if (windowDays && windowDays !== DEFAULT_TRENDS_WINDOW) {
    params.set("days", String(windowDays));
  }
  if (page && page > 1) params.set("page", String(page));
  const query = params.toString();
  const base = hrefFor(locale, { mode: "trends" });
  return query ? `${base}?${query}` : base;
}

function pct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

function growthParts(growth) {
  if (typeof growth !== "number" || Number.isNaN(growth)) return null;
  if (Math.abs(growth) > MAX_DISPLAY_GROWTH) return null;
  const value = pct(growth);
  if (value === null) return null;
  const sign = value > 0 ? "+" : "";
  return {
    value,
    label: `${sign}${value}%`,
    direction: value > 0 ? "up" : value < 0 ? "down" : "flat",
  };
}

function formatMoney(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.round(value).toLocaleString("en-US");
}

function oneSalaryParts(t, salary) {
  if (!salary || typeof salary !== "object") return null;
  const median = formatMoney(salary.median);
  const currency = String(salary.currency || "").trim();
  const n = typeof salary.n === "number" ? salary.n : 0;
  if (!median || !currency || n <= 0) return null;
  const low = formatMoney(salary.low);
  const high = formatMoney(salary.high);
  const range =
    low && high && low !== high && low !== median
      ? t.trendsSalaryRange(low, high, currency)
      : null;
  return {
    median: t.trendsSalaryMedian(median, currency),
    range,
    sample: t.trendsSalaryN(n),
    line: [t.trendsSalaryMedian(median, currency), range, t.trendsSalaryN(n)]
      .filter(Boolean)
      .join(" · "),
  };
}

function salaryGroups(t, item) {
  const list = Array.isArray(item?.salaries) && item.salaries.length
    ? item.salaries
    : item?.salary
      ? [item.salary]
      : [];
  return list.map((row) => oneSalaryParts(t, row)).filter(Boolean);
}

function companionsOf(item) {
  if (!Array.isArray(item?.often_with)) return [];
  return item.often_with
    .map((row) => {
      const name = String(row?.name || "").trim();
      const share = pct(row?.share);
      if (!name || share === null) return null;
      return { name, share };
    })
    .filter(Boolean);
}

function TrendCard({ t, locale, item, index }) {
  const share = pct(item.share);
  const growth = growthParts(item.growth_wow);
  const salaries = salaryGroups(t, item);
  const companions = companionsOf(item);
  const rank = String(index + 1).padStart(2, "0");
  const barWidth = share === null ? 0 : Math.max(4, Math.min(100, share));
  const meta = [
    typeof item.ad_count === "number" ? t.trendsAdsCount(item.ad_count) : null,
    ...salaries.map((row) => row.line),
  ].filter(Boolean);
  const href =
    item.skill_id != null
      ? hrefFor(locale, { mode: "trend", skillId: item.skill_id })
      : null;

  const body = (
    <div className="trends-card-top">
      <span className="trends-rank" aria-hidden="true">
        {rank}
      </span>
      <div className="trends-card-main">
        <div className="trends-card-title">
          <h2>{item.name}</h2>
          {growth ? (
            <span className={`trends-growth trends-growth-${growth.direction}`}>
              {growth.label}
            </span>
          ) : null}
          {share !== null ? <span className="trends-share-value">{share}%</span> : null}
        </div>

        {share !== null ? (
          <div
            className="trends-share-track"
            role="meter"
            aria-label={t.trendsShare}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={share}
          >
            <span className="trends-share-fill" style={{ width: `${barWidth}%` }} />
          </div>
        ) : null}

        {meta.length ? <p className="trends-meta-line">{meta.join(" · ")}</p> : null}

        {companions.length ? (
          <ul className="tech-chips trends-companion-chips" aria-label={t.trendsOftenWith}>
            {companions.map((row) => (
              <li key={row.name} className="tech-chip">
                {row.name}
                <span className="trends-companion-pct">{row.share}%</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );

  return (
    <li className="trends-card">
      {href ? (
        <a className="trends-card-link" href={href}>
          {body}
        </a>
      ) : (
        body
      )}
    </li>
  );
}

export function TrendsPage({ locale, data, error, page = 1, windowDays = DEFAULT_TRENDS_WINDOW }) {
  const t = text(locale);
  const window = clampTrendsWindow(windowDays);
  const allItems = Array.isArray(data?.items) ? data.items : [];
  const total = allItems.length;
  const pages = Math.max(1, Math.ceil(total / TRENDS_PAGE_SIZE));
  const currentPage = Math.min(pages, Math.max(1, Number(page) || 1));
  const offset = (currentPage - 1) * TRENDS_PAGE_SIZE;
  const items = allItems.slice(offset, offset + TRENDS_PAGE_SIZE);
  const disclaimer = data?.disclaimer || t.trendsDisclaimer;
  const asOf = data?.as_of ? t.trendsAsOf(data.as_of) : null;

  return (
    <Shell locale={locale} mode="trends">
      <nav className="breadcrumbs" aria-label={t.breadcrumbs}>
        <ol>
          <li>
            <a href={hrefFor(locale)}>{t.breadcrumbHome}</a>
          </li>
          <li>
            <span aria-current="page">{t.trendsTitle}</span>
          </li>
        </ol>
      </nav>
      <main className="trends-page">
        <PageHeader
          className="trends-hero"
          title={t.trendsTitle}
          count={total ? String(total) : null}
          lede={t.trendsLede}
        >
          <div className="trends-tools">
            <div className="trends-presets" role="group" aria-label={t.trendsWindowLabel}>
              {TRENDS_WINDOWS.map((days) => (
                <a
                  key={days}
                  className={`trends-preset${window === days ? " on" : ""}`}
                  href={listHref(locale, { windowDays: days })}
                  aria-current={window === days ? "true" : undefined}
                >
                  {days}
                </a>
              ))}
            </div>
            <form
              className="trends-custom"
              method="get"
              action={hrefFor(locale, { mode: "trends" })}
            >
              <label className="trends-custom-field" htmlFor="trends-window-days">
                <span className="visually-hidden">{t.trendsWindowLabel}</span>
                <span className="trends-custom-prefix" aria-hidden="true">
                  {t.trendsWindowPrefix}
                </span>
                <input
                  id="trends-window-days"
                  type="number"
                  name="days"
                  min={MIN_TRENDS_WINDOW}
                  max={MAX_TRENDS_WINDOW}
                  step="1"
                  defaultValue={window}
                  inputMode="numeric"
                  required
                />
                <span className="trends-custom-unit">{t.trendsWindowUnit}</span>
              </label>
              <button type="submit" className="btn primary trends-custom-submit">
                {t.trendsWindowApply}
              </button>
            </form>
          </div>
        </PageHeader>
        <div className="trends-meta">
          <p className="hint trends-disclaimer">{disclaimer}</p>
          {asOf ? <p className="hint trends-window">{asOf}</p> : null}
        </div>

        {error || !total ? (
          <div className="trends-empty">
            <p className="note">{t.trendsEmpty}</p>
          </div>
        ) : (
          <>
            <ol className="trends-list" start={offset + 1}>
              {items.map((item, index) => (
                <TrendCard
                  key={item.skill_id || item.name}
                  t={t}
                  locale={locale}
                  item={item}
                  index={offset + index}
                />
              ))}
            </ol>
            <LinkPager
              locale={locale}
              page={currentPage}
              pages={pages}
              hrefOf={(next) => listHref(locale, { page: next, windowDays: window })}
            />
          </>
        )}
      </main>
    </Shell>
  );
}
