import { cache } from "react";
import { fetchJob, fetchJobs } from "../api";

/** Dedupes job fetches within one RSC request (page + generateMetadata). */
export const getJob = cache(async (id) => fetchJob(id));
export const getJobs = cache(async () => fetchJobs());
