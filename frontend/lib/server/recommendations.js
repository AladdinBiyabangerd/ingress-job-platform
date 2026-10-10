import { cache } from "react";
import { apiBase } from "../api";
import { recommendationsEnabled } from "../product-features";
import { getMe, sessionAccess } from "./me";

export const MATCHES_FETCH_LIMIT = 10;
const TIMEOUT_MS = 10_000;

function localeLang(lang) {
  return lang === "en" || lang === "ru" ? lang : "az";
}

async function loadJson(access, path, timeoutMs = TIMEOUT_MS) {
  try {
    const res = await fetch(`${apiBase()}${path}`, {
      headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data && typeof data === "object" ? data : null;
  } catch {
    return null;
  }
}

/**
 * Roles + role-scoped matches (+ optional gap) for /me/recommendations.
 * Skips FastAPI for guests and non-candidates. Deduped within one RSC request.
 */
export const getRecommendationBundle = cache(async (lang = "az", preferredRole = "", includeGap = true) => {
  if (!recommendationsEnabled()) {
    return { roles: null, matches: null, gap: null, role: "" };
  }
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { roles: null, matches: null, gap: null, role: "" };
  }
  const access = await sessionAccess();
  if (!access) return { roles: null, matches: null, gap: null, role: "" };
  const locale = localeLang(lang);
  const qs = `lang=${encodeURIComponent(locale)}`;
  const roles = await loadJson(access, `/api/v1/me/roles?${qs}`);
  const preferred = String(preferredRole || "").trim();
  const roleNames = Array.isArray(roles?.roles)
    ? roles.roles.map((r) => r?.canonical_name).filter(Boolean)
    : [];
  const topRole =
    (preferred && roleNames.includes(preferred) ? preferred : null) || roleNames[0] || "";
  const roleQs = topRole ? `&role=${encodeURIComponent(topRole)}` : "";
  const [matches, gap] = await Promise.all([
    loadJson(access, `/api/v1/me/matches?${qs}&limit=${MATCHES_FETCH_LIMIT}${roleQs}`),
    includeGap && topRole
      ? loadJson(
          access,
          `/api/v1/me/skill-gap?${qs}&role=${encodeURIComponent(topRole)}`,
          12_000,
        )
      : Promise.resolve(null),
  ]);
  return { roles, matches, gap, role: topRole };
});
