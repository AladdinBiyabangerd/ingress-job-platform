"use client";

import { useEffect, useState } from "react";
import { hrefFor, text } from "../lib/copy";

const MAX_DISPLAY_GROWTH = 5;
const LIMIT = 4;

function growthLabel(t, growth) {
  if (typeof growth !== "number" || Number.isNaN(growth)) return null;
  if (Math.abs(growth) > MAX_DISPLAY_GROWTH) return null;
  const pct = Math.round(growth * 100);
  if (pct > 0) return { direction: "up", label: t.trendAsideRising };
  if (pct < 0) return { direction: "down", label: t.trendAsideFalling };
  return { direction: "flat", label: t.trendAsideGrowing };
}

export function TrendAside({ locale }) {
  const t = text(locale);
  const [items, setItems] = useState([]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: String(LIMIT), window_days: "7", lang: locale });
    fetch(`/api/trends?${params}`, { cache: "no-store", signal: controller.signal })
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) return;
        setItems(Array.isArray(data.items) ? data.items.slice(0, LIMIT) : []);
      })
      .catch((err) => {
        if (err?.name === "AbortError") return;
        setItems([]);
      });
    return () => controller.abort();
  }, [locale]);

  if (!items.length) return null;

  return (
    <aside className="side-widget trend-aside" aria-labelledby="trend-aside-title">
      <div className="side-widget-head">
        <h2 id="trend-aside-title">{t.trendAsideTitle}</h2>
        <a className="side-widget-link" href={hrefFor(locale, { mode: "trends" })}>
          {t.trendAsideViewAll}
        </a>
      </div>
      <ul className="trend-aside-list">
        {items.map((item) => {
          const growth = growthLabel(t, item.growth_wow);
          const href =
            item.skill_id != null
              ? hrefFor(locale, { mode: "trend", skillId: item.skill_id })
              : hrefFor(locale, { mode: "trends" });
          return (
            <li key={item.skill_id || item.name}>
              <a className="trend-aside-item" href={href}>
                <span className="trend-aside-mark" aria-hidden="true">
                  {(item.name || "?").charAt(0).toUpperCase()}
                </span>
                <span className="trend-aside-name">{item.name}</span>
                {growth ? (
                  <span className={`trend-aside-growth is-${growth.direction}`}>{growth.label}</span>
                ) : null}
              </a>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
