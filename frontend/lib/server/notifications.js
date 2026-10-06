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
 * Notification list for /notifications. Skips FastAPI for guests.
 * Deduped within one RSC request.
 */
export const getNotifications = cache(async () => {
  const me = await getMe();
  if (!me?.authenticated) {
    return { items: null, unread: null };
  }
  const store = await cookies();
  const access = store.get(ACCESS_COOKIE)?.value;
  if (!access) return { items: null, unread: null };
  const data = await loadJson(access, "/api/v1/notifications");
  if (!data || !Array.isArray(data.items)) return { items: null, unread: null };
  return { items: data.items, unread: Number(data.unread) || 0 };
});
