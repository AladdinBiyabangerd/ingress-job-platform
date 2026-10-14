import { cache } from "react";
import { apiBase, fetchCompanies, fetchCompany, fetchJob, fetchJobs } from "../api";

/** Dedupes job fetches within one RSC request (page + generateMetadata). */
export const getJob = cache(async (id) => fetchJob(id));

/** Cache key is JSON so object-shaped filters dedupe correctly. */
export const getJobs = cache(async (paramsKey = "{}") => {
  const params = typeof paramsKey === "string" ? JSON.parse(paramsKey || "{}") : paramsKey || {};
  return fetchJobs(params);
});

export const getCompanies = cache(async (q, sort, page) => fetchCompanies({ q, sort, page }));
export const getCompany = cache(async (slug, page) => fetchCompany(slug, { page }));

export function emptyJobsPayload() {
  return {
    items: [],
    total: 0,
    pages: 1,
    catalog_total: 0,
    facets: { languages: [], categories: [], stacks: [], countries: [], cities: [], remote_total: 0 },
  };
}

export async function loadHomeJobs(board = {}) {
  const forYouMode = Boolean(board.forYouMode);
  const forYouCv = forYouMode && String(board.forYouSource || "cv") !== "filters";
  const fetchParams = {
    page: forYouCv ? 1 : Math.max(1, Number(board.page) || 1),
    perPage: 20,
    q: board.q || "",
    company: board.company || "",
    city: board.city || "",
    remote: Boolean(board.remote),
    relocation: Boolean(board.relocation),
    onsite: Boolean(board.onsite),
    when: board.when || "any",
    sort: board.sort || "newest",
    languages: Array.isArray(board.languages) ? board.languages : [],
    categories: Array.isArray(board.categories) ? board.categories : [],
    stacks: Array.isArray(board.stacks) ? board.stacks : [],
    salaryMin: board.salaryMin || "",
    salaryMax: board.salaryMax || "",
  };
  try {
    const data = await getJobs(JSON.stringify(fetchParams));
    if (forYouCv) {
      // CV matches load client-side; keep facets from catalogue fetch.
      return {
        data: { ...data, items: [], total: 0, pages: 1, page: 1 },
        error: false,
      };
    }
    return { data, error: false };
  } catch (err) {
    console.error("[home] getJobs failed", {
      base: apiBase(),
      message: err instanceof Error ? err.message : String(err),
    });
    return { data: emptyJobsPayload(), error: true };
  }
}
