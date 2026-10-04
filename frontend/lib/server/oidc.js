import { apiBase } from "../api";

const SAFE_RETURN = /^\/(?:(?:en|ru)(?:\/jobs\/\d+|\/post|\/company|\/admin|\/applications|\/profile|\/notifications)?|jobs\/\d+|post|company|admin|applications|profile|notifications)?$/;

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
  const url = new URL(request.url);
  const configured = (process.env.APP_URL || process.env.NEXT_PUBLIC_APP_URL || "").replace(/\/$/, "");
  const railwayHost = (process.env.RAILWAY_PUBLIC_DOMAIN || "").trim();
  const origin = configured
    || (railwayHost ? `https://${railwayHost}` : `${url.protocol}//${url.host}`);
  const issuer = (process.env.JOB_OIDC_ISSUER || "http://127.0.0.1:8000/").replace(/\/?$/, "/");
  return {
    origin,
    clientId: process.env.JOB_OIDC_CLIENT_ID || "job-web",
    authorizeUrl: process.env.JOB_OIDC_AUTHORIZE_URL || new URL("portal/oauth/authorize", issuer).toString(),
    apiBase: apiBase(),
  };
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

export function cookie(name, value, maxAgeSeconds) {
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAgeSeconds}${secure}`;
}

export function clearAuthCookies() {
  return [cookie("job_oidc_state", "", 0), cookie("job_access_token", "", 0), cookie("job_refresh_token", "", 0)];
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

export function appendCookies(response, values) {
  for (const value of values) response.headers.append("Set-Cookie", value);
  return response;
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
    return { upstream: new Response(null, { status: 401 }), setCookies: access ? clearAuthCookies() : [] };
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
    return { upstream: new Response(null, { status: 401 }), setCookies: clearAuthCookies() };
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
