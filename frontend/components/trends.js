import { LinkPager } from "./companies";
import { Shell } from "./shell";
import { SkillIcon } from "./skill-icon";
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
    low && high && low !== high && low !== median ? t.trendsSalaryRange(low, high, currency) : null;
  return {
    median: t.trendsSalaryMedian(median, currency),
    range,
    sample: t.trendsSalaryN(n),
    line: [t.trendsSalaryMedian(median, currency), range, t.trendsSalaryN(n)].filter(Boolean).join(" · "),
  };
}

function salaryGroups(t, item) {
  const list =
    Array.isArray(item?.salaries) && item.salaries.length
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

function skillHref(locale, item) {
  return item?.skill_id != null ? hrefFor(locale, { mode: "trend", skillId: item.skill_id }) : null;
}

function rowTeaser(t, item, growth) {
  if (growth?.direction === "up") return t.trendsPulseRowRising(growth.label);
  if (growth?.direction === "down") return t.trendsPulseRowFalling(growth.label);
  return t.trendsPulseRowSteady;
}

/** Build up to 3 signal cards from live ranking data — no invented stats. */
function buildRisingSignals(t, locale, allItems) {
  const signals = [];
  const used = new Set();
  const mark = (item) => {
    const key = item?.skill_id ?? item?.name;
    if (key == null || used.has(key)) return false;
    used.add(key);
    return true;
  };

  const rankedByGrowth = allItems
    .slice(1)
    .map((item) => ({ item, growth: growthParts(item.growth_wow) }))
    .filter((row) => row.growth?.direction === "up")
    .sort((a, b) => b.growth.value - a.growth.value);

  const rising = rankedByGrowth[0];
  if (rising && mark(rising.item)) {
    const share = pct(rising.item.share);
    const ads = typeof rising.item.ad_count === "number" ? rising.item.ad_count : null;
    signals.push({
      key: `rise-${rising.item.skill_id || rising.item.name}`,
      label: t.trendsPulseSignalRising,
      title: share != null ? `${rising.item.name} · ${share}%` : rising.item.name,
      body:
        ads != null
          ? t.trendsPulseSignalRisingBody(ads, rising.growth.label)
          : rising.growth.label,
      href: skillHref(locale, rising.item),
      name: rising.item.name,
    });
  }

  const leader = allItems[0];
  const pair = leader ? companionsOf(leader)[0] : null;
  if (leader && pair) {
    signals.push({
      key: `pair-${leader.skill_id || leader.name}-${pair.name}`,
      label: t.trendsPulseSignalPair,
      title: `${leader.name} + ${pair.name}`,
      body: t.trendsPulseSignalPairBody(pair.name, pair.share),
      href: skillHref(locale, leader),
      name: leader.name,
    });
  }

  for (const item of allItems.slice(1)) {
    if (signals.length >= 3) break;
    if (!mark(item)) continue;
    const share = pct(item.share);
    const ads = typeof item.ad_count === "number" ? item.ad_count : null;
    signals.push({
      key: `watch-${item.skill_id || item.name}`,
      label: t.trendsPulseSignalRunner,
      title: share != null ? `${item.name} · ${share}%` : item.name,
      body: ads != null ? t.trendsPulseSignalRunnerBody(ads) : t.trendsPulseRowSteady,
      href: skillHref(locale, item),
      name: item.name,
    });
  }

  return signals.slice(0, 3);
}

function TrendRow({ t, locale, item, index }) {
  const share = pct(item.share);
  const growth = growthParts(item.growth_wow);
  const salaries = salaryGroups(t, item);
  const companions = companionsOf(item);
  const rank = String(index + 1).padStart(2, "0");
  const barWidth = share === null ? 0 : Math.max(4, Math.min(100, share));
  const teaser = rowTeaser(t, item, growth);
  const meta = [
    typeof item.ad_count === "number" ? t.trendsAdsCount(item.ad_count) : null,
    teaser,
    ...salaries.map((row) => row.line),
  ].filter(Boolean);
  const href = skillHref(locale, item);

  const body = (
    <>
      <span className="trend-row-rank" aria-hidden="true">
        {rank}
      </span>
      <div className="trend-row-main">
        <div className="trend-row-title">
          <span className="trend-row-heading">
            <SkillIcon name={item.name} />
            <h2>{item.name}</h2>
          </span>
          {growth ? (
            <span className={`trends-growth trends-growth-${growth.direction}`}>{growth.label}</span>
          ) : null}
          {share !== null ? <span className="trend-row-share">{share}%</span> : null}
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
        {meta.length ? <p className="trend-row-meta">{meta.join(" · ")}</p> : null}
        {companions.length ? (
          <ul className="tech-chips trends-companion-chips" aria-label={t.trendsOftenWith}>
            {companions.map((row) => (
              <li key={row.name} className="tech-chip trends-companion-chip">
                <SkillIcon name={row.name} />
                <span>{row.name}</span>
                <span className="trends-companion-pct">{row.share}%</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      {href ? (
        <span className="trend-row-chevron" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" focusable="false">
            <path
              d="M6 3.5 10.5 8 6 12.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      ) : null}
    </>
  );

  return (
    <li className="trend-row">
      {href ? (
        <a className="trend-row-link" href={href}>
          {body}
        </a>
      ) : (
        <div className="trend-row-link">{body}</div>
      )}
    </li>
  );
}

function TrendsWindowTools({ t, locale, window }) {
  return (
    <div className="h2-tools h2-trends-tools">
      <div className="filter-chips-scroll" role="group" aria-label={t.trendsWindowLabel}>
        {TRENDS_WINDOWS.map((days) => (
          <a
            key={days}
            className={`filter-chip${window === days ? " is-on" : ""}`}
            href={listHref(locale, { windowDays: days })}
            aria-current={window === days ? "true" : undefined}
          >
            {days}
          </a>
        ))}
      </div>
      <form className="h2-trends-custom" method="get" action={hrefFor(locale, { mode: "trends" })}>
        <label className="h2-trends-custom-field" htmlFor="trends-window-days">
          <span className="visually-hidden">{t.trendsWindowLabel}</span>
          <span className="h2-trends-custom-prefix" aria-hidden="true">
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
          <span className="h2-trends-custom-unit">{t.trendsWindowUnit}</span>
        </label>
        <button type="submit" className="btn ink">
          {t.trendsWindowApply}
        </button>
      </form>
    </div>
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
  const leader = allItems[0] || null;
  const leaderShare = leader ? pct(leader.share) : null;
  const leaderHref = skillHref(locale, leader);
  const signals = total ? buildRisingSignals(t, locale, allItems) : [];
  const showRisingCta = signals.length > 0;

  return (
    <Shell locale={locale} mode="trends">
      <div className="h2-public h2-trends h2-trends-pulse">
        <section className="trends-pulse-stage" aria-labelledby="trends-pulse-title">
          <div className="trends-pulse-grid">
            <div className="trends-pulse-copy">
              <p className="trends-pulse-live">
                <span className="trends-pulse-live-dot" aria-hidden="true" />
                <span>{t.trendsPulseLive}</span>
                <span className="trends-pulse-live-sep" aria-hidden="true">
                  ·
                </span>
                <span>{t.trendsPulseWindowHint(window)}</span>
              </p>
              <h1 id="trends-pulse-title" className="trends-pulse-title">
                <span>{t.trendsPulseTitleLead} </span>
                <span className="trends-pulse-title-focus">{t.trendsPulseTitleFocus}</span>
                <span> {t.trendsPulseTitleTail}</span>
              </h1>
              <p className="trends-pulse-lede">{t.trendsPulseLede}</p>
              <div className="trends-pulse-cta">
                <a className="btn trends-pulse-btn-primary" href="#trends-board">
                  {t.trendsPulseCtaBoard}
                </a>
                {showRisingCta ? (
                  <a className="btn trends-pulse-btn-ghost" href="#trends-rising">
                    {t.trendsPulseCtaRising}
                  </a>
                ) : null}
              </div>
            </div>

            {leader && leaderShare != null ? (
              <aside className="trends-pulse-champ">
                <span className="trends-pulse-champ-badge">{t.trendsPulseChampBadge}</span>
                <p className="trends-pulse-champ-rank" aria-hidden="true">
                  01
                </p>
                <div className="trends-pulse-champ-heading">
                  <SkillIcon name={leader.name} className="trends-pulse-champ-icon" />
                  {leaderHref ? (
                    <a className="trends-pulse-champ-name" href={leaderHref}>
                      {leader.name}
                    </a>
                  ) : (
                    <span className="trends-pulse-champ-name">{leader.name}</span>
                  )}
                </div>
                <p className="trends-pulse-champ-line">
                  {t.trendsPulseChampLine(leader.name, leaderShare)}
                </p>
                <div className="trends-pulse-champ-bar" aria-hidden="true">
                  <span style={{ width: `${Math.max(8, Math.min(100, leaderShare))}%` }} />
                </div>
                <div className="trends-pulse-champ-meta">
                  <span>{t.trendsPulseChampShareLabel}</span>
                  <strong>{leaderShare}%</strong>
                </div>
                {typeof leader.ad_count === "number" ? (
                  <p className="trends-pulse-champ-ads">{t.trendsAdsCount(leader.ad_count)}</p>
                ) : null}
              </aside>
            ) : null}
          </div>
        </section>

        {signals.length ? (
          <section
            id="trends-rising"
            className="trends-pulse-rising"
            aria-label={t.trendsPulseCtaRising}
          >
            <div className="trends-pulse-rising-strip">
              {signals.map((signal) => {
                const inner = (
                  <>
                    <p className="trends-pulse-rise-label">{signal.label}</p>
                    <h2 className="trends-pulse-rise-title">
                      <SkillIcon name={signal.name} />
                      <span>{signal.title}</span>
                    </h2>
                    <p className="trends-pulse-rise-body">{signal.body}</p>
                  </>
                );
                return signal.href ? (
                  <a key={signal.key} className="trends-pulse-rise" href={signal.href}>
                    {inner}
                  </a>
                ) : (
                  <article key={signal.key} className="trends-pulse-rise">
                    {inner}
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}

        <section id="trends-board" className="trends-pulse-board" aria-labelledby="trends-board-title">
          <div className="trends-pulse-board-head">
            <div>
              <h2 id="trends-board-title" className="trends-pulse-board-title">
                {t.trendsPulseBoardTitle}
                {total ? <span className="trends-pulse-board-count">{total}</span> : null}
              </h2>
              <p className="trends-pulse-board-lede">{t.trendsPulseBoardLede}</p>
            </div>
            <a className="trends-pulse-back" href={hrefFor(locale)}>
              ← {t.breadcrumbHome}
            </a>
          </div>

          <TrendsWindowTools t={t} locale={locale} window={window} />

          <div className="h2-trends-meta">
            <p className="hint">{disclaimer}</p>
            {asOf ? <p className="hint">{asOf}</p> : null}
          </div>

          {error || !total ? (
            <div className="h2-empty">
              <p className="note">{t.trendsEmpty}</p>
            </div>
          ) : (
            <>
              <ol className="trend-row-list" start={offset + 1}>
                {items.map((item, index) => (
                  <TrendRow
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
        </section>
      </div>
    </Shell>
  );
}
