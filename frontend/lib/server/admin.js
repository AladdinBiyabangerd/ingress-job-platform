import { cache } from "react";
import { apiBase } from "../api";
import { getMe, sessionAccess } from "./me";

const TIMEOUT_MS = 10_000;

async function loadJson(access, path) {
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

function emptyAdmin() {
  return { jobs: null, applications: null, crawled: null, aiFlags: null };
}

/**
 * Moderation queue + applications for /admin first paint.
 * Crawled ads and AI flags load on tab open (CollectedAdmin / AdminAiFlags).
 * Skips FastAPI for guests and non-staff. Deduped within one RSC request.
 */
export const getAdmin = cache(async () => {
  const me = await getMe();
  if (!me?.authenticated || !me.staff) {
    return emptyAdmin();
  }
  const access = await sessionAccess();
  if (!access) return emptyAdmin();
  // Default tab only. Applications, crawled, and AI flags load after paint / on tab.
  const jobs = await loadJson(access, "/api/v1/admin/jobs");
  return {
    jobs: jobs && Array.isArray(jobs.items) ? jobs.items : null,
    applications: null,
    crawled: null,
    aiFlags: null,
  };
});
