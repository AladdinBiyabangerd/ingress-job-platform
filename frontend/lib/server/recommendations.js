import { cache } from "react";
import { cookies } from "next/headers";
import { apiBase } from "../api";
import { ACCESS_COOKIE } from "./oidc";
import { getMe } from "./me";

export const MATCHES_FETCH_LIMIT = 50;
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
 * Roles + matches for /me/recommendations. Skips FastAPI for guests and
 * non-candidates. Deduped within one RSC request.
 */
export const getRecommendationBundle = cache(async (lang = "az") => {
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { roles: null, matches: null };
  }
  const store = await cookies();
  const access = store.get(ACCESS_COOKIE)?.value;
  if (!access) return { roles: null, matches: null };
  const locale = localeLang(lang);
  const qs = `lang=${encodeURIComponent(locale)}`;
  const [roles, matches] = await Promise.all([
    loadJson(access, `/api/v1/me/roles?${qs}`),
    loadJson(access, `/api/v1/me/matches?${qs}&limit=${MATCHES_FETCH_LIMIT}`),
  ]);
  return { roles, matches };
});
