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

/** Saved jobs page seed. Guests get null items (gate UI). */
export const getSavedJobs = cache(async () => {
  const me = await getMe();
  if (!me?.authenticated) return { items: null, ids: [] };
  const access = await sessionAccess();
  if (!access) return { items: null, ids: [] };
  const [list, idsPayload] = await Promise.all([
    loadJson(access, "/api/v1/me/saved-jobs?page=1&per_page=20"),
    loadJson(access, "/api/v1/me/saved-jobs/ids"),
  ]);
  const items = list && Array.isArray(list.items) ? list.items : null;
  const ids = idsPayload && Array.isArray(idsPayload.ids)
    ? idsPayload.ids.map((id) => Number(id)).filter((id) => id > 0)
    : [];
  return { items, ids, total: list?.total ?? 0, pages: list?.pages ?? 0 };
});
