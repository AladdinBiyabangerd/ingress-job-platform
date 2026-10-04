import { NextResponse } from "next/server";
import { apiBase } from "../api";

const SAFE_RETURN = /^\/(?:(?:en|ru)(?:\/jobs\/\d+|\/post|\/company|\/admin|\/applications|\/profile|\/notifications)?|jobs\/\d+|post|company|admin|applications|profile|notifications)?$/;
const EXPIRED = new Date(0);
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
    logoutUrl: process.env.JOB_OIDC_LOGOUT_URL || "",
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

function cookieOptions(maxAgeSeconds) {
  const options = {
    path: "/",
    httpOnly: true,
    sameSite: "lax",
    secure: cookieSecure(),
    maxAge: maxAgeSeconds,
  };
  if (maxAgeSeconds <= 0) options.expires = EXPIRED;
  return options;
}

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
  return names;
}

export function clearAuthCookies(request) {
  return [...authCookieNames(request)].map((name) => cookie(name, "", 0));
}

function parseSetCookie(raw) {
  const parts = String(raw).split(";").map((part) => part.trim()).filter(Boolean);
  const [name, ...valueParts] = parts[0].split("=");
  let value = valueParts.join("=");
  try {
    value = decodeURIComponent(value);
  } catch {
    // keep raw value
  }
  const options = { path: "/", httpOnly: false, sameSite: "lax", secure: false };
  for (const part of parts.slice(1)) {
    const eq = part.indexOf("=");
    const key = (eq === -1 ? part : part.slice(0, eq)).trim().toLowerCase();
    const val = eq === -1 ? "" : part.slice(eq + 1).trim();
    if (key === "path") options.path = val || "/";
    else if (key === "httponly") options.httpOnly = true;
    else if (key === "secure") options.secure = true;
    else if (key === "samesite") options.sameSite = val.toLowerCase();
    else if (key === "max-age") options.maxAge = Number(val);
    else if (key === "expires") options.expires = new Date(val);
  }
  return { name, value, options };
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
  for (const raw of values) {
    const { name, value, options } = parseSetCookie(raw);
    next.cookies.set(name, value, options);
  }
  return next;
}

function appendOppositeSecureClears(response, names) {
  // NextResponse.cookies.set rebuilds Set-Cookie from its jar and drops prior
  // headers.append values, so opposite-Secure clears must be appended last.
  const secure = cookieSecure();
  const suffix = secure ? "" : "; Secure";
  for (const name of names) {
    response.headers.append(
      "Set-Cookie",
      `${name}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT${suffix}`,
    );
  }
  return response;
}

export function clearAuthCookiesOn(response, request) {
  const next = asNextResponse(response);
  const names = [...authCookieNames(request)];
  for (const name of names) next.cookies.set(name, "", cookieOptions(0));
  return appendOppositeSecureClears(next, names);
}

export function setAuthCookies(response, entries, request) {
  const next = asNextResponse(response);
  const cleared = [...authCookieNames(request)];
  for (const name of cleared) next.cookies.set(name, "", cookieOptions(0));
  for (const [name, value, maxAgeSeconds] of entries) {
    next.cookies.set(name, value, cookieOptions(maxAgeSeconds));
  }
  // Clear the opposite Secure slot for every auth name. An empty cookie with the
  // other Secure flag does not overwrite the values written above.
  return appendOppositeSecureClears(next, cleared);
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
    return { upstream: new Response(null, { status: 401 }), setCookies: clearAuthCookies(request) };
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
