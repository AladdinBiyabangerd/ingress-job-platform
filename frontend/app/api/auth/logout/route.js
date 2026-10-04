import { NextResponse } from "next/server";
import { clearAuthCookiesOn, noStore, oidcConfig, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const url = new URL(request.url);
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  // Stay on the job site. Do not send the browser to Academy logout or authorize;
  // either one signs the same profile back in, and Academy logout is not ours to do.
  const location = new URL(returnTo, config.origin).toString();
  return noStore(clearAuthCookiesOn(NextResponse.redirect(location, 303), request));
}
