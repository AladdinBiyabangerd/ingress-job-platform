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
    facets: { languages: [], categories: [], stacks: [], cities: [], remote_total: 0 },
  };
}

export async function loadHomeJobs() {
  try {
    const data = await getJobs("{}");
    return { data, error: false };
  } catch (err) {
    console.error("[home] getJobs failed", {
      base: apiBase(),
      message: err instanceof Error ? err.message : String(err),
    });
    return { data: emptyJobsPayload(), error: true };
  }
}
