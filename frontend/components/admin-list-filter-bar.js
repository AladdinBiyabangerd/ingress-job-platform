"use client";

import { adminListFilterActive, emptyAdminListFilter } from "../lib/admin-list-filter";

/**
 * View-only filter row for admin tables (AI %, Rule %, source name).
 * Does not affect threshold publish / recheck actions.
 */
export function AdminListFilterBar({ t, filter, onChange, disabled = false }) {
  const active = adminListFilterActive(filter);

  function patch(partial) {
    onChange({ ...filter, ...partial });
  }

  return (
    <div className="admin-mod-filter" role="search" aria-label={t.adminListFilterLabel}>
      <label className="admin-mod-filter-field">
        <span className="admin-mod-filter-label">{t.adminScoreAi}</span>
        <select
          value={filter.aiOp === "lte" ? "lte" : "gte"}
          disabled={disabled}
          onChange={(event) => patch({ aiOp: event.target.value === "lte" ? "lte" : "gte" })}
          aria-label={`${t.adminScoreAi} ${t.adminOpGte}/${t.adminOpLte}`}
        >
          <option value="gte">{t.adminOpGte}</option>
          <option value="lte">{t.adminOpLte}</option>
        </select>
        <input
          type="number"
          min={0}
          max={100}
          value={filter.aiValue}
          disabled={disabled}
          placeholder="—"
          onChange={(event) => patch({ aiValue: event.target.value })}
          aria-label={`${t.adminScoreAi} ${t.adminThresholdLabel}`}
        />
      </label>
      <label className="admin-mod-filter-field">
        <span className="admin-mod-filter-label">{t.adminScoreRule}</span>
        <select
          value={filter.ruleOp === "lte" ? "lte" : "gte"}
          disabled={disabled}
          onChange={(event) => patch({ ruleOp: event.target.value === "lte" ? "lte" : "gte" })}
          aria-label={`${t.adminScoreRule} ${t.adminOpGte}/${t.adminOpLte}`}
        >
          <option value="gte">{t.adminOpGte}</option>
          <option value="lte">{t.adminOpLte}</option>
        </select>
        <input
          type="number"
          min={0}
          max={100}
          value={filter.ruleValue}
          disabled={disabled}
          placeholder="—"
          onChange={(event) => patch({ ruleValue: event.target.value })}
          aria-label={`${t.adminScoreRule} ${t.adminThresholdLabel}`}
        />
      </label>
      <label className="admin-mod-filter-field admin-mod-filter-source">
        <span className="visually-hidden">{t.adminListFilterSource}</span>
        <input
          type="search"
          value={filter.source}
          disabled={disabled}
          placeholder={t.adminListFilterSourcePlaceholder}
          onChange={(event) => patch({ source: event.target.value })}
          aria-label={t.adminListFilterSource}
        />
      </label>
      {active ? (
        <button
          type="button"
          className="btn small"
          disabled={disabled}
          onClick={() => onChange(emptyAdminListFilter())}
        >
          {t.adminListFilterClear}
        </button>
      ) : null}
    </div>
  );
}
