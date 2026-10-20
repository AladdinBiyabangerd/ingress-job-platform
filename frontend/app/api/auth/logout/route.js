import { NextResponse } from "next/server";
import { buildEndSessionUrl, postLogoutRedirectUri } from "../../../../lib/oidc-logout";
import {
  ID_TOKEN_COOKIE,
  REFRESH_COOKIE,
  clearAuthCookiesOn,
  noStore,
  oidcConfig,
  readCookie,
  safeReturnTo,
} from "../../../../lib/server/oidc";

export const runtime = "nodejs";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Best-effort Academy refresh revoke when JOB_OIDC_REVOKE_URL is set. */
async function revokeRefreshIfConfigured(request, config) {
  const revokeUrl = (process.env.JOB_OIDC_REVOKE_URL || "").trim();
  if (!revokeUrl) return;
  const refresh = readCookie(request, REFRESH_COOKIE);
  if (!refresh) return;
  const body = new URLSearchParams({
    token: refresh,
    token_type_hint: "refresh_token",
    client_id: config.clientId || "",
  });
  const secret = (process.env.OIDC_CLIENT_SECRET || process.env.JOB_OIDC_CLIENT_SECRET || "").trim();
  const headers = { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" };
  if (secret) {
    const basic = Buffer.from(`${config.clientId}:${secret}`).toString("base64");
    headers.Authorization = `Basic ${basic}`;
  }
  try {
    await fetch(revokeUrl, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    // Local cookie clear still proceeds; Academy revoke is best-effort.
  }
}

export async function POST(request) {
  const url = new URL(request.url);
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  const idTokenHint = readCookie(request, ID_TOKEN_COOKIE) || "";
  await revokeRefreshIfConfigured(request, config);
  // End the Academy session too (RP-Initiated Logout). Otherwise the next
  // login reuses it and puts the same person straight back. Academy returns
  // to the registered site root; JOB_OIDC_END_SESSION_URL=off stays on Job.
  const location =
    buildEndSessionUrl({
      endSessionUrl: config.endSessionUrl,
      clientId: config.clientId,
      idTokenHint,
      postLogoutRedirectUri: postLogoutRedirectUri(config.origin),
    }) || new URL(returnTo, config.origin).toString();
  // 200 + client navigation applies Set-Cookie more reliably than a bare 303 in
  // some browsers/proxies; old Tofig tokens were surviving the redirect logout.
  const html = `<!doctype html><html lang="az"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=${escapeHtml(location)}"><title>Çıxış</title></head><body><p>Çıxış edildi.</p><script>location.replace(${JSON.stringify(location)})</script></body></html>`;
  const response = new NextResponse(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
  return noStore(clearAuthCookiesOn(response, request));
}
