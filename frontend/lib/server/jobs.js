import { cache } from "react";
import { fetchCompanies, fetchCompany, fetchJob, fetchJobs } from "../api";

/** Dedupes job fetches within one RSC request (page + generateMetadata). */
export const getJob = cache(async (id) => fetchJob(id));
export const getJobs = cache(async () => fetchJobs());
export const getCompanies = cache(async (q, sort, page) => fetchCompanies({ q, sort, page }));
export const getCompany = cache(async (slug, page) => fetchCompany(slug, { page }));
