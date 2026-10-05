const API_FETCH_TIMEOUT_MS = 5_000;

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
    cache: "no-store",
    ...init,
    signal: init.signal ?? AbortSignal.timeout(API_FETCH_TIMEOUT_MS),
  });
}

export async function fetchJobs() {
  const res = await apiFetch("/api/v1/jobs");
  if (!res.ok) throw new Error(`jobs ${res.status}`);
  const data = await res.json();
  return Array.isArray(data.items) ? data.items : [];
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
