import { cache } from "react";
import { cookies, headers } from "next/headers";
import { apiBase } from "../api";
import { ACCESS_COOKIE, applyCookieEntries, ensureSession, GUEST_COOKIE } from "./oidc";

const ME_TIMEOUT_MS = 5_000;

export const GUEST_ME = { authenticated: false };

/** Deduped ensureSession + cookie write for one RSC/server-action request. */
export const ensureRscSession = cache(async () => {
  const store = await cookies();
  const session = await ensureSession(store);
  applyCookieEntries(store, session.cookieEntries);
  return session;
});

/** Access token after ensureSession (shared by RSC seeders). */
export async function sessionAccess() {
  const session = await ensureRscSession();
  return session.access || null;
}

/**
 * Session identity for this RSC request. Guests skip FastAPI.
 * Near-exp / missing access refreshes via ensureSession before calling /me.
 * Deduped within one request (shell + cabinet).
 */
export const getMe = cache(async () => {
  const store = await cookies();
  if (store.get(GUEST_COOKIE)?.value) return GUEST_ME;
  const session = await ensureRscSession();
  if (!session.access) return GUEST_ME;
  try {
    const headerList = await headers();
    const locale = headerList.get("x-locale") || "az";
    const load = (token) => fetch(`${apiBase()}/api/v1/me?lang=${encodeURIComponent(locale)}`, {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(ME_TIMEOUT_MS),
    });
    let res = await load(session.access);
    if (res.status === 401) {
      const alreadyRotated = session.cookieEntries.some(([name]) => name === ACCESS_COOKIE);
      if (alreadyRotated) return GUEST_ME;
      const forced = await ensureSession(store, { force: true });
      applyCookieEntries(store, forced.cookieEntries);
      if (!forced.access) return GUEST_ME;
      res = await load(forced.access);
    }
    if (!res.ok) return GUEST_ME;
    const data = await res.json();
    return data && typeof data === "object" ? data : GUEST_ME;
  } catch {
    return null;
  }
});
