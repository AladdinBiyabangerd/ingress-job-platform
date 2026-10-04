import { NextResponse } from "next/server";
import {
  clampAge,
  clearAuthCookiesOn,
  companyPath,
  noStore,
  oidcConfig,
  readCookie,
  safeReturnTo,
  setAuthCookies,
} from "../../../../lib/server/oidc";

export const runtime = "nodejs";

function fail(request, origin, code) {
  const response = NextResponse.redirect(new URL(`/?sso_error=${encodeURIComponent(code)}`, origin), 307);
  return noStore(clearAuthCookiesOn(response, request));
}

export async function GET(request) {
  const config = oidcConfig(request);
  const url = new URL(request.url);
  const code = url.searchParams.get("code") || "";
  const state = url.searchParams.get("state") || "";
  const oauthError = url.searchParams.get("error");
  const expected = readCookie(request, "job_oidc_state");
  if (oauthError || !code || code.length > 4096 || !state || state !== expected) {
    return fail(request, config.origin, oauthError ? "provider_error" : "invalid_callback");
  }

  let exchanged;
  try {
    exchanged = await fetch(`${config.apiBase}/api/v1/auth/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        state,
        code,
        redirect_uri: `${config.origin}/api/auth/callback`,
      }),
      cache: "no-store",
    });
  } catch {
    return fail(request, config.origin, "token_exchange_unavailable");
  }
  if (!exchanged.ok) return fail(request, config.origin, "token_exchange");

  const data = await exchanged.json();
  if (!data.access_token) return fail(request, config.origin, "invalid_token_response");
  let dest = safeReturnTo(data.return_to);
  if (data.me && data.me.needs_company_profile) dest = companyPath(dest);

  const entries = [
    ["job_access_token", data.access_token, clampAge(data.expires_in, 900, 3600)],
  ];
  if (data.refresh_token) {
    entries.push([
      "job_refresh_token",
      data.refresh_token,
      clampAge(data.refresh_expires_in, 3600, 365 * 24 * 60 * 60),
    ]);
  }
  return noStore(setAuthCookies(
    NextResponse.redirect(new URL(dest, config.origin), 307),
    entries,
    request,
  ));
}
