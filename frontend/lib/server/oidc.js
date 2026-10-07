import { NextResponse } from "next/server";
import { apiBase } from "../api";
import { ensureSessionLogic, sessionEntriesFromTokens } from "./ensure-session-logic";

const SAFE_RETURN = /^\/(?:(?:en|ru)(?:\/jobs\/\d+|\/post|\/company|\/admin|\/applications|\/profile(?:\/review)?|\/me\/(?:recommendations|skills)|\/settings\/emails|\/notifications|\/trends(?:\/\d+)?)?|jobs\/\d+|post|company|admin|applications|profile(?:\/review)?|me\/(?:recommendations|skills)|settings\/emails|notifications|trends(?:\/\d+)?)?$/;

/** Current auth cookies. Legacy names are expired on every auth response but never trusted. */
export const ACCESS_COOKIE = "job_at";
export const REFRESH_COOKIE = "job_rt";
export const EXP_COOKIE = "job_exp";
export const STATE_COOKIE = "job_st";
export const GUEST_COOKIE = "job_guest";

const LEGACY_AUTH_COOKIES = [
  "job_access_token",
  "job_refresh_token",
  "job_oidc_state",
  "job_oidc_nonce",
  "job_pkce_verifier",
  "job_pkce_challenge",
  "job_session",
  "job_token",
];

export function safeReturnTo(value) {
  const text = typeof value === "string" ? value.trim() : "";
  return SAFE_RETURN.test(text) ? text : "/";
}

export function companyPath(returnTo) {
  if (returnTo.startsWith("/en")) return "/en/company";
  if (returnTo.startsWith("/ru")) return "/ru/company";
  return "/company";
}

export function oidcConfig(request) {
  const origin = publicOrigin(request);
  const issuer = (process.env.JOB_OIDC_ISSUER || "http://127.0.0.1:8000/").replace(/\/?$/, "/");
  return {
    origin,
    clientId: process.env.JOB_OIDC_CLIENT_ID || "job-web",
    authorizeUrl: process.env.JOB_OIDC_AUTHORIZE_URL || new URL("portal/oauth/authorize", issuer).toString(),
    jobAccountUrl:
      process.env.JOB_OIDC_JOB_ACCOUNT_URL || new URL("portal/job-account/", issuer).toString(),
    apiBase: apiBase(),
  };
}

export function publicOrigin(request) {
  const url = new URL(request.url);
  const configured = (process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL || "").trim().replace(/\/$/, "");
  const railwayHost = (process.env.RAILWAY_PUBLIC_DOMAIN || "").trim();
  return configured || (railwayHost ? `https://${railwayHost}` : `${url.protocol}//${url.host}`);
}

export function readCookie(request, name) {
  const header = request.headers.get("cookie") || "";
  for (const item of header.split(";")) {
    const [rawName, ...parts] = item.trim().split("=");
    if (rawName !== name) continue;
    try {
      return decodeURIComponent(parts.join("="));
    } catch {
      return null;
    }
  }
  return null;
}

function cookieSecure() {
  return process.env.NODE_ENV === "production";
}

export function cookie(name, value, maxAgeSeconds) {
  const secure = cookieSecure() ? "; Secure" : "";
  const expires = maxAgeSeconds <= 0 ? "; Expires=Thu, 01 Jan 1970 00:00:00 GMT" : "";
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSeconds}${expires}${secure}`;
}

function requestHosts(request) {
  const hosts = new Set();
  const add = (value) => {
    const host = String(value || "").trim().toLowerCase().split(":")[0];
    if (host && /^[a-z0-9.-]+$/.test(host)) hosts.add(host);
  };
  try {
    add(new URL(request?.url || "http://localhost/").hostname);
  } catch {
    // ignore
  }
  try {
    add(new URL(publicOrigin(request)).hostname);
  } catch {
    // ignore
  }
  add(request?.headers?.get("host"));
  add(request?.headers?.get("x-forwarded-host")?.split(",")[0]);
  return [...hosts];
}

function clearDomains(request) {
  const domains = [""];
  for (const host of requestHosts(request)) {
    if (host.includes(".") && !host.endsWith(".localhost") && !/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
      domains.push(host);
    }
  }
  return domains;
}

function expireVariants(name, request, spareLive) {
  const liveSecure = cookieSecure();
  const headers = [];
  for (const domain of clearDomains(request)) {
    for (const secure of [false, true]) {
      if (spareLive && domain === "" && secure === liveSecure) continue;
      const parts = [
        `${name}=`,
        "Path=/",
        "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
        "Max-Age=0",
        "HttpOnly",
        "SameSite=Lax",
      ];
      if (domain) parts.push(`Domain=${domain}`);
      if (secure) parts.push("Secure");
      headers.push(parts.join("; "));
    }
  }
  return headers;
}

function guestSetHeaders() {
  const secure = cookieSecure() ? "; Secure" : "";
  return [`${GUEST_COOKIE}=1; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400${secure}`];
}

function allAuthCookieNames(request) {
  const names = new Set([
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    EXP_COOKIE,
    STATE_COOKIE,
    ...LEGACY_AUTH_COOKIES,
  ]);
  const header = request?.headers?.get("cookie") || "";
  for (const item of header.split(";")) {
    const name = item.trim().split("=", 1)[0];
    if (/^job_(?:access|refresh|token|session|state|nonce|oidc_|pkce_|at|rt|st)/.test(name)) {
      names.add(name);
    }
  }
  return [...names];
}

export function clearAuthCookies(request) {
  return allAuthCookieNames(request).flatMap((name) => expireVariants(name, request, false));
}

export function clampAge(value, fallback, max) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return fallback;
  return Math.max(1, Math.min(Math.floor(number), max));
}

export function noStore(response) {
  response.headers.set("Cache-Control", "no-store, max-age=0");
  response.headers.set("Pragma", "no-cache");
  return response;
}

export function asNextResponse(response) {
  if (response instanceof NextResponse) return response;
  return new NextResponse(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export function appendCookies(response, values) {
  if (!values?.length) return response;
  const next = asNextResponse(response);
  for (const value of values) next.headers.append("Set-Cookie", value);
  return next;
}

function applyCookieHeaders(response, headers) {
  const next = asNextResponse(response);
  for (const value of headers) next.headers.append("Set-Cookie", value);
  return next;
}

export function clearAuthCookiesOn(response, request) {
  return applyCookieHeaders(response, [...clearAuthCookies(request), ...guestSetHeaders()]);
}

export function setAuthCookies(response, entries, request) {
  const setting = new Set(entries.map(([name]) => name));
  const headers = [];
  for (const name of allAuthCookieNames(request)) {
    headers.push(...expireVariants(name, request, setting.has(name)));
  }
  headers.push(...expireVariants(GUEST_COOKIE, request, false));
  for (const [name, value, maxAgeSeconds] of entries) {
    headers.push(cookie(name, value, maxAgeSeconds));
  }
  return applyCookieHeaders(response, headers);
}

/** Start OAuth after logout without dropping the guest lock. */
export function beginLoginCookies(response, state, request) {
  const headers = [];
  for (const name of allAuthCookieNames(request)) {
    headers.push(...expireVariants(name, request, name === STATE_COOKIE));
  }
  headers.push(...guestSetHeaders());
  headers.push(cookie(STATE_COOKIE, state, 600));
  return applyCookieHeaders(response, headers);
}

export function signedOut(request) {
  return Boolean(readCookie(request, GUEST_COOKIE));
}

export function hasSessionCookies(request) {
  return Boolean(readCookie(request, ACCESS_COOKIE) || readCookie(request, REFRESH_COOKIE));
}

function clearSessionCookies(request) {
  return [ACCESS_COOKIE, REFRESH_COOKIE, EXP_COOKIE, ...LEGACY_AUTH_COOKIES]
    .flatMap((name) => expireVariants(name, request, false));
}

function readSessionValue(source, name) {
  if (source && typeof source.headers?.get === "function") {
    return readCookie(source, name);
  }
  const raw = source?.get?.(name);
  if (raw == null) return null;
  return typeof raw === "string" ? raw : (raw.value ?? null);
}

function clearSessionEntries() {
  return [
    [ACCESS_COOKIE, "", 0],
    [REFRESH_COOKIE, "", 0],
    [EXP_COOKIE, "", 0],
    [GUEST_COOKIE, "1", 86400],
  ];
}

export function authCookieEntries(data) {
  return sessionEntriesFromTokens(data, { clampAge });
}

export function entriesToSetCookies(entries) {
  return (entries || []).map(([name, value, maxAge]) => cookie(name, value, maxAge));
}

/** Write ensureSession cookieEntries via Next.js `cookies()` store (RSC / Server Action). */
export function applyCookieEntries(store, entries) {
  if (!entries?.length) return;
  const secure = cookieSecure();
  for (const [name, value, maxAge] of entries) {
    store.set({
      name,
      value: value || "",
      httpOnly: true,
      path: "/",
      sameSite: "lax",
      maxAge,
      secure,
      ...(maxAge <= 0 ? { expires: new Date(0) } : {}),
    });
  }
}

/**
 * One session path for Route Handlers, RSC, and Server Actions.
 * @returns {{ access: string|null, cookieEntries: Array, setCookies: string[], guest: boolean }}
 */
export async function ensureSession(source, { force = false } = {}) {
  const isRequest = Boolean(source && typeof source.headers?.get === "function");
  const base = isRequest ? oidcConfig(source).apiBase : apiBase();
  const result = await ensureSessionLogic({
    getCookie: (name) => readSessionValue(source, name),
    fetchFn: fetch,
    apiBaseUrl: base,
    force,
    clampAge,
    clearEntries: clearSessionEntries,
  });
  let setCookies = entriesToSetCookies(result.cookieEntries);
  if (isRequest && result.cookieEntries.some(([name, , maxAge]) => name === GUEST_COOKIE || maxAge === 0)) {
    // Full clear on refresh rejection: expire domain variants like logout.
    if (!result.access && result.cookieEntries.some(([n]) => n === GUEST_COOKIE)) {
      setCookies = clearAuthCookies(source);
    }
  }
  return {
    access: result.access,
    cookieEntries: result.cookieEntries,
    setCookies,
    guest: Boolean(result.guest),
  };
}

export async function authorizedApi(request, path, init = {}) {
  const config = oidcConfig(request);
  const call = (token) => fetch(`${config.apiBase}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    cache: "no-store",
  });

  // Guest lock stays until a matching login callback finishes. Never rebuild
  // the session from leftover tokens, and do not wipe OIDC state mid-login.
  if (signedOut(request)) {
    const leftover = hasSessionCookies(request)
      || Boolean(readCookie(request, "job_access_token") || readCookie(request, "job_refresh_token"));
    return {
      upstream: new Response(null, { status: 401 }),
      setCookies: leftover ? clearSessionCookies(request) : [],
    };
  }

  let session = await ensureSession(request);
  const setCookies = [...session.setCookies];
  if (!session.access) {
    return { upstream: new Response(null, { status: 401 }), setCookies };
  }
  // If we already rotated refresh this request, do not force-refresh again
  // with the stale request cookie (Academy revokes the family on reuse).
  const rotated = session.cookieEntries.some(([name]) => name === ACCESS_COOKIE);

  try {
    let upstream = await call(session.access);
    if (upstream.status === 401) {
      if (rotated) {
        setCookies.push(...clearAuthCookies(request));
        return { upstream: new Response(null, { status: 401 }), setCookies };
      }
      session = await ensureSession(request, { force: true });
      setCookies.push(...session.setCookies);
      if (!session.access) {
        return { upstream: new Response(null, { status: 401 }), setCookies };
      }
      upstream = await call(session.access);
    }
    return { upstream, setCookies };
  } catch {
    return { upstream: new Response(null, { status: 503 }), setCookies };
  }
}
