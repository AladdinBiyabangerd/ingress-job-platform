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
 * Moderation queue, applications, crawled ads, and AI flags for /admin.
 * Skips FastAPI for guests and non-staff. Deduped within one RSC request.
 */
export const getAdmin = cache(async () => {
  const me = await getMe();
  if (!me?.authenticated || !me.staff) {
    return emptyAdmin();
  }
  const access = await sessionAccess();
  if (!access) return emptyAdmin();
  const [jobs, applications, crawled, ai] = await Promise.all([
    loadJson(access, "/api/v1/admin/jobs"),
    loadJson(access, "/api/v1/admin/applications"),
    loadJson(access, "/api/v1/admin/crawled"),
    loadJson(access, "/api/v1/admin/ai-flags"),
  ]);
  return {
    jobs: jobs && Array.isArray(jobs.items) ? jobs.items : null,
    applications: applications && Array.isArray(applications.items) ? applications.items : null,
    crawled: crawled && Array.isArray(crawled.items) ? crawled.items : null,
    aiFlags:
      ai && ai.flags && typeof ai.flags === "object"
        ? { flags: ai.flags, key_configured: Boolean(ai.key_configured) }
        : null,
  };
});
