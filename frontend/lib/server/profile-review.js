import { cache } from "react";
import { apiBase } from "../api";
import { getMe, sessionAccess } from "./me";

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
 * CV profile + role hints for /profile/review. Skips FastAPI for guests and
 * non-candidates. Deduped within one RSC request.
 */
export const getProfileReview = cache(async (lang = "az") => {
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { profile: null, roles: null };
  }
  const access = await sessionAccess();
  if (!access) return { profile: null, roles: null };
  const locale = localeLang(lang);
  const [profile, roles] = await Promise.all([
    loadJson(access, "/api/v1/profile"),
    loadJson(access, `/api/v1/me/roles?lang=${encodeURIComponent(locale)}`),
  ]);
  return { profile, roles };
});
