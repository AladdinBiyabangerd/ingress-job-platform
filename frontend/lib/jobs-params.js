/** Build query string for GET /api/v1/jobs (and the Next BFF). */
export function jobsListParams({
  page = 1,
  perPage = 20,
  q = "",
  company = "",
  city = "",
  remote = false,
  relocation = false,
  onsite = false,
  when = "any",
  sort = "newest",
  languages = [],
  categories = [],
  stacks = [],
  salaryMin = "",
  salaryMax = "",
} = {}) {
  const params = new URLSearchParams();
  params.set("page", String(Math.max(1, Number(page) || 1)));
  params.set("per_page", String(Math.max(1, Math.min(60, Number(perPage) || 20))));
  const query = String(q || "").trim();
  if (query) params.set("q", query);
  const companyQ = String(company || "").trim();
  if (companyQ) params.set("company", companyQ);
  const cityQ = String(city || "").trim();
  if (cityQ) params.set("city", cityQ);
  if (remote) params.set("remote", "true");
  if (relocation) params.set("relocation", "true");
  if (onsite) params.set("onsite", "true");
  if (when && when !== "any") params.set("when", when);
  if (sort && sort !== "newest") params.set("sort", sort);
  for (const code of languages || []) {
    const value = String(code || "").trim();
    if (value) params.append("language", value);
  }
  for (const name of categories || []) {
    const value = String(name || "").trim();
    if (value) params.append("category", value);
  }
  for (const name of stacks || []) {
    const value = String(name || "").trim();
    if (value) params.append("stack", value);
  }
  const minRaw = String(salaryMin ?? "").trim();
  const maxRaw = String(salaryMax ?? "").trim();
  if (minRaw !== "" && Number.isFinite(Number(minRaw))) params.set("salary_min", String(Number(minRaw)));
  if (maxRaw !== "" && Number.isFinite(Number(maxRaw))) params.set("salary_max", String(Number(maxRaw)));
  return params;
}

function _firstParam(query, key) {
  const v = query?.[key];
  if (Array.isArray(v)) return v[0] ?? "";
  return v ?? "";
}

function _allParams(query, key) {
  const v = query?.[key];
  if (v == null || v === "") return [];
  if (Array.isArray(v)) return v.map(String).map((s) => s.trim()).filter(Boolean);
  return [String(v).trim()].filter(Boolean);
}

function _truthyParam(value) {
  const s = String(value || "").trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes";
}

export const DEFAULT_BOARD_FILTERS = {
  q: "",
  company: "",
  city: "",
  languages: [],
  remote: false,
  relocation: false,
  onsite: false,
  stacks: [],
  categories: [],
  when: "any",
  sort: "newest",
  salaryMin: "",
  salaryMax: "",
  page: 1,
  forYouMode: false,
};

/** Parse home-board filters from Next.js `searchParams` or a plain query object. */
export function boardFiltersFromSearchParams(query = {}) {
  const whenRaw = String(_firstParam(query, "when") || "any").trim().toLowerCase();
  const sortRaw = String(_firstParam(query, "sort") || "newest").trim().toLowerCase();
  const page = Math.max(1, Number(_firstParam(query, "page")) || 1);
  const tab = String(_firstParam(query, "tab") || "").trim().toLowerCase();
  return {
    q: String(_firstParam(query, "q") || "").trim(),
    company: String(_firstParam(query, "company") || "").trim(),
    city: String(_firstParam(query, "city") || "").trim(),
    languages: _allParams(query, "language"),
    remote: _truthyParam(_firstParam(query, "remote")),
    relocation: _truthyParam(_firstParam(query, "relocation")),
    onsite: _truthyParam(_firstParam(query, "onsite")),
    stacks: _allParams(query, "stack"),
    categories: _allParams(query, "category"),
    when: whenRaw === "today" || whenRaw === "week" ? whenRaw : "any",
    sort: sortRaw === "newest" ? "newest" : sortRaw || "newest",
    salaryMin: String(_firstParam(query, "salary_min") || "").trim(),
    salaryMax: String(_firstParam(query, "salary_max") || "").trim(),
    page,
    forYouMode: tab === "foryou",
  };
}

/** Browser URL query for the home board (no per_page; omit defaults). */
export function boardUrlSearchParams(board = {}) {
  const params = new URLSearchParams();
  if (board.forYouMode) params.set("tab", "foryou");
  const query = String(board.q || "").trim();
  if (query) params.set("q", query);
  const companyQ = String(board.company || "").trim();
  if (companyQ) params.set("company", companyQ);
  const cityQ = String(board.city || "").trim();
  if (cityQ) params.set("city", cityQ);
  if (board.remote) params.set("remote", "true");
  if (board.relocation) params.set("relocation", "true");
  if (board.onsite) params.set("onsite", "true");
  if (board.when && board.when !== "any") params.set("when", board.when);
  if (board.sort && board.sort !== "newest") params.set("sort", board.sort);
  for (const code of board.languages || []) {
    const value = String(code || "").trim();
    if (value) params.append("language", value);
  }
  for (const name of board.categories || []) {
    const value = String(name || "").trim();
    if (value) params.append("category", value);
  }
  for (const name of board.stacks || []) {
    const value = String(name || "").trim();
    if (value) params.append("stack", value);
  }
  const minRaw = String(board.salaryMin ?? "").trim();
  const maxRaw = String(board.salaryMax ?? "").trim();
  if (minRaw !== "" && Number.isFinite(Number(minRaw))) params.set("salary_min", String(Number(minRaw)));
  if (maxRaw !== "" && Number.isFinite(Number(maxRaw))) params.set("salary_max", String(Number(maxRaw)));
  const page = Math.max(1, Number(board.page) || 1);
  if (page > 1) params.set("page", String(page));
  return params;
}
