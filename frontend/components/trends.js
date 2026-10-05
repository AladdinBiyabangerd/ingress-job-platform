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
