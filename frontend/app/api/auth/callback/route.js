import {
  appendCookies,
  clampAge,
  clearAuthCookies,
  companyPath,
  cookie,
  noStore,
  oidcConfig,
  readCookie,
  safeReturnTo,
} from "../../../../lib/server/oidc";

export const runtime = "nodejs";

function fail(origin, code) {
  const response = new Response(null, {
    status: 307,
    headers: { Location: new URL(`/?sso_error=${encodeURIComponent(code)}`, origin).toString() },
  });
  return noStore(appendCookies(response, clearAuthCookies()));
}

export async function GET(request) {
  const config = oidcConfig(request);
  const url = new URL(request.url);
  const code = url.searchParams.get("code") || "";
  const state = url.searchParams.get("state") || "";
  const oauthError = url.searchParams.get("error");
  const expected = readCookie(request, "job_oidc_state");
  if (oauthError || !code || code.length > 4096 || !state || state !== expected) {
    return fail(config.origin, oauthError ? "provider_error" : "invalid_callback");
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
    return fail(config.origin, "token_exchange_unavailable");
  }
  if (!exchanged.ok) return fail(config.origin, "token_exchange");

  const data = await exchanged.json();
  if (!data.access_token) return fail(config.origin, "invalid_token_response");
  let dest = safeReturnTo(data.return_to);
  if (data.me && data.me.needs_company_profile) dest = companyPath(dest);

  const response = new Response(null, {
    status: 307,
    headers: { Location: new URL(dest, config.origin).toString() },
  });
  const cookies = [
    cookie("job_oidc_state", "", 0),
    cookie("job_access_token", data.access_token, clampAge(data.expires_in, 900, 3600)),
  ];
  if (data.refresh_token) {
    cookies.push(cookie(
      "job_refresh_token",
      data.refresh_token,
      clampAge(data.refresh_expires_in, 3600, 365 * 24 * 60 * 60),
    ));
  }
  return noStore(appendCookies(response, cookies));
}
