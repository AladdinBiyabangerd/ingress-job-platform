import { cache } from "react";
import { cookies, headers } from "next/headers";
import { apiBase } from "../api";
import { ACCESS_COOKIE, applyCookieEntries, ensureSession, GUEST_COOKIE } from "./oidc";

const ME_TIMEOUT_MS = 5_000;
const ACCESS_HEADER = "x-job-access";

export const GUEST_ME = { authenticated: false };

/**
 * Deduped session for one RSC / Server Action request.
 * Prefer middleware-forwarded access (cookie writes happen in middleware).
 * Server Actions may still refresh + write when the header is absent.
 */
export const ensureRscSession = cache(async () => {
  const headerList = await headers();
  const forwarded = headerList.get(ACCESS_HEADER);
  if (forwarded) {
    return { access: forwarded, cookieEntries: [], setCookies: [], guest: false };
  }

  const store = await cookies();
  if (store.get(GUEST_COOKIE)?.value) {
    return { access: null, cookieEntries: [], setCookies: [], guest: true };
  }

  // Server Action (Next-Action) may mutate cookies; RSC must not.
  const canWrite = Boolean(headerList.get("next-action"));
  if (canWrite) {
    const session = await ensureSession(store);
    applyCookieEntries(store, session.cookieEntries);
    return session;
  }

  // RSC without middleware forward: read access only — never refresh/write.
  const access = store.get(ACCESS_COOKIE)?.value || null;
  return { access, cookieEntries: [], setCookies: [], guest: false };
});

/** Access token after ensureSession (shared by RSC seeders). */
export async function sessionAccess() {
  const session = await ensureRscSession();
  return session.access || null;
}

/**
 * Session identity for this RSC request. Guests skip FastAPI.
 * Near-exp access is refreshed in middleware; this path only reads.
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
    const res = await fetch(`${apiBase()}/api/v1/me?lang=${encodeURIComponent(locale)}`, {
      headers: { Authorization: `Bearer ${session.access}`, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(ME_TIMEOUT_MS),
    });
    if (!res.ok) return GUEST_ME;
    const data = await res.json();
    return data && typeof data === "object" ? data : GUEST_ME;
  } catch {
    return null;
  }
});
