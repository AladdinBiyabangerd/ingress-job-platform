import { NextResponse } from "next/server";
import { apiBase } from "../api";

const SAFE_RETURN = /^\/(?:(?:en|ru)(?:\/jobs\/\d+|\/post|\/company|\/admin|\/applications|\/profile(?:\/review)?|\/me\/recommendations|\/settings\/emails|\/notifications)?|jobs\/\d+|post|company|admin|applications|profile(?:\/review)?|me\/recommendations|settings\/emails|notifications)?$/;

/** Current auth cookies. Legacy names are expired on every auth response but never trusted. */
export const ACCESS_COOKIE = "job_at";
export const REFRESH_COOKIE = "job_rt";
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
  return [ACCESS_COOKIE, REFRESH_COOKIE, ...LEGACY_AUTH_COOKIES]
    .flatMap((name) => expireVariants(name, request, false));
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

  const access = readCookie(request, ACCESS_COOKIE);
  if (access) {
    try {
      const upstream = await call(access);
      if (upstream.status !== 401) return { upstream, setCookies: [] };
    } catch {
      return { upstream: new Response(null, { status: 503 }), setCookies: [] };
    }
  }

  const refresh = readCookie(request, REFRESH_COOKIE);
  if (!refresh) {
    return {
      upstream: new Response(null, { status: 401 }),
      setCookies: access ? clearAuthCookies(request) : [],
    };
  }

  let refreshed;
  try {
    refreshed = await fetch(`${config.apiBase}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
  } catch {
    return { upstream: new Response(null, { status: 503 }), setCookies: [] };
  }
  if (!refreshed.ok) {
    // 401 = refresh token rejected (invalid_grant). 5xx = Academy/upstream
    // blip — keep cookies so a temporary outage does not force re-login.
    if (refreshed.status === 401) {
      return { upstream: new Response(null, { status: 401 }), setCookies: clearAuthCookies(request) };
    }
    return { upstream: new Response(null, { status: 503 }), setCookies: [] };
  }
  const data = await refreshed.json();
  const setCookies = [cookie(ACCESS_COOKIE, data.access_token, clampAge(data.expires_in, 900, 3600))];
  if (data.refresh_token) {
    setCookies.push(cookie(
      REFRESH_COOKIE,
      data.refresh_token,
      clampAge(data.refresh_expires_in, 3600, 365 * 24 * 60 * 60),
    ));
  }
  try {
    return { upstream: await call(data.access_token), setCookies };
  } catch {
    return { upstream: new Response(null, { status: 503 }), setCookies };
  }
}
