import { NextResponse } from "next/server";
import { apiBase } from "../api";

const SAFE_RETURN = /^\/(?:(?:en|ru)(?:\/jobs\/\d+|\/post|\/company|\/admin|\/applications|\/profile|\/notifications)?|jobs\/\d+|post|company|admin|applications|profile|notifications)?$/;
const AUTH_COOKIE_NAMES = [
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

const CLEAR_PATHS = ["/", "/api", "/api/auth", "/api/auth/callback", "/api/auth/login", "/api/auth/logout", "/api/auth/me"];
const GUEST_COOKIE = "job_guest";

export function cookie(name, value, maxAgeSeconds) {
  const secure = cookieSecure() ? "; Secure" : "";
  const expires = maxAgeSeconds <= 0 ? "; Expires=Thu, 01 Jan 1970 00:00:00 GMT" : "";
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSeconds}${expires}${secure}`;
}

function authCookieNames(request) {
  const names = new Set(AUTH_COOKIE_NAMES);
  const header = request?.headers?.get("cookie") || "";
  for (const item of header.split(";")) {
    const name = item.trim().split("=", 1)[0];
    if (/^job_(?:access|refresh|token|session|state|nonce|oidc_|pkce_)/.test(name)) names.add(name);
  }
  return [...names];
}

function clearPaths(request) {
  const paths = new Set(CLEAR_PATHS);
  try {
    const pathname = new URL(request?.url || "http://localhost/").pathname || "/";
    let acc = "";
    for (const bit of pathname.split("/").filter(Boolean)) {
      if (!/^[A-Za-z0-9._~-]+$/.test(bit)) break;
      acc += `/${bit}`;
      if (acc.length > 200) break;
      paths.add(acc);
    }
  } catch {
    // The fixed paths still cover the auth routes.
  }
  return [...paths];
}

function clearDomains(request) {
  const domains = [""];
  try {
    const host = new URL(publicOrigin(request)).hostname.toLowerCase();
    const named = /^[a-z0-9.-]+$/.test(host) && host.includes(".") && !host.endsWith(".localhost") && !/^\d+\.\d+\.\d+\.\d+$/.test(host);
    if (named) domains.push(host);
  } catch {
    // Host-only clears still apply to whatever host the browser used.
  }
  return domains;
}

function expireVariants(name, request, spareHostRoot) {
  const liveSecure = cookieSecure();
  const headers = [];
  for (const path of clearPaths(request)) {
    for (const domain of clearDomains(request)) {
      if (domain && path !== "/") continue;
      for (const secure of [false, true]) {
        if (spareHostRoot && path === "/" && domain === "" && secure === liveSecure) continue;
        const parts = [
          `${name}=`,
          `Path=${path}`,
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
  }
  return headers;
}

function guestSetHeaders() {
  const base = `${GUEST_COOKIE}=1; Path=/; HttpOnly; SameSite=Lax; Max-Age=86400`;
  return [base, `${base}; Secure`];
}

export function clearAuthCookies(request) {
  return authCookieNames(request).flatMap((name) => expireVariants(name, request, false));
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

export function clearAuthCookiesOn(response, request) {
  const next = asNextResponse(response);
  for (const value of [...clearAuthCookies(request), ...guestSetHeaders()]) {
    next.headers.append("Set-Cookie", value);
  }
  return next;
}

export function setAuthCookies(response, entries, request) {
  const next = asNextResponse(response);
  const setting = new Set(entries.map(([name]) => name));
  const headers = [];
  for (const name of authCookieNames(request)) {
    headers.push(...expireVariants(name, request, setting.has(name)));
  }
  headers.push(...expireVariants(GUEST_COOKIE, request, false));
  for (const [name, value, maxAgeSeconds] of entries) {
    headers.push(cookie(name, value, maxAgeSeconds));
  }
  for (const value of headers) next.headers.append("Set-Cookie", value);
  return next;
}

export function signedOut(request) {
  return Boolean(readCookie(request, GUEST_COOKIE));
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

  // A refresh cookie must not rebuild the session after logout. The guest
  // cookie stays until the visitor starts a new sign-in.
  if (signedOut(request)) {
    const header = request.headers.get("cookie") || "";
    const leftover = /(?:^|;\s*)job_(?:access|refresh|token|session|state|nonce|oidc_|pkce_)/.test(header);
    return {
      upstream: new Response(null, { status: 401 }),
      setCookies: leftover ? clearAuthCookies(request) : [],
    };
  }

  const access = readCookie(request, "job_access_token");
  if (access) {
    try {
      const upstream = await call(access);
      if (upstream.status !== 401) return { upstream, setCookies: [] };
    } catch {
      return { upstream: new Response(null, { status: 503 }), setCookies: [] };
    }
  }

  const refresh = readCookie(request, "job_refresh_token");
  if (!refresh) {
    return { upstream: new Response(null, { status: 401 }), setCookies: access ? clearAuthCookies(request) : [] };
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
  const setCookies = [cookie("job_access_token", data.access_token, clampAge(data.expires_in, 900, 3600))];
  if (data.refresh_token) {
    setCookies.push(cookie(
      "job_refresh_token",
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
