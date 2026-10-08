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
 * Growth hub payload for /me/insights. Skips FastAPI for guests / non-candidates.
 */
export const getInsightsBundle = cache(async (lang = "az") => {
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { insights: null };
  }
  const access = await sessionAccess();
  if (!access) return { insights: null };
  const locale = localeLang(lang);
  const insights = await loadJson(access, `/api/v1/me/insights?lang=${encodeURIComponent(locale)}`);
  return { insights };
});
