import { cache } from "react";
import { cookies } from "next/headers";
import { apiBase } from "../api";
import { ACCESS_COOKIE, GUEST_COOKIE, REFRESH_COOKIE } from "./oidc";

const ME_TIMEOUT_MS = 5_000;

export const GUEST_ME = { authenticated: false };

/**
 * Session identity for this RSC request. Guests skip FastAPI.
 * Expired access (401) returns null so the client BFF can refresh cookies.
 * Deduped within one request (shell + cabinet).
 */
export const getMe = cache(async () => {
  const store = await cookies();
  if (store.get(GUEST_COOKIE)?.value) return GUEST_ME;
  const access = store.get(ACCESS_COOKIE)?.value;
  if (!access) {
    return store.get(REFRESH_COOKIE)?.value ? null : GUEST_ME;
  }
  try {
    const res = await fetch(`${apiBase()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${access}`, Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.timeout(ME_TIMEOUT_MS),
    });
    if (res.status === 401) return null;
    if (!res.ok) return GUEST_ME;
    const data = await res.json();
    return data && typeof data === "object" ? data : GUEST_ME;
  } catch {
    return null;
  }
});
