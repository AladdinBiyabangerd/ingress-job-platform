const API_FETCH_TIMEOUT_MS = 5_000;

/** Public catalog pages share this ISR window (seconds). */
export const PUBLIC_REVALIDATE = 60;

export function apiBase() {
  const direct = process.env.JOB_API_BASE_URL;
  if (direct) return direct.replace(/\/$/, "");
  const host = (process.env.API_PRIVATE_HOST || "").trim();
  if (host) {
    const port = process.env.API_PORT || "8080";
    return `http://${host}:${port}`;
  }
  return process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8010";
}

function apiFetch(path, init = {}) {
  return fetch(`${apiBase()}${path}`, {
    next: { revalidate: PUBLIC_REVALIDATE },
    ...init,
    signal: init.signal ?? AbortSignal.timeout(API_FETCH_TIMEOUT_MS),
  });
}

/** Build query string for GET /api/v1/jobs (and the Next BFF). */
export function jobsListParams({
  page = 1,
  perPage = 20,
  q = "",
  company = "",
  remote = false,
  relocation = false,
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
  if (remote) params.set("remote", "true");
  if (relocation) params.set("relocation", "true");
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

export async function fetchJobs(options = {}) {
  const params = jobsListParams(options);
  const qs = params.toString();
  const res = await apiFetch(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`jobs ${res.status}`);
  const data = await res.json();
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: Number(data.total) || 0,
    page: Number(data.page) || 1,
    per_page: Number(data.per_page) || 20,
    pages: Number(data.pages) || 1,
    catalog_total: Number(data.catalog_total) || 0,
    facets: data.facets && typeof data.facets === "object"
      ? data.facets
      : { languages: [], categories: [], stacks: [] },
  };
}

export async function fetchCompanies({ q = "", sort = "jobs", page = 1, perPage = 24 } = {}) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("sort", sort);
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  const res = await apiFetch(`/api/v1/companies?${params.toString()}`);
  if (!res.ok) throw new Error(`companies ${res.status}`);
  return res.json();
}

export async function fetchCompany(slug, { page = 1, perPage = 20 } = {}) {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  const res = await apiFetch(`/api/v1/companies/${encodeURIComponent(slug)}?${params.toString()}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`company ${res.status}`);
  return res.json();
}

export async function fetchJob(id) {
  const res = await apiFetch(`/api/v1/jobs/${id}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`job ${res.status}`);
  return res.json();
}

export async function fetchTrends({
  category = "",
  region = "",
  limit = 30,
  windowDays = 7,
  lang = "az",
} = {}) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (region) params.set("region", region);
  if (limit) params.set("limit", String(limit));
  if (windowDays) params.set("window_days", String(windowDays));
  if (lang) params.set("lang", lang);
  const res = await apiFetch(`/api/v1/trends?${params.toString()}`);
  if (!res.ok) throw new Error(`trends ${res.status}`);
  return res.json();
}
