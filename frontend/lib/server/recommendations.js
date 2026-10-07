import { cache } from "react";
import { apiBase } from "../api";
import { getMe, sessionAccess } from "./me";

export const MATCHES_FETCH_LIMIT = 10;
const TIMEOUT_MS = 10_000;

function localeLang(lang) {
  return lang === "en" || lang === "ru" ? lang : "az";
}

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

/**
 * Roles + top-role gap + role-scoped matches for /me/recommendations.
 * Skips FastAPI for guests and non-candidates. Deduped within one RSC request.
 */
export const getRecommendationBundle = cache(async (lang = "az") => {
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { roles: null, matches: null, gap: null };
  }
  const access = await sessionAccess();
  if (!access) return { roles: null, matches: null, gap: null };
  const locale = localeLang(lang);
  const qs = `lang=${encodeURIComponent(locale)}`;
  const roles = await loadJson(access, `/api/v1/me/roles?${qs}`);
  const topRole = roles?.roles?.[0]?.canonical_name || "";
  const roleQs = topRole ? `&role=${encodeURIComponent(topRole)}` : "";
  const [matches, gap] = await Promise.all([
    loadJson(access, `/api/v1/me/matches?${qs}&limit=${MATCHES_FETCH_LIMIT}${roleQs}`),
    topRole
      ? loadJson(access, `/api/v1/me/skill-gap?${qs}&role=${encodeURIComponent(topRole)}`)
      : Promise.resolve(null),
  ]);
  return { roles, matches, gap };
});
