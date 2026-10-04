import { NextResponse } from "next/server";
import { clearAuthCookiesOn, noStore, oidcConfig, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const url = new URL(request.url);
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  const location = config.logoutUrl
    ? new URL(config.logoutUrl, config.origin).toString()
    : new URL(returnTo, config.origin).toString();
  return noStore(clearAuthCookiesOn(NextResponse.redirect(location, 303), request));
}
