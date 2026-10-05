import { PageHeader } from "./page-header";
import { Shell } from "./shell";
import { text } from "../lib/copy";

function pct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

function growthLabel(t, growth) {
  const value = pct(growth);
  if (value === null) return null;
  const sign = value > 0 ? "+" : "";
  return `${t.trendsGrowth}: ${sign}${value}%`;
}

function formatMoney(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return Math.round(value).toLocaleString("en-US");
}

function salaryLabel(t, salary) {
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
  return [t.trendsSalary(median, currency), range, t.trendsSalaryN(n)]
    .filter(Boolean)
    .join(" · ");
}

export function TrendsPage({ locale, data, error }) {
  const t = text(locale);
  const items = Array.isArray(data?.items) ? data.items : [];
  const disclaimer = data?.disclaimer || t.trendsDisclaimer;

  return (
    <Shell locale={locale} mode="trends">
      <main className="trends-page">
        <PageHeader
          title={t.trendsTitle}
          count={items.length ? String(items.length) : null}
          lede={t.trendsLede}
        />
        <p className="hint trends-disclaimer">{disclaimer}</p>
        {data?.as_of || data?.window_days ? (
          <p className="hint">
            {[
              data?.as_of ? t.trendsAsOf(data.as_of) : null,
              data?.window_days ? t.trendsWindow(data.window_days) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        ) : null}

        {error ? (
          <p className="hint">{t.trendsEmpty}</p>
        ) : !items.length ? (
          <p className="hint">{t.trendsEmpty}</p>
        ) : (
          <ol className="trends-list">
            {items.map((item, index) => {
              const share = pct(item.share);
              const growth = growthLabel(t, item.growth_wow);
              const salary = salaryLabel(t, item.salary);
              return (
                <li key={item.skill_id || item.name} className="trends-item">
                  <span className="trends-rank">{index + 1}</span>
                  <div className="trends-body">
                    <strong>{item.name}</strong>
                    <p className="hint">
                      {[
                        share !== null ? `${t.trendsShare}: ${share}%` : null,
                        typeof item.ad_count === "number"
                          ? `${t.trendsAds}: ${item.ad_count}`
                          : null,
                        growth,
                        salary,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </main>
    </Shell>
  );
}
