import { appendCookies, clearAuthCookies, noStore, oidcConfig, safeReturnTo } from "../../../../lib/server/oidc";

export const runtime = "nodejs";

export async function POST(request) {
  const url = new URL(request.url);
  const config = oidcConfig(request);
  const returnTo = safeReturnTo(url.searchParams.get("returnTo") || "/");
  const location = config.logoutUrl
    ? new URL(config.logoutUrl, config.origin).toString()
    : new URL(returnTo, config.origin).toString();
  const response = new Response(null, {
    status: 303,
    headers: { Location: location },
  });
  return noStore(appendCookies(response, clearAuthCookies(request)));
}
