/** Persist home-board filters across refresh / leave until the user clears them. */

import { boardUrlSearchParams, DEFAULT_BOARD_FILTERS } from "./jobs-params";

const STORAGE_KEY = "ingress.job.board.v1";

function browseBasePath(locale) {
  if (locale === "en") return "/en";
  if (locale === "ru") return "/ru";
  return "/";
}

function _asStringArray(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function _asBool(value) {
  return Boolean(value);
}

/** Normalize a partial board object into a safe persisted shape. */
export function normalizePersistedBoard(raw = {}) {
  const whenRaw = String(raw.when || "any").trim().toLowerCase();
  const sortRaw = String(raw.sort || "newest").trim().toLowerCase();
  const sourceRaw = String(raw.forYouSource || "cv").trim().toLowerCase();
  return {
    q: String(raw.q || "").trim(),
    company: String(raw.company || "").trim(),
    city: String(raw.city || "").trim(),
    languages: _asStringArray(raw.languages),
    remote: _asBool(raw.remote),
    relocation: _asBool(raw.relocation),
    onsite: _asBool(raw.onsite),
    stacks: _asStringArray(raw.stacks),
    categories: _asStringArray(raw.categories),
    when: whenRaw === "today" || whenRaw === "week" ? whenRaw : "any",
    sort: sortRaw === "oldest" || sortRaw === "title" ? sortRaw : "newest",
    salaryMin: String(raw.salaryMin ?? "").trim(),
    salaryMax: String(raw.salaryMax ?? "").trim(),
    page: Math.max(1, Number(raw.page) || 1),
    forYouMode: _asBool(raw.forYouMode),
    forYouSource: sourceRaw === "filters" ? "filters" : "cv",
  };
}

export function readPersistedBoard() {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    return normalizePersistedBoard(parsed);
  } catch {
    return null;
  }
}

export function writePersistedBoard(board) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizePersistedBoard(board)));
  } catch {
    /* quota / private mode */
  }
}

export function clearPersistedBoard() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** True when the live URL already carries board state. */
export function urlHasBoardState(search = "") {
  const params = new URLSearchParams(
    String(search || "").startsWith("?") ? String(search).slice(1) : String(search || ""),
  );
  for (const key of [
    "tab",
    "q",
    "company",
    "city",
    "language",
    "remote",
    "relocation",
    "onsite",
    "stack",
    "category",
    "when",
    "sort",
    "salary_min",
    "salary_max",
    "page",
    "fy",
  ]) {
    if (params.has(key)) return true;
  }
  return false;
}

/**
 * Merge persisted filters under a URL board: URL wins for present params;
 * missing fields come from localStorage so leave/refresh keeps choices until clear.
 */
export function mergeBoardWithPersist(urlBoard = {}, saved = null, search = "") {
  if (!saved) return normalizePersistedBoard(urlBoard);
  const params = new URLSearchParams(
    String(search || "").startsWith("?") ? String(search).slice(1) : String(search || ""),
  );
  if (![...params.keys()].length) return normalizePersistedBoard(saved);

  const base = normalizePersistedBoard(urlBoard);
  const fill = normalizePersistedBoard(saved);
  return normalizePersistedBoard({
    q: params.has("q") ? base.q : fill.q,
    company: params.has("company") ? base.company : fill.company,
    city: params.has("city") ? base.city : fill.city,
    languages: params.has("language") ? base.languages : fill.languages,
    remote: params.has("remote") ? base.remote : fill.remote,
    relocation: params.has("relocation") ? base.relocation : fill.relocation,
    onsite: params.has("onsite") ? base.onsite : fill.onsite,
    stacks: params.has("stack") ? base.stacks : fill.stacks,
    categories: params.has("category") ? base.categories : fill.categories,
    when: params.has("when") ? base.when : fill.when,
    sort: params.has("sort") ? base.sort : fill.sort,
    salaryMin: params.has("salary_min") ? base.salaryMin : fill.salaryMin,
    salaryMax: params.has("salary_max") ? base.salaryMax : fill.salaryMax,
    page: params.has("page") ? base.page : fill.page,
    forYouMode: params.has("tab") ? base.forYouMode : fill.forYouMode,
    forYouSource: params.has("fy") ? base.forYouSource : fill.forYouSource,
  });
}

export function boardsDiffer(a, b) {
  return JSON.stringify(normalizePersistedBoard(a)) !== JSON.stringify(normalizePersistedBoard(b));
}

export function boardEqualsDefault(board) {
  const n = normalizePersistedBoard(board);
  const d = DEFAULT_BOARD_FILTERS;
  return (
    n.q === d.q
    && n.company === d.company
    && n.city === d.city
    && n.languages.length === 0
    && n.remote === false
    && n.relocation === false
    && n.onsite === false
    && n.stacks.length === 0
    && n.categories.length === 0
    && n.when === "any"
    && n.sort === "newest"
    && n.salaryMin === ""
    && n.salaryMax === ""
    && n.page === 1
    && n.forYouMode === false
    && n.forYouSource === "cv"
  );
}

/** Home/browse URL with last saved filters (empty query when nothing saved). */
export function browseHrefFromPersist(locale) {
  const base = browseBasePath(locale);
  if (typeof window === "undefined") return base;
  const saved = readPersistedBoard();
  if (!saved || boardEqualsDefault(saved)) return base;
  const query = boardUrlSearchParams(saved).toString();
  if (!query) return base;
  return `${base}?${query}`;
}
