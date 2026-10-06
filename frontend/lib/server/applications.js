import { cache } from "react";
import { cookies } from "next/headers";
import { apiBase } from "../api";
import { ACCESS_COOKIE } from "./oidc";
import { getMe } from "./me";

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

/**
 * Candidate application list for /applications. Skips FastAPI for guests and
 * non-candidates. Deduped within one RSC request.
 */
export const getMyApplications = cache(async () => {
  const me = await getMe();
  if (!me?.authenticated || !(me.candidate || me.staff)) {
    return { items: null };
  }
  const store = await cookies();
  const access = store.get(ACCESS_COOKIE)?.value;
  if (!access) return { items: null };
  const data = await loadJson(access, "/api/v1/applications");
  if (!data || !Array.isArray(data.items)) return { items: null };
  return { items: data.items };
});
