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
    if (!res.ok) return { ok: false, status: res.status, data: null };
    const data = await res.json();
    return { ok: true, status: res.status, data: data && typeof data === "object" ? data : null };
  } catch {
    return { ok: false, status: 502, data: null };
  }
}

/** Talent search SSR seed. Guests / non-employers get gate info only. */
export const getTalentSearch = cache(async (q = "") => {
  const me = await getMe();
  if (!me?.authenticated) {
    return { me, items: null, total: 0, pages: 0, q: "", gate: "guest" };
  }
  if (!(me.employer || me.staff)) {
    return { me, items: null, total: 0, pages: 0, q: "", gate: "role" };
  }
  if (me.needs_company_profile) {
    return { me, items: null, total: 0, pages: 0, q: "", gate: "company" };
  }
  const access = await sessionAccess();
  if (!access) {
    return { me, items: null, total: 0, pages: 0, q: "", gate: "guest" };
  }
  const params = new URLSearchParams({ page: "1", per_page: "20" });
  const query = typeof q === "string" ? q.trim() : "";
  if (query) params.set("q", query);
  const result = await loadJson(access, `/api/v1/talent?${params}`);
  if (!result.ok || !result.data) {
    return { me, items: null, total: 0, pages: 0, q: query, gate: result.status === 403 ? "company" : "error" };
  }
  return {
    me,
    items: Array.isArray(result.data.items) ? result.data.items : [],
    total: Number(result.data.total) || 0,
    pages: Number(result.data.pages) || 0,
    q: result.data.q || query,
    gate: null,
  };
});
