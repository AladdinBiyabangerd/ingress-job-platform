import { cache } from "react";
import { fetchTrendDetail } from "../api";
import { sessionAccess } from "./me";

/**
 * Public trend detail; attaches Authorization when a session exists so `you`
 * can hydrate on first paint for candidates.
 */
export const getTrendDetail = cache(async (skillId, { lang = "az", windowDays = 7 } = {}) => {
  const access = await sessionAccess();
  return fetchTrendDetail(skillId, {
    lang,
    windowDays,
    jobsLimit: 10,
    access: access || "",
  });
});
