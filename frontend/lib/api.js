import { jobsListParams } from "./jobs-params.js";

export { jobsListParams };

const API_FETCH_TIMEOUT_MS = 5_000;

/** Public catalog pages share this ISR window (seconds). */
export const PUBLIC_REVALIDATE = 60;

function env(name) {
  return String((process.env && process.env[name]) || "").trim();
}

function originWithPort(raw, fallbackPort) {
  try {
    const parsed = new URL(raw.includes("://") ? raw : `http://${raw}`);
    if (!parsed.port) parsed.port = fallbackPort;
    return parsed.origin;
  } catch {
    return raw.replace(/\/$/, "");
  }
}

export function apiBase() {
  const fallbackPort = env("API_PORT") || (env("NODE_ENV") === "production" ? "8080" : "8010");
  const direct = env("JOB_API_BASE_URL");
  if (direct) return originWithPort(direct, fallbackPort);
  const host = env("API_PRIVATE_HOST");
  if (host) {
    const formatted = host.includes(":") && !host.startsWith("[") ? `[${host}]` : host;
    return `http://${formatted}:${fallbackPort}`;
  }
  return env("NEXT_PUBLIC_API_BASE") || "http://127.0.0.1:8010";
}

function apiFetch(path, init = {}) {
  return fetch(`${apiBase()}${path}`, {
    next: { revalidate: PUBLIC_REVALIDATE },
    ...init,
    signal: init.signal ?? AbortSignal.timeout(API_FETCH_TIMEOUT_MS),
  });
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
