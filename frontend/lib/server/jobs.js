import { cache } from "react";
import { fetchCompanies, fetchCompany, fetchJob, fetchJobs } from "../api";

/** Dedupes job fetches within one RSC request (page + generateMetadata). */
export const getJob = cache(async (id) => fetchJob(id));

/** Cache key is JSON so object-shaped filters dedupe correctly. */
export const getJobs = cache(async (paramsKey = "{}") => {
  const params = typeof paramsKey === "string" ? JSON.parse(paramsKey || "{}") : paramsKey || {};
  return fetchJobs(params);
});

export const getCompanies = cache(async (q, sort, page) => fetchCompanies({ q, sort, page }));
export const getCompany = cache(async (slug, page) => fetchCompany(slug, { page }));
